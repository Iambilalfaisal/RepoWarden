from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from app.agents.editor.prompt import EDITOR_SYSTEM_PROMPT
from app.agents.editor.tools import make_write_file_tool
from app.agents.llm import build_llm
from app.agents.shared.filesystem import make_list_directory_tool, make_read_file_tool
from app.agents.shared.memory import make_recall_memory_tool, make_save_memory_tool
from app.core.fs_safety import resolve_root
from app.core.memory_store import get_store
from app.core.mongo import get_checkpointer


def build_editor_agent(root_dir: str) -> CompiledStateGraph:
    root = resolve_root(root_dir)
    llm = build_llm()
    store = get_store()

    tools = [
        make_list_directory_tool(root),
        make_read_file_tool(root),
        make_write_file_tool(root),
        make_recall_memory_tool(store, root_dir),
        make_save_memory_tool(store, root_dir),
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=EDITOR_SYSTEM_PROMPT,
        checkpointer=get_checkpointer(),
        store=store,
    )
