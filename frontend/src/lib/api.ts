import type { ChatTurn, TreeNode } from "@/types"

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

async function apiGet<T>(path: string, params: Record<string, string>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}?${new URLSearchParams(params)}`)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function fetchTree(root: string): Promise<TreeNode> {
  return apiGet<TreeNode>("/api/workspace/tree", { root })
}

export function fetchFile(root: string, path: string): Promise<{ path: string; content: string }> {
  return apiGet("/api/workspace/file", { root, path })
}

export function fetchChatHistory(rootDir: string, threadId: string): Promise<ChatTurn[]> {
  return apiGet<ChatTurn[]>("/api/chat/history", { root_dir: rootDir, thread_id: threadId })
}

const THREAD_ID_PREFIX = "repowarden:thread:"

export function getOrCreateThreadId(rootDir: string): string {
  const key = THREAD_ID_PREFIX + rootDir
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}
