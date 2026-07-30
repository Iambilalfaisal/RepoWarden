from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.fs_safety import FsSafetyError, MAX_READ_CHARS_FOR_LLM, read_text_file, write_text_file
from app.tools.schemas import FileEdit

WRITE_FILE_SYSTEM_PROMPT = """You are a senior software engineer performing \
a safe, behavior-preserving edit to a single source file. Rewrite the full \
file content to address the given instructions while preserving existing \
behavior and public interfaces unless a fix specifically requires changing \
them. Return the COMPLETE new file content, not a fragment or diff. \
Explain what changed and why in plain language."""


class WriteFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root to edit.")
    instructions: str = Field(
        description=(
            "What to fix or improve in this file, drawn from prior findings "
            "and the agreed plan."
        )
    )


def make_write_file_tool(root: Path, llm: BaseChatModel) -> StructuredTool:
    """The one CODE-MODIFICATION tool — only ever bound to the Editor agent
    (see app/agent/orchestrator.py), which is itself only ever constructed
    after the user has authorized. Calling it both generates the new
    content and immediately persists it to disk; there's no separate
    propose/apply step."""

    structured_llm = llm.with_structured_output(FileEdit)

    async def _run(path: str, instructions: str) -> str:
        try:
            original_code = read_text_file(root, path, max_chars=MAX_READ_CHARS_FOR_LLM)
        except FsSafetyError as exc:
            return FileEdit(
                file_name=path,
                explanation=f"Could not read file: {exc}",
                original_code="",
                proposed_code="",
            ).model_dump_json()

        prompt = (
            f"File: {path}\n\n"
            f"Original code:\n```\n{original_code}\n```\n\n"
            f"Instructions:\n{instructions}\n\n"
            "Produce a FileEdit with the complete rewritten file content."
        )
        result = await structured_llm.ainvoke(
            [
                {"role": "system", "content": WRITE_FILE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        result.file_name = path
        result.original_code = original_code

        try:
            write_text_file(root, path, result.proposed_code)
        except FsSafetyError as exc:
            result.explanation = f"Generated the edit but could not write it: {exc}"
            result.proposed_code = original_code

        return result.model_dump_json()

    return StructuredTool.from_function(
        coroutine=_run,
        name="write_file",
        description=(
            "Rewrites a file on disk to implement a described change and "
            "immediately persists it. Returns the diff of what was written."
        ),
        args_schema=WriteFileInput,
    )
