from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from app.agents.llm import build_llm
from app.agents.reviewer.analyzers import (
    code_quality_analyzer,
    performance_analyzer,
    security_analyzer,
)
from app.agents.reviewer.prompt import REVIEWER_SYSTEM_PROMPT
from app.agents.reviewer.tools import make_propose_edit_tool
from app.agents.shared.filesystem import (
    make_list_directory_tool,
    make_read_file_tool,
    make_search_code_tool,
)
from app.agents.shared.memory import make_recall_memory_tool, make_save_memory_tool
from app.core.fs_safety import resolve_root
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


def build_reviewer_agent(root_dir: str) -> CompiledStateGraph:
    root = resolve_root(root_dir)
    llm = build_llm()
    store = get_store()

    tools = [
        make_list_directory_tool(root),
        make_read_file_tool(root),
        make_search_code_tool(root),
        security_analyzer,
        performance_analyzer,
        code_quality_analyzer,
        make_propose_edit_tool(root),
        make_recall_memory_tool(store, root_dir),
        make_save_memory_tool(store, root_dir),
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        checkpointer=get_checkpointer(),
        store=store,
    )
