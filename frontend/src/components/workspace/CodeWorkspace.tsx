import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react"
import {
  DiffEditor,
  Editor,
  type DiffOnMount,
  type Monaco,
  type OnMount,
} from "@monaco-editor/react"
import type { editor as MonacoEditorNS } from "monaco-editor"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { FileEdit, TreeNode } from "@/types"
import { FileTree } from "./FileTree"

export interface CodeWorkspaceHandle {
  revealLine: (line: number) => void
}

interface CodeWorkspaceProps {
  tree: TreeNode
  activeFile: string | null
  onSelectFile: (file: string) => void
  fileContent: string | null
  isFileLoading: boolean
  writtenFiles: Record<string, FileEdit>
}

function languageForFile(name: string): string {
  if (name.endsWith(".ts") || name.endsWith(".tsx")) return "typescript"
  if (name.endsWith(".js") || name.endsWith(".jsx")) return "javascript"
  if (name.endsWith(".py")) return "python"
  if (name.endsWith(".json")) return "json"
  if (name.endsWith(".md")) return "markdown"
  return "plaintext"
}

function countLineChanges(changes: MonacoEditorNS.ILineChange[]) {
  let added = 0
  let removed = 0
  for (const c of changes) {
    if (c.originalEndLineNumber > 0) {
      removed += c.originalEndLineNumber - c.originalStartLineNumber + 1
    }
    if (c.modifiedEndLineNumber > 0) {
      added += c.modifiedEndLineNumber - c.modifiedStartLineNumber + 1
    }
  }
  return { added, removed }
}

export const CodeWorkspace = forwardRef<CodeWorkspaceHandle, CodeWorkspaceProps>(
  function CodeWorkspace(
    { tree, activeFile, onSelectFile, fileContent, isFileLoading, writtenFiles },
    ref,
  ) {
    const [showDiff, setShowDiff] = useState(true)
    const [diffStats, setDiffStats] = useState<{ added: number; removed: number } | null>(null)

    const edit = activeFile ? writtenFiles[activeFile] : undefined
    const language = languageForFile(activeFile ?? "")
    const displayDiff = Boolean(edit) && showDiff

    const editorRef = useRef<MonacoEditorNS.IStandaloneCodeEditor | null>(null)
    const monacoRef = useRef<Monaco | null>(null)
    const pendingLineRef = useRef<number | null>(null)
    const decorationIdsRef = useRef<string[]>([])

    useEffect(() => {
      setDiffStats(null)
    }, [edit])

    const revealAndHighlight = (line: number) => {
      const editorInst = editorRef.current
      const monacoNs = monacoRef.current
      if (!editorInst || !monacoNs) {
        pendingLineRef.current = line
        return
      }
      editorInst.revealLineInCenter(line)
      decorationIdsRef.current = editorInst.deltaDecorations(decorationIdsRef.current, [
        {
          range: new monacoNs.Range(line, 1, line, 1),
          options: { isWholeLine: true, className: "jump-highlight-line" },
        },
      ])
      window.setTimeout(() => {
        decorationIdsRef.current = editorInst.deltaDecorations(decorationIdsRef.current, [])
      }, 2000)
    }

    useImperativeHandle(ref, () => ({
      revealLine(line: number) {
        setShowDiff(false)
        revealAndHighlight(line)
      },
    }))

    const handleMount: OnMount = (editorInst, monacoNs) => {
      editorRef.current = editorInst
      monacoRef.current = monacoNs
      if (pendingLineRef.current != null) {
        const line = pendingLineRef.current
        pendingLineRef.current = null
        revealAndHighlight(line)
      }
    }

    const handleDiffMount: DiffOnMount = (diffEditor) => {
      const update = () => {
        const changes = diffEditor.getLineChanges()
        if (changes) setDiffStats(countLineChanges(changes))
      }
      update()
      diffEditor.onDidUpdateDiff(update)
    }

    return (
      <div className="flex h-full min-w-0 flex-1">
        <FileTree tree={tree} activeFile={activeFile} onSelect={onSelectFile} />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="truncate text-sm font-medium">
              {activeFile ?? "No file selected"}
            </span>
            {edit && (
              <div className="flex items-center gap-2">
                {displayDiff && diffStats && (
                  <span className="flex items-center gap-1 text-xs font-mono">
                    <Badge variant="outline" className="text-green-600">
                      +{diffStats.added}
                    </Badge>
                    <Badge variant="outline" className="text-red-600">
                      -{diffStats.removed}
                    </Badge>
                  </span>
                )}
                <Button
                  size="sm"
                  variant={showDiff ? "default" : "outline"}
                  onClick={() => setShowDiff(true)}
                >
                  Diff
                </Button>
                <Button
                  size="sm"
                  variant={!showDiff ? "default" : "outline"}
                  onClick={() => setShowDiff(false)}
                >
                  Source
                </Button>
              </div>
            )}
          </div>
          {displayDiff && edit?.explanation && (
            <p className="border-b bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              {edit.explanation}
            </p>
          )}
          <div className="min-h-0 flex-1">
            {!activeFile ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Select a file from the tree to view it.
              </div>
            ) : displayDiff && edit ? (
              <DiffEditor
                original={edit.original_code}
                modified={edit.proposed_code}
                language={language}
                theme="vs-dark"
                options={{ readOnly: true, minimap: { enabled: false } }}
                height="100%"
                onMount={handleDiffMount}
              />
            ) : isFileLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Loading...
              </div>
            ) : (
              <Editor
                value={fileContent ?? ""}
                language={language}
                theme="vs-dark"
                options={{ readOnly: true, minimap: { enabled: false }, fontSize: 13 }}
                height="100%"
                onMount={handleMount}
              />
            )}
          </div>
        </div>
      </div>
    )
  },
)
