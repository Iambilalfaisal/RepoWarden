from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import ConfigurableField
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from app.agent.memory_store import get_store
from app.agent.rules import CLEAN_CODE_RULES
from app.core.config import settings
from app.core.fs_safety import resolve_root
from app.core.mongo import get_checkpointer
from app.tools.analyzers import (
    make_performance_analyzer_tool,
    make_quality_analyzer_tool,
    make_security_analyzer_tool,
)
from app.tools.filesystem import make_list_directory_tool, make_read_file_tool
from app.tools.memory import make_recall_memory_tool, make_save_memory_tool
from app.tools.write_file import make_write_file_tool

# The Reviewer and Editor are two separate agents (two separate compiled
# graphs), not one agent asked to police itself. The Reviewer's toolset
# structurally has no write_file at all, so it is physically incapable of
# modifying anything, no matter what a prompt says. The Editor is only ever
# constructed by routes.py after the user has clicked "Allow All" — so the
# authorization boundary is enforced by which agent gets invoked, not by an
# instruction the model has to keep honoring. Both share the same
# checkpointer + thread_id, so the Editor sees the Reviewer's plan in the
# persisted conversation with no extra hand-off plumbing.
AUTHORIZATION_NOTICE = (
    "USER_AUTHORIZATION: GRANTED. The Editor agent is now implementing the "
    "plan described above."
)

REVIEWER_SYSTEM_PROMPT = f"""You are the RepoWarden Reviewer — a read-only \
code-review agent with access to a real directory on the user's machine. \
You cannot modify any file; you have no write tool. Your job is to find \
issues and propose a plan for a separate Editor agent to implement, once a \
human approves it.

Judge code quality against these rules:

{CLEAN_CODE_RULES}

You have six tools, all read-only and always safe to call:
- list_directory: lists one directory level at a time.
- read_file: always read a file before analyzing it — never assume its
  contents.
- security_analyzer: analyzes one file for security vulnerabilities.
- performance_analyzer: analyzes one file for performance issues.
- code_quality_analyzer: analyzes one file against the clean-code rules
  above.
- recall_memory: recalls notes saved about this project in a previous
  session.
- save_memory: saves a short note about this project for future sessions.

Workflow:
1. Call recall_memory first to see if you've reviewed this project before.
2. Explore with list_directory as needed — don't assume the directory
   structure.
3. Run security_analyzer, performance_analyzer, and code_quality_analyzer
   on the files relevant to the user's request.
4. Summarize findings and propose a concrete, specific PLAN: exactly which
   files should change and why, grounded in the rules and findings above.
5. Always stop after presenting the plan. State clearly that you are
   awaiting user authorization before any file is modified — you have no
   way to modify one even if asked to.
"""

EDITOR_SYSTEM_PROMPT = """You are the RepoWarden Editor — a code-modification \
agent with access to a real directory on the user's machine. A human has \
already reviewed and approved a plan (written by a separate Reviewer agent, \
visible earlier in this conversation) before you were invoked at all — you \
are only ever run after authorization, so do not ask for further permission.

You have five tools:
- list_directory / read_file: read-only, use them to re-check current file
  contents before editing if needed.
- write_file: rewrites a file and immediately persists it to disk.
- recall_memory / save_memory: notes about this project that persist across
  sessions.

Workflow:
1. Implement the plan exactly as approved — call write_file once per file
   it named, with instructions derived from the Reviewer's findings. Do not
   invent additional changes beyond what was approved.
2. After each write_file call, briefly report what changed in that file.
3. When done, call save_memory to record what you changed and why.
"""


def _build_llm() -> BaseChatModel:
    # Configurable model: the model name and temperature can be overridden
    # per-invocation via RunnableConfig (config={"configurable": {...}})
    # instead of being fixed at construction time.
    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    ).configurable_fields(
        model_name=ConfigurableField(
            id="model_name", name="Model", description="OpenRouter model slug to use"
        ),
        temperature=ConfigurableField(
            id="temperature", name="Temperature", description="Sampling temperature"
        ),
    )


def build_reviewer_agent(root_dir: str) -> CompiledStateGraph:
    root = resolve_root(root_dir)
    llm = _build_llm()
    store = get_store()

    tools = [
        make_list_directory_tool(root),
        make_read_file_tool(root),
        make_security_analyzer_tool(root, llm),
        make_performance_analyzer_tool(root, llm),
        make_quality_analyzer_tool(root, llm),
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


def build_editor_agent(root_dir: str) -> CompiledStateGraph:
    root = resolve_root(root_dir)
    llm = _build_llm()
    store = get_store()

    tools = [
        make_list_directory_tool(root),
        make_read_file_tool(root),
        make_write_file_tool(root, llm),
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
