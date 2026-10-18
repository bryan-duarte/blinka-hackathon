import json
from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from contracts.payments import TraceMessage, TraceRole, TraceToolCall
from core.agents import message_text

TRACE_ROLE_BY_MESSAGE_TYPE: dict[type[BaseMessage], TraceRole] = {
    SystemMessage: TraceRole.SYSTEM,
    HumanMessage: TraceRole.HUMAN,
    AIMessage: TraceRole.AI,
    ToolMessage: TraceRole.TOOL,
}
CURRENT_SYSTEM_PROMPT_NOTICE = "Current system prompt (not stored with this run):"


def serialize_messages(messages: Sequence[object], system_prompt: str) -> list[TraceMessage]:
    known_messages = [message for message in messages if _trace_role(message) is not None]
    has_system_prompt = any(isinstance(message, SystemMessage) for message in known_messages)
    trace_messages = [] if has_system_prompt else [_system_prompt_message(system_prompt)]
    for message in known_messages:
        trace_messages.append(_trace_message(len(trace_messages), message))
    return trace_messages


def _trace_role(message: object) -> TraceRole | None:
    for message_type, role in TRACE_ROLE_BY_MESSAGE_TYPE.items():
        if isinstance(message, message_type):
            return role
    return None


def _system_prompt_message(system_prompt: str) -> TraceMessage:
    return TraceMessage(
        index=0,
        role=TraceRole.SYSTEM,
        text=f"{CURRENT_SYSTEM_PROMPT_NOTICE}\n\n{system_prompt}",
    )


def _trace_message(index: int, message: BaseMessage) -> TraceMessage:
    text = message_text(message.content)
    if isinstance(message, AIMessage):
        return TraceMessage(
            index=index,
            role=TraceRole.AI,
            text=text,
            tool_calls=[
                TraceToolCall(call_id=call["id"] or "", name=call["name"], args=call["args"])
                for call in message.tool_calls
            ],
        )
    if isinstance(message, ToolMessage):
        return TraceMessage(
            index=index,
            role=TraceRole.TOOL,
            text=text,
            tool_call_id=message.tool_call_id,
            tool_name=message.name,
            output_json=_parsed_output(text),
        )
    return TraceMessage(index=index, role=_trace_role(message) or TraceRole.HUMAN, text=text)


def _parsed_output(text: str) -> dict | list | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict | list) else None
