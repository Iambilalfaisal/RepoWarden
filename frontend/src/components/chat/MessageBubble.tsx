import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { SEVERITY_CONFIG } from "@/lib/severity"
import { TOOL_META } from "@/lib/tools"
import type { ChatMessage } from "@/types"
import { FindingsSummary } from "./FindingsSummary"
import { ToolBadge } from "./ToolBadge"
import { CheckCircle2, ChevronRight, MapPin } from "lucide-react"

interface MessageBubbleProps {
  message: ChatMessage
  onJumpToLine?: (fileName: string, line: number) => void
  onViewFile?: (fileName: string) => void
}

export function MessageBubble({ message, onJumpToLine, onViewFile }: MessageBubbleProps) {
  if (message.kind === "authorization" || message.kind === "rejection") {
    return (
      <div className="flex justify-center py-1">
        <Badge variant={message.kind === "authorization" ? "default" : "outline"}>
          {message.kind === "authorization" ? "Changes authorized" : "Plan rejected"}
        </Badge>
      </div>
    )
  }

  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-2", isUser && "flex-row-reverse")}>
      <Avatar className="h-7 w-7 shrink-0">
        <AvatarFallback>{isUser ? "You" : "RW"}</AvatarFallback>
      </Avatar>
      <div className={cn("flex min-w-0 max-w-[85%] flex-col gap-2", isUser && "items-end")}>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.toolCalls.map((tc, i) => (
              <ToolBadge key={`${tc.tool}-${i}`} tool={tc.tool} status={tc.status} />
            ))}
          </div>
        )}

        {message.analyses && message.analyses.length > 0 && (
          <div className="w-full rounded-md border bg-card p-3 text-sm">
            <FindingsSummary analyses={message.analyses} />
            <div className="mt-3 flex flex-col gap-3">
              {message.analyses.map((a, ai) => {
                const meta = TOOL_META[a.tool]
                const Icon = meta.icon
                return (
                  <div key={ai}>
                    <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <Icon className="h-3.5 w-3.5" />
                      {meta.label}
                    </div>
                    {a.findings.length === 0 ? (
                      <p className="pl-5 text-xs italic text-muted-foreground">
                        No issues found.
                      </p>
                    ) : (
                      <ul className="flex flex-col gap-1.5">
                        {a.findings.map((f, fi) => {
                          const cfg = SEVERITY_CONFIG[f.severity]
                          const SevIcon = cfg.icon
                          return (
                            <li
                              key={fi}
                              className={cn("border-l-2 pl-2.5", cfg.border)}
                            >
                              <details className="group">
                                <summary className="flex cursor-pointer list-none items-start gap-1.5 py-0.5">
                                  <ChevronRight className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
                                  <SevIcon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", cfg.iconColor)} />
                                  <span className="min-w-0 flex-1 text-left font-medium">
                                    {f.title}
                                  </span>
                                  <Badge variant={cfg.badgeVariant} className="shrink-0">
                                    {cfg.label}
                                  </Badge>
                                </summary>
                                <div className="mt-1 flex flex-col gap-1.5 pl-[1.125rem] text-muted-foreground">
                                  <p>{f.description}</p>
                                  {f.suggested_fix && (
                                    <pre className="overflow-x-auto rounded bg-muted p-2 text-xs text-foreground">
                                      <code>{f.suggested_fix}</code>
                                    </pre>
                                  )}
                                  {f.line != null && (
                                    <button
                                      type="button"
                                      onClick={() => onJumpToLine?.(a.file_name, f.line as number)}
                                      className="flex w-fit items-center gap-1 text-xs text-foreground underline decoration-dotted underline-offset-2 hover:text-primary"
                                    >
                                      <MapPin className="h-3 w-3" />
                                      Line {f.line} in {a.file_name}
                                    </button>
                                  )}
                                </div>
                              </details>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {message.edits && message.edits.length > 0 && (
          <div className="flex w-full flex-col gap-1.5 rounded-md border bg-card p-3 text-sm">
            <p className="text-xs font-medium text-muted-foreground">
              {message.edits.length} file{message.edits.length === 1 ? "" : "s"} written
            </p>
            {message.edits.map((edit, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onViewFile?.(edit.file_name)}
                className="flex items-start gap-1.5 rounded border-l-2 border-l-green-500 pl-2.5 text-left hover:bg-accent"
              >
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-600" />
                <span>
                  <span className="font-medium underline decoration-dotted underline-offset-2">
                    {edit.file_name}
                  </span>
                  <br />
                  <span className="text-xs text-muted-foreground">{edit.explanation}</span>
                </span>
              </button>
            ))}
          </div>
        )}

        {message.content && (
          <div
            className={cn(
              "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
              isUser ? "bg-primary text-primary-foreground" : "bg-muted",
            )}
          >
            {message.content}
            {message.streaming && <span className="animate-pulse">▍</span>}
          </div>
        )}
      </div>
    </div>
  )
}
