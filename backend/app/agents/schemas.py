from typing import Literal

from pydantic import BaseModel

Severity = Literal["low", "medium", "high", "critical"]


class Finding(BaseModel):
    severity: Severity
    line: int | None = None
    title: str
    description: str
    suggested_fix: str | None = None


class AnalysisReport(BaseModel):
    file_name: str = ""
    summary: str
    findings: list[Finding]


class FileEdit(BaseModel):
    file_name: str
    explanation: str
    original_code: str
    proposed_code: str


class PlanSummary(BaseModel):
    overall_risk: Severity
    files_affected: list[str]
    headline: str
