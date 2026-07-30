import json
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.fs_safety import (
    FsSafetyError,
    MAX_READ_CHARS_FOR_LLM,
    list_dir_shallow,
    read_text_file,
    search_files,
)


class ListDirectoryInput(BaseModel):
    path: str = Field(
        default=".",
        description="Directory path relative to the workspace root. Use '.' for the root itself.",
    )


def make_list_directory_tool(root: Path) -> StructuredTool:
    async def _run(path: str = ".") -> str:
        try:
            entries = list_dir_shallow(root, path)
        except FsSafetyError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"path": path, "entries": entries})

    return StructuredTool.from_function(
        coroutine=_run,
        name="list_directory",
        description=(
            "Lists the immediate contents (files and subdirectories) of a "
            "directory within the workspace, one level deep. Call again with "
            "a subdirectory path to go deeper. Read-only and always safe."
        ),
        args_schema=ListDirectoryInput,
    )


class ReadFileInput(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")


def make_read_file_tool(root: Path) -> StructuredTool:
    async def _run(path: str) -> str:
        try:
            content = read_text_file(root, path, max_chars=MAX_READ_CHARS_FOR_LLM)
        except FsSafetyError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"path": path, "content": content})

    return StructuredTool.from_function(
        coroutine=_run,
        name="read_file",
        description=(
            "Reads the text content of a single file within the workspace. "
            "Read-only and always safe. Always read a file before analyzing "
            "or proposing changes to it."
        ),
        args_schema=ReadFileInput,
    )


class SearchCodeInput(BaseModel):
    pattern: str = Field(description="Text (or regex, if is_regex=true) to search for.")
    is_regex: bool = Field(default=False, description="Treat pattern as a regular expression.")


def make_search_code_tool(root: Path) -> StructuredTool:
    async def _run(pattern: str, is_regex: bool = False) -> str:
        try:
            matches = search_files(root, pattern, is_regex=is_regex)
        except FsSafetyError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"pattern": pattern, "matches": matches})

    return StructuredTool.from_function(
        coroutine=_run,
        name="search_code",
        description=(
            "Searches file contents across the whole workspace for a piece of "
            "text (or a regex, with is_regex=true) and returns matching "
            "file/line locations. Use this before proposing a change to a "
            "shared function, class, or exported symbol, to check its "
            "'blast radius' — every other place that references it — so a "
            "fix doesn't silently break a caller elsewhere. Read-only and "
            "always safe."
        ),
        args_schema=SearchCodeInput,
    )
