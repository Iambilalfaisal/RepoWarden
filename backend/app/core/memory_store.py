import asyncio
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)
from pymongo.collection import Collection

from app.core.config import settings
from app.core.mongo import get_mongo_client

NAMESPACE_SEP = "\x1f"


def _ns_str(namespace: tuple[str, ...]) -> str:
    return NAMESPACE_SEP.join(namespace)


class MongoDBStore(BaseStore):
    """Minimal LangGraph BaseStore backed by a MongoDB collection, used for
    long-term memory: notes the agent has learned about a project that
    should persist across separate conversations (separate checkpointer
    threads), not just within one.

    No official MongoDB Store implementation exists yet (only a checkpoint
    saver) — LangGraph's BaseStore only strictly requires batch/abatch, with
    get/put/search/delete implemented in terms of them, so this stays small:
    Get/Put/Search/ListNamespaces ops over one collection, no vector search.
    """

    def __init__(self, collection: Collection):
        self._collection = collection
        self._collection.create_index([("namespace_str", 1), ("key", 1)], unique=True)

    def _doc_to_item(self, doc: dict) -> Item:
        return Item(
            value=doc["value"],
            key=doc["key"],
            namespace=tuple(doc["namespace"]),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    def _doc_to_search_item(self, doc: dict) -> SearchItem:
        return SearchItem(
            namespace=tuple(doc["namespace"]),
            key=doc["key"],
            value=doc["value"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    def _run(self, op: Op) -> Any:
        if isinstance(op, GetOp):
            doc = self._collection.find_one({"namespace_str": _ns_str(op.namespace), "key": op.key})
            return self._doc_to_item(doc) if doc else None

        if isinstance(op, PutOp):
            filt = {"namespace_str": _ns_str(op.namespace), "key": op.key}
            if op.value is None:
                self._collection.delete_one(filt)
                return None
            now = datetime.now(timezone.utc)
            self._collection.update_one(
                filt,
                {
                    "$set": {"value": op.value, "namespace": list(op.namespace), "updated_at": now},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            return None

        if isinstance(op, SearchOp):
            prefix = _ns_str(op.namespace_prefix)
            query: dict[str, Any] = {"namespace_str": {"$regex": f"^{re.escape(prefix)}"}}
            if op.filter:
                for k, v in op.filter.items():
                    query[f"value.{k}"] = v
            if op.query:
                query["value.content"] = {"$regex": re.escape(op.query), "$options": "i"}
            cursor = self._collection.find(query).skip(op.offset).limit(op.limit)
            return [self._doc_to_search_item(d) for d in cursor]

        if isinstance(op, ListNamespacesOp):
            namespaces = self._collection.distinct("namespace_str")
            parsed = [tuple(n.split(NAMESPACE_SEP)) for n in namespaces]
            return parsed[op.offset : op.offset + op.limit]

        return None

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        return [self._run(op) for op in ops]

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return await asyncio.to_thread(self.batch, ops)


@lru_cache(maxsize=1)
def get_store() -> MongoDBStore:
    db = get_mongo_client()[settings.mongodb_db_name]
    return MongoDBStore(db["long_term_memory"])
