from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    root_dir: str
    authorized: bool = False
    model: str | None = None
    temperature: float | None = None


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
