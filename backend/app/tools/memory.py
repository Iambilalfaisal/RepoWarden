import json
from datetime import datetime, timezone

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agent.memory_store import MongoDBStore


def _namespace(root_dir: str) -> tuple[str, ...]:
    return ("project_memory", root_dir)


class SaveMemoryInput(BaseModel):
    content: str = Field(
        description="A concise note to remember about this project for future sessions."
    )


def make_save_memory_tool(store: MongoDBStore, root_dir: str) -> StructuredTool:
    async def _run(content: str) -> str:
        key = datetime.now(timezone.utc).isoformat()
        await store.aput(_namespace(root_dir), key, {"content": content})
        return json.dumps({"status": "saved"})

    return StructuredTool.from_function(
        coroutine=_run,
        name="save_memory",
        description=(
            "Saves a short note to long-term memory about this project, so "
            "future review sessions on the same directory can recall it "
            "(e.g. a fix already applied, a known false positive, a "
            "recurring pattern worth flagging). Read-only with respect to "
            "source files — does not modify any code."
        ),
        args_schema=SaveMemoryInput,
    )


class RecallMemoryInput(BaseModel):
    query: str = Field(default="", description="Optional text to filter remembered notes by.")


def make_recall_memory_tool(store: MongoDBStore, root_dir: str) -> StructuredTool:
    async def _run(query: str = "") -> str:
        items = await store.asearch(_namespace(root_dir), query=query or None, limit=20)
        notes = [
            {"content": item.value.get("content"), "saved_at": item.created_at.isoformat()}
            for item in items
        ]
        return json.dumps({"notes": notes})

    return StructuredTool.from_function(
        coroutine=_run,
        name="recall_memory",
        description=(
            "Recalls previously saved notes about this project from "
            "long-term memory. Always call this early when reviewing a "
            "project you may have seen before. Read-only and always safe."
        ),
        args_schema=RecallMemoryInput,
    )
