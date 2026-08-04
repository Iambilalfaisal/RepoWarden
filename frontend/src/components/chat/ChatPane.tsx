import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { ShieldCheck, Sparkles, Zap } from "lucide-react"
import type { ChatMessage, FileEdit } from "@/types"
import { FileApprovalQueue } from "./FileApprovalQueue"
import { MessageBubble } from "./MessageBubble"
import { MessageInput } from "./MessageInput"
import { PermissionBar } from "./PermissionBar"

interface ChatPaneProps {
  messages: ChatMessage[]
  isHydrating: boolean
  isStreaming: boolean
  awaitingAuthorization: boolean
  pendingApprovals: FileEdit[]
  onSend: (text: string) => void
  onAllow: () => void
  onReject: () => void
  onDecideFile: (fileName: string, type: "approve" | "reject") => void
  onJumpToLine?: (fileName: string, line: number) => void
  onViewFile?: (fileName: string) => void
}

const SUGGESTED_PROMPTS = [
  { icon: ShieldCheck, text: "Review this project for security vulnerabilities" },
  { icon: Zap, text: "Review this project for performance issues" },
  { icon: Sparkles, text: "Explore the project and suggest fixes" },
]

export function ChatPane({
  messages,
  isHydrating,
  isStreaming,
  awaitingAuthorization,
  pendingApprovals,
  onSend,
  onAllow,
  onReject,
  onDecideFile,
  onJumpToLine,
  onViewFile,
}: ChatPaneProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col border-r">
      <div className="border-b px-4 py-3">
        <h1 className="text-sm font-semibold">RepoWarden</h1>
        <p className="text-xs text-muted-foreground">Code Evaluation Assistant</p>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-3 p-4">
          {isHydrating && (
            <p className="text-xs text-muted-foreground">Loading previous conversation...</p>
          )}
          {!isHydrating && messages.length === 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Ask RepoWarden to review this project — it can browse the directory
                itself.
              </p>
              <div className="flex flex-col gap-1.5">
                {SUGGESTED_PROMPTS.map(({ icon: Icon, text }) => (
                  <Button
                    key={text}
                    variant="outline"
                    size="sm"
                    className="justify-start gap-2 font-normal"
                    onClick={() => onSend(text)}
                  >
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    {text}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              onJumpToLine={onJumpToLine}
              onViewFile={onViewFile}
            />
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {pendingApprovals.length > 0 && (
        <FileApprovalQueue pending={pendingApprovals} onDecide={onDecideFile} disabled={isStreaming} />
      )}

      {awaitingAuthorization && (
        <PermissionBar
          onAllow={onAllow}
          onReject={onReject}
          disabled={isStreaming}
          planSummary={[...messages].reverse().find((m) => m.planSummary)?.planSummary}
        />
      )}

      <MessageInput
        onSend={onSend}
        disabled={isStreaming || awaitingAuthorization || pendingApprovals.length > 0 || isHydrating}
      />
    </div>
  )
}
