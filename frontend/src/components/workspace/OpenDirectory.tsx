import { useState, type KeyboardEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { FolderOpen } from "lucide-react"

interface OpenDirectoryProps {
  onOpen: (path: string) => void
  isOpening: boolean
  error: string | null
}

export function OpenDirectory({ onOpen, isOpening, error }: OpenDirectoryProps) {
  const [value, setValue] = useState("")

  const submit = () => {
    if (!value.trim() || isOpening) return
    onOpen(value.trim())
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submit()
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex w-full max-w-md flex-col gap-4 rounded-lg border p-6">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-sm font-semibold">Open a project directory</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          RepoWarden will browse and review files under this directory. Paste an absolute
          path on this machine, e.g. <code className="rounded bg-muted px-1">C:\Users\you\project</code>.
        </p>
        <div className="flex gap-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="C:\path\to\project"
            disabled={isOpening}
            autoFocus
          />
          <Button onClick={submit} disabled={isOpening || !value.trim()}>
            {isOpening ? "Opening..." : "Open"}
          </Button>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    </div>
  )
}
