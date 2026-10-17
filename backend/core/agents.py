from collections.abc import Mapping
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

MessageContent = str | list[str | dict]


def thread_config(thread_id: UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": str(thread_id)}}


def message_text(content: MessageContent) -> str:
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def last_reply_text(agent_state: Mapping[str, list[BaseMessage]]) -> str:
    for message in reversed(agent_state.get("messages", [])):
        if isinstance(message, AIMessage) and message.content:
            return message_text(message.content)
    return ""
