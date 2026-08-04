from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.graph.state import CompiledStateGraph

from app.agents.guardrails import make_secret_guardrail
from app.agents.llm import build_llm
from app.agents.reviewer.analyzers import (
    code_quality_analyzer,
    performance_analyzer,
    security_analyzer,
)
from app.agents.reviewer.prompt import render_reviewer_prompt
from app.agents.reviewer.tools import propose_edit
from app.agents.shared.filesystem import list_directory, read_file, search_code
from app.agents.shared.memory import recall_memory, save_memory
from app.core.memory_store import get_store
from app.core.mongo import get_checkpointer

# The Reviewer and Editor are two separate agents (two separate compiled
# graphs), not one agent asked to police itself. The Reviewer's toolset
# structurally has no write_file at all, so it is physically incapable of
# modifying anything, no matter what a prompt says. The Editor
# (app/agents/editor/agent.py) is only ever constructed by routes.py after
# the user has clicked "Allow All" — so the authorization boundary is
# enforced by which agent gets invoked, not by an instruction the model has
# to keep honoring. Both share the same checkpointer + thread_id, so the
# Editor sees the Reviewer's plan in the persisted conversation with no
# extra hand-off plumbing.
#
# Every tool bound below resolves its per-request root_dir from
# RunnableConfig (via ToolRuntime, injected by the ToolNode at call time —
# see app/agents/shared/filesystem.py) rather than closing over a directory,
# so this graph is identical for every request/directory and only needs to
# be compiled once.


@lru_cache(maxsize=1)
def build_reviewer_agent() -> CompiledStateGraph:
    llm = build_llm()
    store = get_store()

    tools = [
        list_directory,
        read_file,
        search_code,
        security_analyzer,
        performance_analyzer,
        code_quality_analyzer,
        propose_edit,
        recall_memory,
        save_memory,
    ]

    # SummarizationMiddleware condenses everything older than the last 20
    # messages into one summary once the thread crosses ~6000 tokens, so a
    # long-running review doesn't grow the checkpointer's message list (and
    # therefore cost/latency) forever — reuses this same model, no separate
    # summarizer to configure. make_secret_guardrail() is the LLM-content
    # guardrail: it redacts secret-shaped tokens from tool results and the
    # model's own output, layered on top of (not instead of) fs_safety's
    # filesystem sandboxing, which stops secret *files* from being opened at
    # all but says nothing about a token that appears inside an allowed file.
    middleware = [
        SummarizationMiddleware(model=llm, trigger=("tokens", 6000), keep=("messages", 20)),
        make_secret_guardrail(),
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=render_reviewer_prompt(),
        middleware=middleware,
        checkpointer=get_checkpointer(),
        store=store,
    )
