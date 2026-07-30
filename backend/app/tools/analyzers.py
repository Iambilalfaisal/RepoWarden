from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agent.rules import CLEAN_CODE_RULES
from app.core.fs_safety import FsSafetyError, MAX_READ_CHARS_FOR_LLM, read_text_file
from app.tools.schemas import AnalysisReport

SECURITY_PROMPT = """You are a senior application security engineer \
reviewing a single source file. Identify concrete security vulnerabilities: \
injection flaws, broken auth/authz, unsafe deserialization, hardcoded \
secrets, insecure crypto, SSRF, path traversal, and similar OWASP Top \
10-class issues. Cite line numbers where possible. Do not invent issues \
that are not actually present in the code — an empty findings list is a \
valid and expected result for clean code."""

PERFORMANCE_PROMPT = """You are a senior performance engineer reviewing a \
single source file. Identify concrete performance issues: bad algorithmic \
complexity, N+1 query patterns, unnecessary allocations or copies, \
blocking I/O inside async code, missing caching/memoization, and similar. \
Cite line numbers where possible. Do not invent issues that are not \
actually present in the code — an empty findings list is a valid and \
expected result for efficient code."""

QUALITY_PROMPT = f"""You are a senior software engineer reviewing a single \
source file for clean-code quality — not security or performance. Judge it \
strictly against the following rules:

{CLEAN_CODE_RULES}

Cite line numbers where possible. Do not invent issues that aren't \
actually present — an empty findings list is a valid and expected result \
for already-clean code. Do not flag security or performance issues here; \
those are covered by other reviewers."""


class AnalyzerInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root to analyze.")
    focus: str = Field(default="", description="Optional hint about what to focus the review on.")


def _make_analyzer_tool(
    name: str, description: str, system_prompt: str, root: Path, llm: BaseChatModel
) -> StructuredTool:
    # function_calling routes structured output through the same tool-calling
    # path every model here already has to support to use this agent at all —
    # broader OpenRouter-model compatibility than the default json_schema
    # mode, which several providers don't implement faithfully (some just
    # return prose instead of the requested schema).
    structured_llm = llm.with_structured_output(AnalysisReport, method="function_calling")

    async def _run(path: str, focus: str = "") -> str:
        try:
            code = read_text_file(root, path, max_chars=MAX_READ_CHARS_FOR_LLM)
        except FsSafetyError as exc:
            return AnalysisReport(
                file_name=path, summary=f"Could not read file: {exc}", findings=[]
            ).model_dump_json()

        prompt = (
            f"File: {path}\n\n```\n{code}\n```\n\n"
            + (f"Focus area: {focus}\n\n" if focus else "")
            + "Produce an AnalysisReport for this file. Where a finding has a "
            "clear, concrete fix, include it as a short code snippet in "
            "suggested_fix — leave it null if the fix genuinely needs more "
            "context or a design decision first."
        )
        result = await structured_llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        if result is None:
            # The model responded without actually calling the structured
            # output function — happens occasionally even in function_calling
            # mode with smaller models. Fail this one analysis gracefully
            # rather than crashing the whole agent turn.
            return AnalysisReport(
                file_name=path,
                summary="The model did not return a valid analysis for this file — try again.",
                findings=[],
            ).model_dump_json()
        result.file_name = path
        return result.model_dump_json()

    return StructuredTool.from_function(
        coroutine=_run, name=name, description=description, args_schema=AnalyzerInput
    )


def make_security_analyzer_tool(root: Path, llm: BaseChatModel) -> StructuredTool:
    return _make_analyzer_tool(
        "security_analyzer",
        "Reads and analyzes a file (given its path) for security vulnerabilities, "
        "returning a structured AnalysisReport. Read-only and always safe to call "
        "— does not modify any file.",
        SECURITY_PROMPT,
        root,
        llm,
    )


def make_performance_analyzer_tool(root: Path, llm: BaseChatModel) -> StructuredTool:
    return _make_analyzer_tool(
        "performance_analyzer",
        "Reads and analyzes a file (given its path) for performance issues, "
        "returning a structured AnalysisReport. Read-only and always safe to call "
        "— does not modify any file.",
        PERFORMANCE_PROMPT,
        root,
        llm,
    )


def make_quality_analyzer_tool(root: Path, llm: BaseChatModel) -> StructuredTool:
    return _make_analyzer_tool(
        "code_quality_analyzer",
        "Reads and analyzes a file (given its path) against clean-code best "
        "practices (naming, structure, duplication, complexity, dead code, etc.), "
        "returning a structured AnalysisReport. Read-only and always safe to call "
        "— does not modify any file.",
        QUALITY_PROMPT,
        root,
        llm,
    )
