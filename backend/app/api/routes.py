import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agents import build_editor_agent, build_reviewer_agent
from app.agents.reviewer.summary_chain import build_plan_summary_chain
from app.agents.shared.editing import build_file_edit
from app.core.chat_history import append_turn, get_turns
from app.core.fs_safety import FsSafetyError, build_tree, read_text_file, resolve_root

router = APIRouter()


# Request/response contracts — kept here rather than in a separate
# api/schemas.py, since this router is the only place that ever
# constructs or consumes them.
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    root_dir: str
    authorized: bool = False
    model: str | None = None
    temperature: float | None = None


class FileDecision(BaseModel):
    file_name: str
    type: Literal["approve", "reject"]
    message: str | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    root_dir: str
    decisions: list[FileDecision]


logger = logging.getLogger(__name__)

# Tools whose output should be surfaced to the UI as structured analysis
# results rather than a generic tool badge.
ANALYSIS_TOOLS = {"security_analyzer", "performance_analyzer", "code_quality_analyzer"}
PROPOSE_TOOL = "propose_edit"
WRITE_TOOL = "write_file"


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data)}


def _tool_output_to_dict(output: Any) -> dict[str, Any]:
    """Tool outputs arrive as JSON strings (see app/tools/*), but LangGraph
    may wrap them in a ToolMessage depending on version — unwrap defensively."""
    content = getattr(output, "content", output)
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"text": content}
    return {"text": str(content)}


