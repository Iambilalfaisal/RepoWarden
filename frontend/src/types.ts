export type Role = "user" | "assistant"

export interface ChatTurn {
  role: Role
  content: string
}

export type Severity = "low" | "medium" | "high" | "critical"

export interface Finding {
  severity: Severity
  line: number | null
  title: string
  description: string
  suggested_fix: string | null
}

export type AnalyzerTool = "security_analyzer" | "performance_analyzer" | "code_quality_analyzer"

export interface AnalysisResult {
  tool: AnalyzerTool
  file_name: string
  summary: string
  findings: Finding[]
}

export interface FileEdit {
  file_name: string
  explanation: string
  original_code: string
  proposed_code: string
}

export interface PlanSummary {
  overall_risk: Severity
  files_affected: string[]
  headline: string
}

export interface ToolCallStatus {
  tool: string
  status: "running" | "done"
}

export interface ChatMessage {
  id: string
  role: Role
  content: string
  kind?: "authorization" | "rejection"
  toolCalls?: ToolCallStatus[]
  analyses?: AnalysisResult[]
  proposals?: FileEdit[]
  edits?: FileEdit[]
  planSummary?: PlanSummary
  streaming?: boolean
  startedAt?: number
}

export interface ChatRequestBody {
  message: string
  thread_id: string
  root_dir: string
  authorized: boolean
  model?: string
  temperature?: number
}

export interface FileDecision {
  file_name: string
  type: "approve" | "reject"
  message?: string
}

export interface ResumeRequestBody {
  thread_id: string
  root_dir: string
  decisions: FileDecision[]
}

export interface TreeNode {
  name: string
  type: "file" | "dir"
  children?: TreeNode[]
}
