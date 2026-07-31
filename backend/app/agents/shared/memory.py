from datetime import datetime, timezone

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field

from app.core.memory_store import MongoDBStore


def _namespace(root_dir: str) -> tuple[str, ...]:
    return ("project_memory", root_dir)


class SaveMemoryInput(BaseModel):
    content: str = Field(
        description="A concise note to remember about this project for future sessions."
    )


def make_save_memory_tool(store: MongoDBStore, root_dir: str) -> StructuredTool:
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
    async def _run(content: str) -> dict:
        key = datetime.now(timezone.utc).isoformat()
        await store.aput(_namespace(root_dir), key, {"content": content})
        return {"status": "saved"}

    return _run


class RecallMemoryInput(BaseModel):
    query: str = Field(default="", description="Optional text to filter remembered notes by.")


def make_recall_memory_tool(store: MongoDBStore, root_dir: str) -> StructuredTool:
    @tool(
        "recall_memory",
        args_schema=RecallMemoryInput,
        description=(
            "Recalls previously saved notes about this project from "
            "long-term memory. Always call this early when reviewing a "
            "project you may have seen before. Read-only and always safe."
        ),
    )
    async def _run(query: str = "") -> dict:
        items = await store.asearch(_namespace(root_dir), query=query or None, limit=20)
        notes = [
            {"content": item.value.get("content"), "saved_at": item.created_at.isoformat()}
            for item in items
        ]
        return {"notes": notes}

    return _run
