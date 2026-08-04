from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware
from langgraph.graph.state import CompiledStateGraph

from app.agents.editor.prompt import render_editor_prompt
from app.agents.editor.tools import write_file
from app.agents.guardrails import make_secret_guardrail
from app.agents.llm import build_llm
from app.agents.shared.filesystem import list_directory, read_file
from app.agents.shared.memory import recall_memory, save_memory
from app.core.memory_store import get_store
from app.core.mongo import get_checkpointer

# Every tool bound below resolves its per-request root_dir from
# RunnableConfig (via ToolRuntime) rather than closing over a directory, so
# this graph is identical for every request/directory and only needs to be
# compiled once — see app/agents/reviewer/agent.py for the full reasoning.


@lru_cache(maxsize=1)
def build_editor_agent() -> CompiledStateGraph:
    llm = build_llm()
    store = get_store()

    tools = [
        list_directory,
        read_file,
        write_file,
        recall_memory,
        save_memory,
    ]

    # See app/agents/reviewer/agent.py for why SummarizationMiddleware and
    # make_secret_guardrail() exist — same reasoning applies here.
    #
    # HumanInTheLoopMiddleware is the real authorization gate for each
    # individual write: it pauses the graph with a genuine interrupt()
    # before write_file executes, requiring an explicit approve/reject
    # decision (see app/api/routes.py's /chat/resume) rather than trusting a
    # message in the prompt. This is layered *inside* the Editor as a
    # second, finer-grained (per-file) gate — the first, coarser gate is
    # structural: the Reviewer this Editor is paired with has no write_file
    # tool bound at all, so it can't reach this point regardless of what
    # any prompt says.
    middleware = [
        SummarizationMiddleware(model=llm, trigger=("tokens", 6000), keep=("messages", 20)),
        make_secret_guardrail(),
        HumanInTheLoopMiddleware(interrupt_on={"write_file": {"allowed_decisions": ["approve", "reject"]}}),
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=render_editor_prompt(),
        middleware=middleware,
        checkpointer=get_checkpointer(),
        store=store,
    )
