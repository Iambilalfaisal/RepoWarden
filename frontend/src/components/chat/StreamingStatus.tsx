import { useEffect, useState } from "react"
import { TOOL_META } from "@/lib/tools"
import type { ToolCallStatus } from "@/types"

interface StreamingStatusProps {
  toolCalls?: ToolCallStatus[]
  hasContent: boolean
  startedAt: number
}

export function StreamingStatus({ toolCalls, hasContent, startedAt }: StreamingStatusProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(() =>
    Math.floor((Date.now() - startedAt) / 1000),
  )

  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    return () => window.clearInterval(id)
  }, [startedAt])

  const runningTool = toolCalls
    ? [...toolCalls].reverse().find((t) => t.status === "running")
    : undefined

  const label = runningTool
    ? `Running ${TOOL_META[runningTool.tool]?.label ?? runningTool.tool}...`
    : hasContent
      ? "Writing response..."
      : "Thinking..."

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
      </span>
      <span>{label}</span>
      <span className="tabular-nums">{elapsedSeconds}s</span>
    </div>
  )
}
