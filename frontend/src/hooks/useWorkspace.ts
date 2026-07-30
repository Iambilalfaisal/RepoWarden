import { useCallback, useEffect, useRef, useState } from "react"
import { fetchFile, fetchTree } from "@/lib/api"
import type { TreeNode } from "@/types"

export function useWorkspace() {
  const [rootDir, setRootDir] = useState<string | null>(null)
  const [tree, setTree] = useState<TreeNode | null>(null)
  const [openError, setOpenError] = useState<string | null>(null)
  const [isOpening, setIsOpening] = useState(false)

  const [activeFile, setActiveFile] = useState<string | null>(null)
  const [fileCache, setFileCache] = useState<Record<string, string>>({})
  const [isFileLoading, setIsFileLoading] = useState(false)
  const fetchTokenRef = useRef(0)

  const openRoot = useCallback(async (path: string) => {
    setIsOpening(true)
    setOpenError(null)
    try {
      const result = await fetchTree(path)
      setRootDir(path)
      setTree(result)
      setActiveFile(null)
      setFileCache({})
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : "Failed to open directory")
    } finally {
      setIsOpening(false)
    }
  }, [])

  const refreshTree = useCallback(async () => {
    if (!rootDir) return
    try {
      const result = await fetchTree(rootDir)
      setTree(result)
    } catch {
      // best-effort refresh; keep the stale tree rather than surfacing an error
    }
  }, [rootDir])

  useEffect(() => {
    if (!rootDir || !activeFile || activeFile in fileCache) return
    const token = ++fetchTokenRef.current
    setIsFileLoading(true)
    fetchFile(rootDir, activeFile)
      .then((res) => {
        if (fetchTokenRef.current !== token) return
        setFileCache((prev) => ({ ...prev, [activeFile]: res.content }))
      })
      .catch(() => {
        if (fetchTokenRef.current !== token) return
        setFileCache((prev) => ({ ...prev, [activeFile]: "// Failed to load file content" }))
      })
      .finally(() => {
        if (fetchTokenRef.current === token) setIsFileLoading(false)
      })
  }, [rootDir, activeFile, fileCache])

  const updateFileCache = useCallback((path: string, content: string) => {
    setFileCache((prev) => ({ ...prev, [path]: content }))
  }, [])

  return {
    rootDir,
    tree,
    openError,
    isOpening,
    openRoot,
    activeFile,
    setActiveFile,
    fileContent: activeFile ? (fileCache[activeFile] ?? null) : null,
    isFileLoading,
    updateFileCache,
    refreshTree,
  }
}
