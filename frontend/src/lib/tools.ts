import {
  BrainCircuit,
  FilePenLine,
  FileSearch,
  FolderOpen,
  SearchCode,
  ShieldCheck,
  Sparkles,
  Zap,
  type LucideIcon,
} from "lucide-react"

interface ToolMeta {
  label: string
  icon: LucideIcon
}

export const TOOL_META: Record<string, ToolMeta> = {
  list_directory: { label: "Listing Directory", icon: FolderOpen },
  read_file: { label: "Reading File", icon: FileSearch },
  search_code: { label: "Searching Codebase", icon: SearchCode },
  security_analyzer: { label: "Security Analyzer", icon: ShieldCheck },
  performance_analyzer: { label: "Performance Analyzer", icon: Zap },
  code_quality_analyzer: { label: "Code Quality Analyzer", icon: Sparkles },
  recall_memory: { label: "Recalling Memory", icon: BrainCircuit },
  save_memory: { label: "Saving Memory", icon: BrainCircuit },
  write_file: { label: "Editing File", icon: FilePenLine },
}
