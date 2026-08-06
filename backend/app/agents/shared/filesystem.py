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


# Shared args_schema for all three filesystem tools, matching the same
# consolidation applied to agents/shared/memory.py. Each tool only reads
# the field(s) it actually uses; the rest stay unset. Trade-off accepted:
# each tool's LLM-facing schema now advertises fields it ignores (e.g.
# list_directory/read_file show "pattern"/"is_regex", search_code shows
# "path") — if tool-calling reliability regresses on weaker models, that's
# the first place to look.
class FilesystemInput(BaseModel):
    path: str | None = Field(
        default=None,
        description=(
            f"list_directory/read_file only: {PATH_FIELD_DESCRIPTION} "
            "For list_directory, use '.' for the root itself; defaults to "
            "'.' if omitted. Required for read_file."
        ),
    )
    pattern: str | None = Field(
        default=None,
        description="search_code only: text (or regex, if is_regex=true) to search for.",
    )
    is_regex: bool = Field(
        default=False, description="search_code only: treat pattern as a regular expression."
    )


@tool(
    "list_directory",
    args_schema=FilesystemInput,
    description=(
        "Lists the immediate contents (files and subdirectories) of a "
        "directory within the workspace, one level deep. Call again with "
        "a subdirectory path to go deeper. Read-only and always safe."
    ),
)
async def list_directory(
    path: str | None = None, pattern: str | None = None, is_regex: bool = False, *, runtime: ToolRuntime
) -> dict:
    path = path or "."
    try:
        entries = list_dir_shallow(_root(runtime), path)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"path": path, "entries": entries}


@tool(
    "read_file",
    args_schema=FilesystemInput,
    description=(
        "Reads the text content of a single file within the workspace. "
        "Requires path. Read-only and always safe. Always read a file "
        "before analyzing or proposing changes to it."
    ),
)
async def read_file(
    path: str | None = None, pattern: str | None = None, is_regex: bool = False, *, runtime: ToolRuntime
) -> dict:
    if not path:
        return {"error": "path is required to read a file."}
    try:
        content = read_text_file(_root(runtime), path, max_chars=MAX_READ_CHARS_FOR_LLM)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"path": path, "content": content}


@tool(
    "search_code",
    args_schema=FilesystemInput,
    description=(
        "Searches file contents across the whole workspace for a piece of "
        "text (or a regex, with is_regex=true) and returns matching "
        "file/line locations. Requires pattern. Use this before proposing "
        "a change to a shared function, class, or exported symbol, to "
        "check its 'blast radius' — every other place that references it "
        "— so a fix doesn't silently break a caller elsewhere. Read-only "
        "and always safe."
    ),
)
async def search_code(
    path: str | None = None, pattern: str | None = None, is_regex: bool = False, *, runtime: ToolRuntime
) -> dict:
    if not pattern:
        return {"error": "pattern is required to search code."}
    try:
        matches = search_files(_root(runtime), pattern, is_regex=is_regex)
    except FsSafetyError as exc:
        return {"error": str(exc)}
    return {"pattern": pattern, "matches": matches}
