from langchain.tools import ToolRuntime, tool

from app.agents.shared.editing import FileEditInput, build_file_edit
from app.core.fs_safety import FsSafetyError, resolve_root, write_text_file

# The one CODE-MODIFICATION tool — only ever bound to the Editor agent
# (see app/agents/editor/agent.py). The Editor's own LLM turn composes the
# complete new file content itself (no nested LLM call here); this tool's
# only job is the actual filesystem write.


@tool(
    "write_file",
    args_schema=FileEditInput,
    description=(
        "Rewrites a file on disk with the COMPLETE new content you "
        "composed yourself in proposed_code (not a fragment) and "
        "immediately persists it. Returns the diff of what was written."
    ),
)
async def write_file(
    path: str, explanation: str, proposed_code: str, *, runtime: ToolRuntime
) -> dict:
    root = resolve_root(runtime.config["configurable"]["root_dir"])
    edit = build_file_edit(root, path, explanation, proposed_code)
    try:
        write_text_file(root, path, edit.proposed_code)
    except FsSafetyError as exc:
        edit.explanation = f"Generated the edit but could not write it: {exc}"
        edit.proposed_code = edit.original_code
    return edit.model_dump()
