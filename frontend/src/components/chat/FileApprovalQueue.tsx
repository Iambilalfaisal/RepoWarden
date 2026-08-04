import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { FileCode2, ShieldQuestion } from "lucide-react"
import type { FileEdit } from "@/types"

interface FileApprovalQueueProps {
  pending: FileEdit[]
  onDecide: (fileName: string, type: "approve" | "reject") => void
  disabled?: boolean
}

// Surfaces each write_file call the Editor has individually paused on (a
// real LangGraph interrupt() per file — see HumanInTheLoopMiddleware in
// app/agents/editor/agent.py) so a human approves or rejects one file at a
// time, rather than one "Allow All" covering an entire multi-file plan.
export function FileApprovalQueue({ pending, onDecide, disabled }: FileApprovalQueueProps) {
  const [decided, setDecided] = useState<Record<string, "approve" | "reject">>({})

  useEffect(() => {
    setDecided({})
  }, [pending])

  return (
    <div className="animate-in slide-in-from-bottom-2 fade-in flex flex-col gap-2 border-t border-sky-300/60 bg-sky-50 px-4 py-3 duration-200 dark:border-sky-800/60 dark:bg-sky-950/40">
      <div className="flex items-start gap-2 text-sm">
        <ShieldQuestion className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
        <div>
          <p className="font-medium text-sky-900 dark:text-sky-200">
            {pending.length} file{pending.length === 1 ? "" : "s"} awaiting approval
          </p>
          <p className="text-xs text-sky-800/80 dark:text-sky-300/80">
            The Editor is paused before writing each file below — approve or reject each one.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        {pending.map((edit) => {
          const choice = decided[edit.file_name]
          return (
            <div
              key={edit.file_name}
              className="flex items-center justify-between gap-3 rounded border border-sky-200 bg-white px-2.5 py-1.5 text-xs dark:border-sky-900 dark:bg-sky-950/60"
            >
              <div className="flex min-w-0 items-center gap-1.5">
                <FileCode2 className="h-3.5 w-3.5 shrink-0 text-sky-600 dark:text-sky-400" />
                <span className="truncate font-mono">{edit.file_name}</span>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 px-2 text-xs"
                  disabled={disabled || !!choice}
                  onClick={() => {
                    setDecided((prev) => ({ ...prev, [edit.file_name]: "reject" }))
                    onDecide(edit.file_name, "reject")
                  }}
                >
                  {choice === "reject" ? "Rejected" : "Reject"}
                </Button>
                <Button
                  size="sm"
                  className="h-6 bg-sky-600 px-2 text-xs text-white hover:bg-sky-700"
                  disabled={disabled || !!choice}
                  onClick={() => {
                    setDecided((prev) => ({ ...prev, [edit.file_name]: "approve" }))
                    onDecide(edit.file_name, "approve")
                  }}
                >
                  {choice === "approve" ? "Approved" : "Approve"}
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
