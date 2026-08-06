from typing import Literal

from langchain_core.tools import StructuredTool, tool
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


def _make_report_tool(name: str, description: str) -> StructuredTool:
    """Every analyzer tool has the same shape: the Reviewer's own LLM turn
    does the actual analysis (it already has the file's content in context
    from read_file) and calls this tool with its findings — the tool itself
    just packages them into an AnalysisReport for the SSE layer to render.
    No nested LLM call, no re-reading the file — that's the point."""

    @tool(name, args_schema=AnalysisReport, description=description)
    async def _run(file_name: str, summary: str, findings: list[Finding]) -> dict:
        return AnalysisReport(
            file_name=file_name, summary=summary, findings=findings
        ).model_dump()

    return _run


security_analyzer = _make_report_tool(
    "security_analyzer",
    "Reports your own security analysis of a file you've already read with "
    "read_file — always set file_name to the exact path you analyzed. "
    "Before calling this, look for concrete vulnerabilities: injection "
    "flaws, broken auth/authz, unsafe deserialization, hardcoded secrets, "
    "insecure crypto, SSRF, path traversal, and similar OWASP Top 10-class "
    "issues. Cite line numbers where possible. Do not invent issues that "
    "aren't actually present — an empty findings list is a valid, expected "
    "result for clean code.",
)

performance_analyzer = _make_report_tool(
    "performance_analyzer",
    "Reports your own performance analysis of a file you've already read "
    "with read_file — always set file_name to the exact path you "
    "analyzed. Before calling this, look for concrete issues: bad "
    "algorithmic complexity, N+1 query patterns, unnecessary allocations "
    "or copies, blocking I/O inside async code, missing caching/"
    "memoization, and similar. Cite line numbers where possible. Do not "
    "invent issues that aren't actually present — an empty findings list "
    "is a valid, expected result for efficient code.",
)

code_quality_analyzer = _make_report_tool(
    "code_quality_analyzer",
    "Reports your own clean-code analysis of a file you've already read "
    "with read_file — always set file_name to the exact path you "
    "analyzed. Judge it strictly against the clean-code rules in your "
    "system prompt. Cite line numbers where possible. Do not invent "
    "issues that aren't actually present — an empty findings list is a "
    "valid, expected result for already-clean code. Do not flag security "
    "or performance issues here; those belong to the other analyzer "
    "tools.",
)
