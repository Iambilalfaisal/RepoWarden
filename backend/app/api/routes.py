import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from app.agents import build_editor_agent, build_reviewer_agent
from app.agents.reviewer.summary_chain import build_plan_summary_chain
from app.agents.shared.editing import build_file_edit
from app.api.schemas import ChatRequest, ChatTurn, ResumeRequest
from app.core.fs_safety import FsSafetyError, build_tree, read_text_file, resolve_root

router = APIRouter()

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
) -> dict[str, Any]:
    transcript = _render_transcript(analyses, proposals)
    chain = build_plan_summary_chain()
    plan_summary = await chain.ainvoke({"transcript": transcript})
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
    {"messages": [...]} vs a Command(resume=...))."""
    final_text_parts: list[str] = []
    file_written = False
    analyses: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    try:
        async for event in agent.astream_events(graph_input, version="v2", config=config):
            kind = event.get("event")
            name = event.get("name")
            data = event.get("data", {})

            if kind == "on_tool_start":
                yield _sse("tool_start", {"tool": name, "input": data.get("input")})

            elif kind == "on_tool_end":
                payload = _tool_output_to_dict(data.get("output"))
                if name in ANALYSIS_TOOLS:
                    analyses.append({"tool": name, **payload})
                    yield _sse("analysis_result", {"tool": name, **payload})
                elif name == PROPOSE_TOOL:
                    proposals.append(payload)
                    yield _sse("edit_proposed", payload)
                elif name == WRITE_TOOL:
                    file_written = True
                    yield _sse("file_written", payload)
                else:
                    yield _sse("tool_end", {"tool": name, **payload})

            elif kind == "on_chat_model_stream":
                # Tool implementations (security/performance/quality/
                # propose_edit/write_file) make their own nested LLM calls
                # for structured output. Only forward tokens from the
                # top-level orchestrator's own conversational turn, not
                # those nested calls.
                if event.get("metadata", {}).get("langgraph_node") != "model":
                    continue
                chunk = data.get("chunk")
                text = getattr(chunk, "content", "") if chunk else ""
                if text:
                    final_text_parts.append(text)
                    yield _sse("token", {"text": text})

        # HumanInTheLoopMiddleware pauses the graph with a real interrupt()
        # before write_file executes (see app/agents/editor/agent.py) —
        # astream_events finishes normally rather than raising when that
        # happens, so a pending interrupt has to be checked for explicitly
        # after the loop, not caught as an error.
        state = await agent.aget_state(config)
        if state.interrupts:
            hitl_request = state.interrupts[0].value
            pending = _pending_approvals(resolve_root(root_dir), hitl_request)
            yield _sse("approval_required", {"pending": pending})
            return

        summary = "".join(final_text_parts)
        if file_written or is_editor:
            # Authorized turns are terminal whether or not a file ended up
            # being written (e.g. no changes were warranted).
            yield _sse("done", {"text": summary})
        else:
            if proposals:
                plan_summary = await _summarize_plan(analyses, proposals)
                yield _sse("plan_summary", plan_summary)
            yield _sse("awaiting_authorization", {"text": summary})

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
    """Hydrates the chat UI on load from the checkpointer's persisted state
    for this thread. Only plain human/AI text is replayed — tool calls,
    findings, and diffs aren't part of the persisted LangChain messages, so
    that richer structure the frontend builds live from SSE events can't be
    reconstructed here."""
    try:
        resolve_root(root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Either agent can read the shared checkpointed state — which one we
    # reference here doesn't affect what's returned.
    agent = build_reviewer_agent()
    state = await agent.aget_state(
        {"configurable": {"thread_id": thread_id, "root_dir": root_dir}}
    )
    messages = state.values.get("messages", []) if state.values else []
    return [
        ChatTurn(role="user" if isinstance(m, HumanMessage) else "assistant", content=m.content)
        for m in messages
        if isinstance(m, (HumanMessage, AIMessage)) and isinstance(m.content, str) and m.content
    ]


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
