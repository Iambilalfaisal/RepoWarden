from functools import lru_cache

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from app.core.config import settings


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """One pooled client for the process lifetime — pymongo.MongoClient is
    itself thread-safe and manages its own connection pool internally, so it
    should never be recreated per-request."""
    return MongoClient(settings.mongodb_uri)


@lru_cache(maxsize=1)
def get_checkpointer() -> MongoDBSaver:
    """Short-term memory: persists each conversation's message state, keyed
    by thread_id, so the client no longer needs to resend full history on
    every request — the graph loads/saves it via this checkpointer."""
    return MongoDBSaver(get_mongo_client(), db_name=settings.mongodb_db_name)
