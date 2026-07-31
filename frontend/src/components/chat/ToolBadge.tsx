import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { TOOL_META } from "@/lib/tools"
import { CheckCircle2, Loader2 } from "lucide-react"

interface ToolBadgeProps {
  tool: string
  status: "running" | "done"
}

export function ToolBadge({ tool, status }: ToolBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 font-normal", status === "running" && "animate-pulse border-primary")}
    >
      {status === "running" ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <CheckCircle2 className="h-3 w-3 text-green-600" />
      )}
      {TOOL_META[tool]?.label ?? tool}
    </Badge>
  )
}
