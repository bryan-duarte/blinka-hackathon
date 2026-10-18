from uuid import UUID

from langchain_core.runnables import RunnableConfig

MessageContent = str | list[str | dict]


def thread_config(thread_id: UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": str(thread_id)}}


def message_text(content: MessageContent) -> str:
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
