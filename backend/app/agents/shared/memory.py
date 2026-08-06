from datetime import datetime, timezone

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field


def _namespace(runtime: ToolRuntime) -> tuple[str, ...]:
    return ("project_memory", runtime.config["configurable"]["root_dir"])

class MemoryInput(BaseModel):
    content: str | None = Field(
        default=None,
        description="save_memory only: a concise note to remember about this project for future sessions.",
    )
    query: str | None = Field(
        default=None,
        description="recall_memory only: optional text to filter remembered notes by.",
    )


@tool(
    "save_memory",
    args_schema=MemoryInput,
    description=(
        "Saves a short note to long-term memory about this project, so "
        "future review sessions on the same directory can recall it "
        "(e.g. a fix already applied, a known false positive, a "
        "recurring pattern worth flagging). Requires content. Read-only "
        "with respect to source files — does not modify any code."
    ),
)
async def save_memory(content: str | None = None, query: str | None = None, *, runtime: ToolRuntime) -> dict:
    if not content:
        return {"status": "error", "message": "content is required to save a memory."}
    key = datetime.now(timezone.utc).isoformat()
    await runtime.store.aput(_namespace(runtime), key, {"content": content})
    return {"status": "saved"}


@tool(
    "recall_memory",
    args_schema=MemoryInput,
    description=(
        "Recalls previously saved notes about this project from "
        "long-term memory. Always call this early when reviewing a "
        "project you may have seen before. query is optional. Read-only "
        "and always safe."
    ),
)
async def recall_memory(content: str | None = None, query: str | None = None, *, runtime: ToolRuntime) -> dict:
    items = await runtime.store.asearch(_namespace(runtime), query=query or None, limit=20)
    notes = [
        {"content": item.value.get("content"), "saved_at": item.created_at.isoformat()}
        for item in items
    ]
    return {"notes": notes}
