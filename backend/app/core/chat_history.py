from datetime import datetime, timezone
from functools import lru_cache

from pymongo.collection import Collection

from app.core.config import settings
from app.core.mongo import get_mongo_client


@lru_cache(maxsize=1)
def get_chat_history_collection() -> Collection:
    """A plain, append-only transcript — every user/assistant turn gets its
    own document here, written directly by app/api/routes.py. This is
    deliberately separate from the LangGraph checkpointer's `checkpoints`
    collection (app/core/mongo.py): SummarizationMiddleware (see
    app/agents/*/agent.py) periodically replaces older checkpointed messages
    with a synthetic summary once a thread crosses its token trigger, so the
    checkpointer's state is mutable working memory, not a durable log — old
    turns silently disappear from it even though the conversation is still
    ongoing. Nothing here is ever rewritten or deleted, so this collection
    stays the source of truth for GET /api/chat/history regardless of how
    much the graph's own working state gets condensed."""
    db = get_mongo_client()[settings.mongodb_db_name]
    collection = db["chat_history"]
    collection.create_index([("thread_id", 1), ("created_at", 1)])
    return collection


def append_turn(thread_id: str, root_dir: str, role: str, content: str) -> None:
    if not content:
        return
    get_chat_history_collection().insert_one(
        {
            "thread_id": thread_id,
            "root_dir": root_dir,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_turns(thread_id: str) -> list[dict]:
    cursor = get_chat_history_collection().find(
        {"thread_id": thread_id}, sort=[("created_at", 1), ("_id", 1)]
    )
    return [{"role": doc["role"], "content": doc["content"]} for doc in cursor]
