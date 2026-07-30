import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sse_starlette.sse import EventSourceResponse

from app.agent.orchestrator import AUTHORIZATION_NOTICE, build_editor_agent, build_reviewer_agent
from app.core.fs_safety import FsSafetyError, build_tree, read_text_file, resolve_root
from app.tools.schemas import ChatRequest, ChatTurn

router = APIRouter()

# Tools whose output should be surfaced to the UI as structured analysis
# results rather than a generic tool badge.
ANALYSIS_TOOLS = {"security_analyzer", "performance_analyzer", "code_quality_analyzer"}
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


def _build_config(request: ChatRequest) -> dict[str, Any]:
    configurable: dict[str, Any] = {"thread_id": request.thread_id}
    if request.model:
        configurable["model_name"] = request.model
    if request.temperature is not None:
        configurable["temperature"] = request.temperature
    return {"configurable": configurable}


@router.post("/chat")
async def chat(request: ChatRequest) -> EventSourceResponse:
    # The authorization gate is which AGENT gets invoked, not a prompt the
    # model has to keep honoring: the Reviewer has no write_file tool at
    # all, so it is structurally incapable of modifying anything. The
    # Editor is only ever constructed here, after the user has authorized.
    build_agent = build_editor_agent if request.authorized else build_reviewer_agent
    try:
        agent = build_agent(root_dir=request.root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = _build_config(request)

    # Short-term memory: the checkpointer (keyed by thread_id, in config)
    # loads and persists the full message history itself — we only ever
    # append this turn's new message(s), never resend prior history.
    messages: list[Any] = []
    if request.authorized:
        messages.append(SystemMessage(content=AUTHORIZATION_NOTICE))
    messages.append({"role": "user", "content": request.message})

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        final_text_parts: list[str] = []
        file_written = False
        try:
            async for event in agent.astream_events(
                {"messages": messages}, version="v2", config=config
            ):
                kind = event.get("event")
                name = event.get("name")
                data = event.get("data", {})

                if kind == "on_tool_start":
                    yield _sse("tool_start", {"tool": name, "input": data.get("input")})

                elif kind == "on_tool_end":
                    payload = _tool_output_to_dict(data.get("output"))
                    if name in ANALYSIS_TOOLS:
                        yield _sse("analysis_result", {"tool": name, **payload})
                    elif name == WRITE_TOOL:
                        file_written = True
                        yield _sse("file_written", payload)
                    else:
                        yield _sse("tool_end", {"tool": name, **payload})

                elif kind == "on_chat_model_stream":
                    # Tool implementations (security/performance/write_file)
                    # make their own nested LLM calls for structured output.
                    # Only forward tokens from the top-level orchestrator's
                    # own conversational turn, not those nested calls.
                    if event.get("metadata", {}).get("langgraph_node") != "model":
                        continue
                    chunk = data.get("chunk")
                    text = getattr(chunk, "content", "") if chunk else ""
                    if text:
                        final_text_parts.append(text)
                        yield _sse("token", {"text": text})

            summary = "".join(final_text_parts)
            if file_written or request.authorized:
                # Authorized turns are terminal whether or not a file ended
                # up being written (e.g. no changes were warranted).
                yield _sse("done", {"text": summary})
            else:
                yield _sse("awaiting_authorization", {"text": summary})

        except Exception as exc:  # noqa: BLE001 — surface any failure to the SSE client
            yield _sse("error", {"message": str(exc)})

    return EventSourceResponse(event_stream())


@router.get("/chat/history")
async def chat_history(root_dir: str = Query(...), thread_id: str = Query(...)) -> list[ChatTurn]:
    """Hydrates the chat UI on load from the checkpointer's persisted state
    for this thread. Only plain human/AI text is replayed — tool calls,
    findings, and diffs aren't part of the persisted LangChain messages, so
    that richer structure the frontend builds live from SSE events can't be
    reconstructed here."""
    try:
        # Either agent can read the shared checkpointed state — which one
        # we construct here doesn't affect what's returned.
        agent = build_reviewer_agent(root_dir=root_dir)
    except FsSafetyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
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
