from langchain.tools import ToolRuntime, tool

from app.agents.shared.editing import FileEditInput, build_file_edit
from app.core.fs_safety import resolve_root

# Read-only preview: packages the model's own proposed rewrite into a
# diff-shaped FileEdit, but never persists it. Bound to the Reviewer so
# the user can see a real diff — line-by-line, like a GitHub PR — before
# ever authorizing anything. The Reviewer's own LLM turn composes the
# rewritten content itself; this tool has no LLM call of its own.


@tool(
    "propose_edit",
    args_schema=FileEditInput,
    description=(
        "Submits your own proposed full rewrite of a file as a preview "
        "diff — WITHOUT modifying anything on disk. Call this for every "
        "file named in your plan, passing the COMPLETE new file content "
        "you composed yourself in proposed_code (not a fragment) plus a "
        "plain-language explanation, so the user can review the real "
        "diff before deciding whether to authorize anything. Read-only "
        "and always safe."
    ),
)
async def propose_edit(
    path: str, explanation: str, proposed_code: str, *, runtime: ToolRuntime
) -> dict:
    root = resolve_root(runtime.config["configurable"]["root_dir"])
    edit = build_file_edit(root, path, explanation, proposed_code)
    return edit.model_dump()
