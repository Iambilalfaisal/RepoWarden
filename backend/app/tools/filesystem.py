import json
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.fs_safety import FsSafetyError, list_dir_shallow, read_text_file, MAX_READ_CHARS_FOR_LLM


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
