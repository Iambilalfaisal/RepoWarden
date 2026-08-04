import { useCallback, useEffect, useRef, useState } from "react"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { API_BASE, fetchChatHistory, getOrCreateThreadId } from "@/lib/api"
import type {
  AnalysisResult,
  ChatMessage,
  ChatRequestBody,
  FileDecision,
  FileEdit,
  PlanSummary,
  ResumeRequestBody,
  ToolCallStatus,
} from "@/types"

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
  // Per-file approvals pending inside an already-authorized Editor run (a
  // real LangGraph interrupt() per write_file call — see
  // HumanInTheLoopMiddleware in app/agents/editor/agent.py) — distinct from
  // awaitingAuthorization above, which gates whether the Editor gets
  // invoked at all.
  const [pendingApprovals, setPendingApprovals] = useState<FileEdit[]>([])
  const [writtenFiles, setWrittenFiles] = useState<Record<string, FileEdit>>({})
  const [proposedEdits, setProposedEdits] = useState<Record<string, FileEdit>>({})
  const abortRef = useRef<AbortController | null>(null)
  const onFileWrittenRef = useRef(onFileWritten)
  onFileWrittenRef.current = onFileWritten
  const messagesRef = useRef<ChatMessage[]>([])
  const lastAssistantIdRef = useRef<string | null>(null)
  const decisionsRef = useRef<Record<string, FileDecision>>({})

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Short-term memory now lives server-side, keyed by thread_id (one per
  // rootDir, persisted in localStorage) — on opening a directory we hydrate
  // a plain-text transcript from the checkpointer rather than starting
  // empty, so reopening the same project resumes the same conversation.
  useEffect(() => {
    setMessages([])
    setWrittenFiles({})
    setProposedEdits({})
    setAwaitingAuthorization(false)
    setPendingApprovals([])
    decisionsRef.current = {}
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

  // Shared SSE consumer for both a fresh turn (POST /api/chat) and a
  // resume after per-file approval (POST /api/chat/resume) — both speak
  // the same event vocabulary and both append to the same assistant
  // bubble, since a resume is a continuation of the same paused turn, not
  // a new one.
  const streamEvents = useCallback(
    async (url: string, body: unknown, assistantId: string) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)

      const existing = messagesRef.current.find((m) => m.id === assistantId)
      const toolCalls: ToolCallStatus[] = [...(existing?.toolCalls ?? [])]
      const analyses: AnalysisResult[] = [...(existing?.analyses ?? [])]
      const proposals: FileEdit[] = [...(existing?.proposals ?? [])]
      const edits: FileEdit[] = [...(existing?.edits ?? [])]

      const markToolDone = (tool: string) => {
        const idx = toolCalls.findIndex((t) => t.tool === tool && t.status === "running")
        if (idx !== -1) toolCalls[idx] = { ...toolCalls[idx], status: "done" }
      }

      try {
        await fetchEventSource(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
          openWhenHidden: true,

          async onopen(res) {
            if (!res.ok) {
              const resBody = await res.json().catch(() => null)
              throw new Error(resBody?.detail ?? `Chat request failed: ${res.status}`)
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
              case "plan_summary": {
                const planSummary = payload as PlanSummary
                updateMessage(assistantId, (m) => ({ ...m, planSummary }))
                break
              }
              case "approval_required": {
                const pending: FileEdit[] = (payload.pending ?? []).map(
                  (p: FileEdit) => ({
                    file_name: p.file_name,
                    explanation: p.explanation,
                    original_code: p.original_code,
                    proposed_code: p.proposed_code,
                  }),
                )
                decisionsRef.current = {}
                setPendingApprovals(pending)
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
    [updateMessage],
  )

  const runTurn = useCallback(
    async (userMessage: string, authorized: boolean) => {
      if (!rootDir || !threadId) return

      const assistantId = newId()
      lastAssistantIdRef.current = assistantId
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", streaming: true, startedAt: Date.now() },
      ])
      setAwaitingAuthorization(false)
      setPendingApprovals([])

      await streamEvents(
        `${API_BASE}/api/chat`,
        {
          message: userMessage,
          thread_id: threadId,
          root_dir: rootDir,
          authorized,
        } satisfies ChatRequestBody,
        assistantId,
      )
    },
    [rootDir, threadId, streamEvents],
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

  // Per-file decision inside an already-authorized Editor run. Each
  // write_file call pauses independently (HumanInTheLoopMiddleware), and
  // a single interrupt can bundle more than one pending file if the model
  // requested several writes in the same turn — all of them must be
  // decided before the run can resume, so this only fires the actual
  // /api/chat/resume call once every currently-pending file has a decision.
  const decideFile = useCallback(
    (fileName: string, type: "approve" | "reject", message?: string) => {
      decisionsRef.current[fileName] = { file_name: fileName, type, message }
      const allDecided = pendingApprovals.every((p) => decisionsRef.current[p.file_name])
      if (!allDecided || !rootDir || !threadId || !lastAssistantIdRef.current) return

      const decisions = pendingApprovals.map((p) => decisionsRef.current[p.file_name])
      const assistantId = lastAssistantIdRef.current
      decisionsRef.current = {}
      setPendingApprovals([])

      void streamEvents(
        `${API_BASE}/api/chat/resume`,
        { thread_id: threadId, root_dir: rootDir, decisions } satisfies ResumeRequestBody,
        assistantId,
      )
    },
    [pendingApprovals, rootDir, threadId, streamEvents],
  )

  return {
    messages,
    isHydrating,
    isStreaming,
    awaitingAuthorization,
    pendingApprovals,
    writtenFiles,
    proposedEdits,
    sendMessage,
    authorize,
    reject,
    decideFile,
  }
}
