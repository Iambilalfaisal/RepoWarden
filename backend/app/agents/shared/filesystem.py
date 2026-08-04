from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from app.core.fs_safety import (
    PATH_FIELD_DESCRIPTION,
    FsSafetyError,
    MAX_READ_CHARS_FOR_LLM,
    list_dir_shallow,
    read_text_file,
    resolve_root,
    search_files,
)


def _root(runtime: ToolRuntime):
    return resolve_root(runtime.config["configurable"]["root_dir"])


class ListDirectoryInput(BaseModel):
    path: str = Field(
        default=".",
        description=f"{PATH_FIELD_DESCRIPTION} Use '.' for the root itself.",
    )


@tool(
    "list_directory",
    args_schema=ListDirectoryInput,
    description=(
        "Lists the immediate contents (files and subdirectories) of a "
        "directory within the workspace, one level deep. Call again with "
        "a subdirectory path to go deeper. Read-only and always safe."
    ),
)
async def list_directory(path: str = ".", *, runtime: ToolRuntime) -> dict:
    try:
        entries = list_dir_shallow(_root(runtime), path)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"path": path, "entries": entries}


class ReadFileInput(BaseModel):
    path: str = Field(description=PATH_FIELD_DESCRIPTION)


@tool(
    "read_file",
    args_schema=ReadFileInput,
    description=(
        "Reads the text content of a single file within the workspace. "
        "Read-only and always safe. Always read a file before analyzing "
        "or proposing changes to it."
    ),
)
async def read_file(path: str, *, runtime: ToolRuntime) -> dict:
    try:
        content = read_text_file(_root(runtime), path, max_chars=MAX_READ_CHARS_FOR_LLM)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"path": path, "content": content}


class SearchCodeInput(BaseModel):
    pattern: str = Field(description="Text (or regex, if is_regex=true) to search for.")
    is_regex: bool = Field(default=False, description="Treat pattern as a regular expression.")


@tool(
    "search_code",
    args_schema=SearchCodeInput,
    description=(
        "Searches file contents across the whole workspace for a piece of "
        "text (or a regex, with is_regex=true) and returns matching "
        "file/line locations. Use this before proposing a change to a "
        "shared function, class, or exported symbol, to check its "
        "'blast radius' — every other place that references it — so a "
        "fix doesn't silently break a caller elsewhere. Read-only and "
        "always safe."
    ),
)
async def search_code(pattern: str, is_regex: bool = False, *, runtime: ToolRuntime) -> dict:
    try:
        matches = search_files(_root(runtime), pattern, is_regex=is_regex)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"pattern": pattern, "matches": matches}
