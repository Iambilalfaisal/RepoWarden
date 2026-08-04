import { Button } from "@/components/ui/button"
import { ShieldAlert } from "lucide-react"
import type { PlanSummary, Severity } from "@/types"

interface PermissionBarProps {
  onAllow: () => void
  onReject: () => void
  disabled?: boolean
  planSummary?: PlanSummary
}

const RISK_STYLES: Record<Severity, string> = {
  low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
}

export function PermissionBar({ onAllow, onReject, disabled, planSummary }: PermissionBarProps) {
  return (
    <div className="animate-in slide-in-from-bottom-2 fade-in flex flex-col gap-2 border-t border-amber-300/60 bg-amber-50 px-4 py-3 duration-200 dark:border-amber-800/60 dark:bg-amber-950/40">
      {planSummary && (
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`rounded px-1.5 py-0.5 font-medium uppercase tracking-wide ${RISK_STYLES[planSummary.overall_risk]}`}
          >
            {planSummary.overall_risk} risk
          </span>
          <span className="text-amber-900/80 dark:text-amber-200/80">{planSummary.headline}</span>
          <span className="text-amber-800/60 dark:text-amber-300/60">
            ({planSummary.files_affected.length} file
            {planSummary.files_affected.length === 1 ? "" : "s"})
          </span>
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-start gap-2 text-sm">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <div>
            <p className="font-medium text-amber-900 dark:text-amber-200">
              Authorization required
            </p>
            <p className="text-xs text-amber-800/80 dark:text-amber-300/80">
              RepoWarden proposed a plan above and is paused before it modifies any code.
            </p>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="outline" onClick={onReject} disabled={disabled}>
            Reject
          </Button>
          <Button
            size="sm"
            onClick={onAllow}
            disabled={disabled}
            className="bg-amber-600 text-white hover:bg-amber-700"
          >
            Allow All
          </Button>
        </div>
      </div>
    </div>
  )
}