def _render_transcript(analyses: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for a in analyses:
        lines.append(f"[{a.get('tool')}] {a.get('file_name')}: {a.get('summary')}")
        for f in a.get("findings", []):
            lines.append(f"  - ({f.get('severity')}) {f.get('title')}: {f.get('description')}")
    for p in proposals:
        lines.append(f"[proposed edit] {p.get('file_name')}: {p.get('explanation')}")
    return "\n".join(lines)


async def _summarize_plan(
    analyses: list[dict[str, Any]], proposals: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Best-effort: build_plan_summary_chain() already retries transient bad
    parses internally (see agents/reviewer/summary_chain.py). If every
    attempt still fails, this is a one-sentence risk headline, not the
    actual analysis/proposals — losing it isn't worth killing the whole SSE
    turn (and the real findings/diffs the user needs) over, so log it and
    let the caller skip the plan_summary event instead of erroring out."""
    transcript = _render_transcript(analyses, proposals)
    chain = build_plan_summary_chain()
    try:
        plan_summary = await chain.ainvoke({"transcript": transcript})
    except Exception:
        logger.exception("Plan summary generation failed after retries; skipping plan_summary event.")
        return None
    return plan_summary.model_dump()


def _pending_approvals(root: Path, hitl_request: dict[str, Any]) -> list[dict[str, Any]]:
    """Turns a pending HumanInTheLoopMiddleware interrupt's action_requests
    (each one a not-yet-executed write_file call) into the same FileEdit
    shape the UI already renders for edit_proposed, so the approval queue
    can show a real diff, not just a filename."""
    pending = []
    for action in hitl_request.get("action_requests", []):
        args = action["args"]
        edit = build_file_edit(root, args["path"], args["explanation"], args["proposed_code"])
        pending.append(edit.model_dump())
    return pending


def _build_config(thread_id: str, root_dir: str, model: str | None, temperature: float | None) -> dict[str, Any]:
    configurable: dict[str, Any] = {"thread_id": thread_id, "root_dir": root_dir}
    if model:
        configurable["model_name"] = model
    if temperature is not None:
        configurable["temperature"] = temperature
    return {"configurable": configurable}


@dataclass
class _TurnAccumulator:
    """Mutable state built up while dispatching one turn's astream_events,
    then read back by _finalize_turn once the stream ends."""

    final_text_parts: list[str] = field(default_factory=list)
    file_written: bool = False
    analyses: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)


async def _dispatch_event(event: dict[str, Any], acc: _TurnAccumulator) -> AsyncIterator[dict[str, str]]:
    """Turns one astream_events event into zero or more SSE frames,
    recording whatever _finalize_turn will need afterwards (streamed text,
    whether a file was written, analyses/proposals) into acc along the way."""
    kind = event.get("event")
    name = event.get("name")
    data = event.get("data", {})

    if kind == "on_tool_start":
        yield _sse("tool_start", {"tool": name, "input": data.get("input")})
        return

    if kind == "on_tool_end":
        payload = _tool_output_to_dict(data.get("output"))
        if name in ANALYSIS_TOOLS:
            acc.analyses.append({"tool": name, **payload})
            yield _sse("analysis_result", {"tool": name, **payload})
        elif name == PROPOSE_TOOL:
            acc.proposals.append(payload)
            yield _sse("edit_proposed", payload)
        elif name == WRITE_TOOL:
            acc.file_written = True
            yield _sse("file_written", payload)
        else:
            yield _sse("tool_end", {"tool": name, **payload})
        return

    if kind == "on_chat_model_stream":
        # Tool implementations (security/performance/quality/propose_edit/
        # write_file) make their own nested LLM calls for structured
        # output. Only forward tokens from the top-level orchestrator's own
        # conversational turn, not those nested calls.
        if event.get("metadata", {}).get("langgraph_node") != "model":
            return
        chunk = data.get("chunk")
        text = getattr(chunk, "content", "") if chunk else ""
        if text:
            acc.final_text_parts.append(text)
            yield _sse("token", {"text": text})


async def _finalize_turn(
    agent: CompiledStateGraph,
    config: dict[str, Any],
    root_dir: str,
    thread_id: str,
    acc: _TurnAccumulator,
    *,
    is_editor: bool,
) -> AsyncIterator[dict[str, str]]:
    """Runs once astream_events finishes for a turn: persists the durable
    transcript, then emits whichever terminal SSE event applies —
    approval_required, done, or plan_summary (best-effort) + awaiting_
    authorization."""
    # HumanInTheLoopMiddleware pauses the graph with a real interrupt()
    # before write_file executes (see app/agents/editor/agent.py) —
    # astream_events finishes normally rather than raising when that
    # happens, so a pending interrupt has to be checked for explicitly
    # after the loop, not caught as an error.
    state = await agent.aget_state(config)

    # Durable transcript write — deliberately independent of the
    # checkpointed graph state above, which SummarizationMiddleware can
    # (and does) collapse/replace once a thread grows past its token
    # trigger. See app/core/chat_history.py for why this can't be
    # reconstructed from aget_state() later.
    summary = "".join(acc.final_text_parts)
    await asyncio.to_thread(append_turn, thread_id, root_dir, "assistant", summary)

    if state.interrupts:
        hitl_request = state.interrupts[0].value
        pending = _pending_approvals(resolve_root(root_dir), hitl_request)
        yield _sse("approval_required", {"pending": pending})
        return

    if acc.file_written or is_editor:
        # Authorized turns are terminal whether or not a file ended up
        # being written (e.g. no changes were warranted).
        yield _sse("done", {"text": summary})
        return

    if acc.proposals:
        plan_summary = await _summarize_plan(acc.analyses, acc.proposals)
        if plan_summary is not None:
            yield _sse("plan_summary", plan_summary)
    yield _sse("awaiting_authorization", {"text": summary})


async def _stream_agent_events(
    agent: CompiledStateGraph,
    graph_input: Any,
    config: dict[str, Any],
    root_dir: str,
    *,
    is_editor: bool,
) -> AsyncIterator[dict[str, str]]:
    """Shared SSE loop for both a fresh turn (/chat) and a resume after
    per-file approval (/chat/resume) — both drive the same graph the same
    way and only differ in what they feed in as graph_input (a fresh
    {"messages": [...]} vs a Command(resume=...)). Event-by-event dispatch
    and post-loop finalization are split out into _dispatch_event/
    _finalize_turn above so this stays a thin orchestrator."""
    thread_id = config["configurable"]["thread_id"]
    acc = _TurnAccumulator()
    try:
        async for event in agent.astream_events(graph_input, version="v2", config=config):
            async for sse in _dispatch_event(event, acc):
                yield sse

        async for sse in _finalize_turn(agent, config, root_dir, thread_id, acc, is_editor=is_editor):
            yield sse

    except Exception as exc:  # noqa: BLE001 — surface any failure to the SSE client
        yield _sse("error", {"message": str(exc)})


@router.post("/chat")
async def chat(request: ChatRequest) -> EventSourceResponse:
    # The authorization gate is which AGENT gets invoked, not a prompt the
    # model has to keep honoring: the Reviewer has no write_file tool at
    # all, so it is structurally incapable of modifying anything. The
    # Editor is only ever constructed here, after the user has authorized.
    # Both agents are compiled once (see build_reviewer_agent/build_editor_
    # agent) — every tool resolves root_dir from this request's config, so
    # rebuilding per-request is no longer necessary.
    try:
        resolve_root(request.root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    agent = build_editor_agent() if request.authorized else build_reviewer_agent()

    config = _build_config(request.thread_id, request.root_dir, request.model, request.temperature)

    # Durable transcript write (app/core/chat_history.py) — separate from
    # the checkpointer below, which is mutable working state, not a log.
    await asyncio.to_thread(append_turn, request.thread_id, request.root_dir, "user", request.message)

    # Short-term memory: the checkpointer (keyed by thread_id, in config)
    # loads and persists the full message history itself — we only ever
    # append this turn's new message(s), never resend prior history.
    graph_input = {"messages": [HumanMessage(content=request.message)]}

    return EventSourceResponse(
        _stream_agent_events(agent, graph_input, config, request.root_dir, is_editor=request.authorized)
    )


@router.post("/chat/resume")
async def resume_chat(request: ResumeRequest) -> EventSourceResponse:
    """Resumes an Editor run paused on a per-file write_file approval (see
    HumanInTheLoopMiddleware in app/agents/editor/agent.py). Decisions must
    be reordered to match the pending interrupt's action_requests order —
    HumanInTheLoopMiddleware.after_model maps resume decisions to hanging
    tool calls positionally, not by name."""
    try:
        resolve_root(request.root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent = build_editor_agent()
    config = _build_config(request.thread_id, request.root_dir, None, None)

    state = await agent.aget_state(config)
    if not state.interrupts:
        raise HTTPException(status_code=409, detail="No pending approval for this thread.")

    hitl_request = state.interrupts[0].value
    by_file = {d.file_name: d for d in request.decisions}
    ordered_decisions: list[dict[str, Any]] = []
    for action in hitl_request.get("action_requests", []):
        path = action["args"]["path"]
        decision = by_file.get(path)
        if decision is None:
            raise HTTPException(status_code=400, detail=f"Missing decision for '{path}'.")
        if decision.type == "approve":
            ordered_decisions.append({"type": "approve"})
        else:
            payload: dict[str, Any] = {"type": "reject"}
            if decision.message:
                payload["message"] = decision.message
            ordered_decisions.append(payload)

    graph_input = Command(resume={"decisions": ordered_decisions})
    return EventSourceResponse(
        _stream_agent_events(agent, graph_input, config, request.root_dir, is_editor=True)
    )


@router.get("/chat/history")
async def chat_history(root_dir: str = Query(...), thread_id: str = Query(...)) -> list[ChatTurn]:
    """Hydrates the chat UI on load from this thread's durable transcript
    (app/core/chat_history.py) — NOT the checkpointer's live graph state.
    Only plain human/AI text is replayed — tool calls, findings, and diffs
    aren't recorded here, so that richer structure the frontend builds live
    from SSE events can't be reconstructed on reload."""
    try:
        resolve_root(root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    turns = await asyncio.to_thread(get_turns, thread_id)
    return [ChatTurn(role=t["role"], content=t["content"]) for t in turns]


@router.get("/workspace/tree")
async def get_tree(root: str = Query(...)) -> dict:
    try:
        return build_tree(resolve_root(root))
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspace/file")
async def get_file(root: str = Query(...), path: str = Query(...)) -> dict:
    try:
        content = read_text_file(resolve_root(root), path)
        return {"path": path, "content": content}
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
