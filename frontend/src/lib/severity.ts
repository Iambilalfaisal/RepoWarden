import { AlertCircle, AlertOctagon, AlertTriangle, Info, type LucideIcon } from "lucide-react"
import type { Severity } from "@/types"

interface SeverityConfig {
  label: string
  icon: LucideIcon
  badgeVariant: "default" | "secondary" | "destructive" | "outline"
  border: string
  iconColor: string
}

export const SEVERITY_CONFIG: Record<Severity, SeverityConfig> = {
  critical: {
    label: "Critical",
    icon: AlertOctagon,
    badgeVariant: "destructive",
    border: "border-l-red-600",
    iconColor: "text-red-600",
  },
  high: {
    label: "High",
    icon: AlertTriangle,
    badgeVariant: "destructive",
    border: "border-l-orange-500",
    iconColor: "text-orange-500",
  },
  medium: {
    label: "Medium",
    icon: AlertCircle,
    badgeVariant: "secondary",
    border: "border-l-amber-500",
    iconColor: "text-amber-500",
  },
  low: {
    label: "Low",
    icon: Info,
    badgeVariant: "outline",
    border: "border-l-blue-400",
    iconColor: "text-blue-400",
  },
}

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"]
