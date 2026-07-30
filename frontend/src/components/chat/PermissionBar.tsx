import { Button } from "@/components/ui/button"
import { ShieldAlert } from "lucide-react"

interface PermissionBarProps {
  onAllow: () => void
  onReject: () => void
  disabled?: boolean
}

export function PermissionBar({ onAllow, onReject, disabled }: PermissionBarProps) {
  return (
    <div className="animate-in slide-in-from-bottom-2 fade-in flex items-center justify-between gap-3 border-t border-amber-300/60 bg-amber-50 px-4 py-3 duration-200 dark:border-amber-800/60 dark:bg-amber-950/40">
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
  )
}
