from pathlib import Path

from langchain_core.tools import StructuredTool, tool

from app.agents.shared.editing import FileEditInput, build_file_edit
from app.core.fs_safety import FsSafetyError, write_text_file


def make_write_file_tool(root: Path) -> StructuredTool:
    """The one CODE-MODIFICATION tool — only ever bound to the Editor agent
    (see app/agents/editor/agent.py), which is itself only ever constructed
    after the user has authorized. The Editor's own LLM turn composes the
    complete new file content itself (no nested LLM call here); this tool's
    only job is the actual filesystem write."""

    @tool(
        "write_file",
        args_schema=FileEditInput,
        description=(
            "Rewrites a file on disk with the COMPLETE new content you "
            "composed yourself in proposed_code (not a fragment) and "
            "immediately persists it. Returns the diff of what was written."
        ),
    )
    async def _run(path: str, explanation: str, proposed_code: str) -> dict:
        edit = build_file_edit(root, path, explanation, proposed_code)
        try:
            write_text_file(root, path, edit.proposed_code)
        except FsSafetyError as exc:
            edit.explanation = f"Generated the edit but could not write it: {exc}"
            edit.proposed_code = edit.original_code
        return edit.model_dump()

    return _run
