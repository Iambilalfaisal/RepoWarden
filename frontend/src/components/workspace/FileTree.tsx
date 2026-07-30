import { useState } from "react"
import { ChevronRight, File, Folder, FolderOpen } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TreeNode } from "@/types"

interface FileTreeProps {
  tree: TreeNode
  activeFile: string | null
  onSelect: (path: string) => void
}

export function FileTree({ tree, activeFile, onSelect }: FileTreeProps) {
  return (
    <div className="flex h-full w-56 shrink-0 flex-col overflow-y-auto border-r bg-muted/30 p-2">
      <div className="truncate px-2 pb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {tree.name}
      </div>
      <nav className="flex flex-col gap-0.5">
        {(tree.children ?? []).map((child) => (
          <TreeRow
            key={child.name}
            node={child}
            path={child.name}
            depth={0}
            activeFile={activeFile}
            onSelect={onSelect}
          />
        ))}
      </nav>
    </div>
  )
}

interface TreeRowProps {
  node: TreeNode
  path: string
  depth: number
  activeFile: string | null
  onSelect: (path: string) => void
}

function TreeRow({ node, path, depth, activeFile, onSelect }: TreeRowProps) {
  const [expanded, setExpanded] = useState(depth < 1)
  const indent = { paddingLeft: `${depth * 14 + 8}px` }

  if (node.type === "file") {
    return (
      <button
        type="button"
        onClick={() => onSelect(path)}
        style={indent}
        className={cn(
          "flex items-center gap-1.5 rounded py-1 pr-2 text-left text-sm hover:bg-accent hover:text-accent-foreground",
          path === activeFile && "bg-accent font-medium text-accent-foreground",
        )}
      >
        <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate">{node.name}</span>
      </button>
    )
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        style={indent}
        className="flex w-full items-center gap-1 rounded py-1 pr-2 text-left text-sm hover:bg-accent hover:text-accent-foreground"
      >
        <ChevronRight
          className={cn("h-3.5 w-3.5 shrink-0 transition-transform", expanded && "rotate-90")}
        />
        {expanded ? (
          <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {expanded &&
        (node.children ?? []).map((child) => (
          <TreeRow
            key={child.name}
            node={child}
            path={`${path}/${child.name}`}
            depth={depth + 1}
            activeFile={activeFile}
            onSelect={onSelect}
          />
        ))}
    </div>
  )
}
