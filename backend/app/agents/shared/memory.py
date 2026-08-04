from datetime import datetime, timezone

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field


def _namespace(runtime: ToolRuntime) -> tuple[str, ...]:
    return ("project_memory", runtime.config["configurable"]["root_dir"])


class SaveMemoryInput(BaseModel):
    content: str = Field(
        description="A concise note to remember about this project for future sessions."
    )


@tool(
    "save_memory",
    args_schema=SaveMemoryInput,
    description=(
        "Saves a short note to long-term memory about this project, so "
        "future review sessions on the same directory can recall it "
        "(e.g. a fix already applied, a known false positive, a "
        "recurring pattern worth flagging). Read-only with respect to "
        "source files — does not modify any code."
    ),
)
async def save_memory(content: str, *, runtime: ToolRuntime) -> dict:
    key = datetime.now(timezone.utc).isoformat()
    await runtime.store.aput(_namespace(runtime), key, {"content": content})
    return {"status": "saved"}


class RecallMemoryInput(BaseModel):
    query: str = Field(default="", description="Optional text to filter remembered notes by.")


@tool(
    "recall_memory",
    args_schema=RecallMemoryInput,
    description=(
        "Recalls previously saved notes about this project from "
        "long-term memory. Always call this early when reviewing a "
        "project you may have seen before. Read-only and always safe."
    ),
)
async def recall_memory(query: str = "", *, runtime: ToolRuntime) -> dict:
    items = await runtime.store.asearch(_namespace(runtime), query=query or None, limit=20)
    notes = [
        {"content": item.value.get("content"), "saved_at": item.created_at.isoformat()}
        for item in items
    ]
    return {"notes": notes}
