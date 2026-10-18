from time import monotonic

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.runnables.schema import StreamEvent
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from core.agents import message_text, thread_config
from modules.payments.agent_state import RunState
from modules.payments.agent_tools import STEP_TOOL_NAMES
from modules.payments.events import RunEventRecorder, ThinkingBuffer

PAYMENTS_AGENT_GRAPH_NAME = "payments"
PAYMENTS_MODEL_PROVIDER = "anthropic"
WRITE_TODOS_TOOL = "write_todos"
AGENT_RECURSION_LIMIT = 80
STREAM_EVENTS_VERSION = "v2"
AGENT_MODEL_NODE = "model"
MILLISECONDS_PER_SECOND = 1000
TOOL_ERROR_EVENT = "on_tool_error"
TOOL_END_EVENTS = frozenset({"on_tool_end", TOOL_ERROR_EVENT})
TOOL_ERROR_STATUS = "error"
FILESYSTEM_TOOL_NAMES = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"}
)
PAYMENTS_HARNESS_PROFILE = HarnessProfile(
    excluded_tools=FILESYSTEM_TOOL_NAMES,
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
)
PAYMENTS_AGENT_TOOL_NAMES = STEP_TOOL_NAMES | {WRITE_TODOS_TOOL}

register_harness_profile(PAYMENTS_MODEL_PROVIDER, PAYMENTS_HARNESS_PROFILE)


def build_payments_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver | None,
) -> CompiledStateGraph:
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[TodoListMiddleware()],
        checkpointer=checkpointer,
        name=PAYMENTS_AGENT_GRAPH_NAME,
    )


async def stream_agent(
    agent: CompiledStateGraph,
    state: RunState,
    events: RunEventRecorder,
    thinking_flush_seconds: float,
) -> None:
    thinking = ThinkingBuffer(events, thinking_flush_seconds)
    tool_started_at: dict[str, float] = {}
    final_text = ""
    config = {"recursion_limit": AGENT_RECURSION_LIMIT, **thread_config(state.run_id)}
    agent_input = {"messages": [HumanMessage(content=_task_message(state))]}
    async for event in agent.astream_events(agent_input, config, version=STREAM_EVENTS_VERSION):
        event_kind, event_name = event["event"], event["name"]
        is_agent_model_event = event["metadata"].get("langgraph_node") == AGENT_MODEL_NODE
        if event_kind == "on_chat_model_stream" and is_agent_model_event:
            await thinking.add(_chunk_text(event["data"]["chunk"]))
        elif event_kind == "on_chat_model_end" and is_agent_model_event:
            final_text = _final_reply_text(event) or final_text
        elif event_kind == "on_tool_start" and event_name == WRITE_TODOS_TOOL:
            await thinking.flush()
            await events.todos(event["data"]["input"].get("todos", []))
        elif event_kind == "on_tool_start" and event_name in STEP_TOOL_NAMES:
            await thinking.flush()
            tool_started_at[event["run_id"]] = monotonic()
            await events.tool_started(event_name, call_id=event["run_id"])
        elif event_kind in TOOL_END_EVENTS and event_name in STEP_TOOL_NAMES:
            started_at = tool_started_at.pop(event["run_id"], monotonic())
            await events.tool_finished(
                event_name,
                call_id=event["run_id"],
                output=_tool_output(event),
                duration_ms=round((monotonic() - started_at) * MILLISECONDS_PER_SECOND),
            )
    await thinking.flush()
    if final_text:
        await events.agent_summary(final_text)


def _task_message(state: RunState) -> str:
    source = state.source
    has_attachment = "yes" if source.file_id is not None else "no"
    return (
        "Process the document received for this payment run.\n"
        f"- bill_source_id: {source.source_id}\n"
        f"- channel: {source.source_type}\n"
        f"- sender: {source.sender}\n"
        f"- has_attachment: {has_attachment}"
    )


def _tool_output(event: StreamEvent) -> object:
    if event["event"] != TOOL_ERROR_EVENT:
        return event["data"].get("output")
    return ToolMessage(
        content=str(event["data"].get("error")),
        status=TOOL_ERROR_STATUS,
        tool_call_id=event["run_id"],
    )


def _chunk_text(chunk: object) -> str:
    if not isinstance(chunk, AIMessageChunk):
        return ""
    return message_text(chunk.content)


def _final_reply_text(event: StreamEvent) -> str:
    reply = event["data"].get("output")
    is_final_reply = isinstance(reply, AIMessage) and not reply.tool_calls
    if not is_final_reply:
        return ""
    return message_text(reply.content).strip()
