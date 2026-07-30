import { SEVERITY_CONFIG, SEVERITY_ORDER } from "@/lib/severity"
import type { AnalysisResult } from "@/types"
import { cn } from "@/lib/utils"

export function FindingsSummary({ analyses }: { analyses: AnalysisResult[] }) {
  const counts = analyses
    .flatMap((a) => a.findings)
    .reduce<Record<string, number>>((acc, f) => {
      acc[f.severity] = (acc[f.severity] ?? 0) + 1
      return acc
    }, {})

  const total = Object.values(counts).reduce((a, b) => a + b, 0)

  if (total === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No issues found across {analyses.length} check{analyses.length === 1 ? "" : "s"}.
      </p>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="font-medium text-muted-foreground">
        {total} finding{total === 1 ? "" : "s"}
      </span>
      {SEVERITY_ORDER.filter((s) => counts[s]).map((s) => {
        const cfg = SEVERITY_CONFIG[s]
        const Icon = cfg.icon
        return (
          <span
            key={s}
            className={cn("flex items-center gap-1 rounded-full border px-2 py-0.5", cfg.border, "border-l-2")}
          >
            <Icon className={cn("h-3 w-3", cfg.iconColor)} />
            {counts[s]} {cfg.label}
          </span>
        )
      })}
    </div>
  )
}
