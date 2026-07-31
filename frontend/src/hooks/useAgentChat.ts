import { useCallback, useEffect, useRef, useState } from "react"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { API_BASE, fetchChatHistory, getOrCreateThreadId } from "@/lib/api"
import type { AnalysisResult, ChatMessage, ChatRequestBody, FileEdit, ToolCallStatus } from "@/types"

function newId() {
  return crypto.randomUUID()
}

interface UseAgentChatOptions {
  rootDir: string | null
  onFileWritten?: (edit: FileEdit) => void
}

export function useAgentChat({ rootDir, onFileWritten }: UseAgentChatOptions) {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isHydrating, setIsHydrating] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [awaitingAuthorization, setAwaitingAuthorization] = useState(false)
  const [writtenFiles, setWrittenFiles] = useState<Record<string, FileEdit>>({})
  const [proposedEdits, setProposedEdits] = useState<Record<string, FileEdit>>({})
  const abortRef = useRef<AbortController | null>(null)
  const onFileWrittenRef = useRef(onFileWritten)
  onFileWrittenRef.current = onFileWritten

  // Short-term memory now lives server-side, keyed by thread_id (one per
  // rootDir, persisted in localStorage) — on opening a directory we hydrate
  // a plain-text transcript from the checkpointer rather than starting
  // empty, so reopening the same project resumes the same conversation.
  useEffect(() => {
    setMessages([])
    setWrittenFiles({})
    setProposedEdits({})
    setAwaitingAuthorization(false)
    if (!rootDir) {
      setThreadId(null)
      return
    }
    const id = getOrCreateThreadId(rootDir)
    setThreadId(id)
    setIsHydrating(true)
    fetchChatHistory(rootDir, id)
      .then((turns) => {
        setMessages(turns.map((t) => ({ id: newId(), role: t.role, content: t.content })))
      })
      .catch(() => {
        // No prior state (fresh thread) or the store is unreachable —
        // starting with an empty transcript is a fine fallback either way.
      })
      .finally(() => setIsHydrating(false))
  }, [rootDir])

  const updateMessage = useCallback(
    (id: string, updater: (m: ChatMessage) => ChatMessage) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)))
    },
    [],
  )

  const runTurn = useCallback(
    async (userMessage: string, authorized: boolean) => {
      if (!rootDir || !threadId) return
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const assistantId = newId()

      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", streaming: true, startedAt: Date.now() },
      ])
      setIsStreaming(true)
      setAwaitingAuthorization(false)

      const toolCalls: ToolCallStatus[] = []
      const analyses: AnalysisResult[] = []
      const proposals: FileEdit[] = []
      const edits: FileEdit[] = []

      const markToolDone = (tool: string) => {
        const idx = toolCalls.findIndex((t) => t.tool === tool && t.status === "running")
        if (idx !== -1) toolCalls[idx] = { ...toolCalls[idx], status: "done" }
      }

      try {
        await fetchEventSource(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: userMessage,
            thread_id: threadId,
            root_dir: rootDir,
            authorized,
          } satisfies ChatRequestBody),
          signal: controller.signal,
          openWhenHidden: true,

          async onopen(res) {
            if (!res.ok) {
              const body = await res.json().catch(() => null)
              throw new Error(body?.detail ?? `Chat request failed: ${res.status}`)
            }
          },

          onmessage(ev) {
            if (!ev.data) return
            const payload = JSON.parse(ev.data)

            switch (ev.event) {
              case "tool_start": {
                toolCalls.push({ tool: payload.tool, status: "running" })
                updateMessage(assistantId, (m) => ({ ...m, toolCalls: [...toolCalls] }))
                break
              }
              case "analysis_result": {
                markToolDone(payload.tool)
                analyses.push({
                  tool: payload.tool,
                  file_name: payload.file_name,
                  summary: payload.summary,
                  findings: payload.findings ?? [],
                })
                updateMessage(assistantId, (m) => ({
                  ...m,
                  toolCalls: [...toolCalls],
                  analyses: [...analyses],
                }))
                break
              }
              case "edit_proposed": {
                markToolDone("propose_edit")
                const proposal: FileEdit = {
                  file_name: payload.file_name,
                  explanation: payload.explanation,
                  original_code: payload.original_code,
                  proposed_code: payload.proposed_code,
                }
                proposals.push(proposal)
                setProposedEdits((prev) => ({ ...prev, [proposal.file_name]: proposal }))
                updateMessage(assistantId, (m) => ({
                  ...m,
                  toolCalls: [...toolCalls],
                  proposals: [...proposals],
                }))
                break
              }
              case "file_written": {
                markToolDone("write_file")
                const edit: FileEdit = {
                  file_name: payload.file_name,
                  explanation: payload.explanation,
                  original_code: payload.original_code,
                  proposed_code: payload.proposed_code,
                }
                edits.push(edit)
                setWrittenFiles((prev) => ({ ...prev, [edit.file_name]: edit }))
                onFileWrittenRef.current?.(edit)
                updateMessage(assistantId, (m) => ({
                  ...m,
                  toolCalls: [...toolCalls],
                  edits: [...edits],
                }))
                break
              }
              case "token": {
                updateMessage(assistantId, (m) => ({
                  ...m,
                  content: m.content + payload.text,
                }))
                break
              }
              case "awaiting_authorization": {
                setAwaitingAuthorization(true)
                break
              }
              case "done": {
                break
              }
              case "error": {
                updateMessage(assistantId, (m) => ({
                  ...m,
                  content: m.content || `Error: ${payload.message}`,
                }))
                break
              }
            }
          },

          onerror(err) {
            // rethrow to stop fetchEventSource's built-in retry loop
            throw err
          },
        })
      } catch (err) {
        updateMessage(assistantId, (m) =>
          m.content
            ? m
            : {
                ...m,
                content:
                  err instanceof Error ? err.message : "The agent connection was interrupted.",
              },
        )
      } finally {
        updateMessage(assistantId, (m) => ({ ...m, streaming: false }))
        setIsStreaming(false)
      }
    },
    [rootDir, threadId, updateMessage],
  )

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming || !rootDir) return
      const userMsg: ChatMessage = { id: newId(), role: "user", content: trimmed }
      setMessages((prev) => [...prev, userMsg])
      void runTurn(trimmed, false)
    },
    [isStreaming, rootDir, runTurn],
  )

  const authorize = useCallback(() => {
    if (isStreaming) return
    const note = "You authorized the proposed changes. Proceed with write_file."
    const authMsg: ChatMessage = {
      id: newId(),
      role: "user",
      content: note,
      kind: "authorization",
    }
    setMessages((prev) => [...prev, authMsg])
    void runTurn(note, true)
  }, [isStreaming, runTurn])

  const reject = useCallback(() => {
    setAwaitingAuthorization(false)
    const note: ChatMessage = {
      id: newId(),
      role: "user",
      content: "You rejected the proposed plan. Do not implement it without a revised plan.",
      kind: "rejection",
    }
    setMessages((prev) => [...prev, note])
  }, [])

  return {
    messages,
    isHydrating,
    isStreaming,
    awaitingAuthorization,
    writtenFiles,
    proposedEdits,
    sendMessage,
    authorize,
    reject,
  }
}
