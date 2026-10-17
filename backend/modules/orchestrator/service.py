from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID

from deepagents import create_deep_agent
from langchain_core.messages import (
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables.schema import StreamEvent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from contracts.auth import CurrentUser
from contracts.chat import ChatRequest, ChatResponse, ChatStreamEvent, PreparedChat
from core.agents import last_reply_text, message_text, thread_config
from core.logging_config import get_logger
from modules.orchestrator.errors import AgentProviderError
from modules.orchestrator.tools import (
    INITIATE_PAYMENTS_TOOL_NAME,
    build_initiate_payments_tool,
    extract_run_id,
)
from modules.prompts import get_prompt

if TYPE_CHECKING:
    from clients.files import FilesClient
    from clients.llm import LlmGatewayClient
    from clients.payments import PaymentsClient
    from clients.sessions import SessionsClient

logger = get_logger(__name__)

FILE_CONTEXT_PREAMBLE = "Attached file context for this request:"
STREAM_EVENTS_VERSION = "v2"


class OrchestratorService:
    def __init__(
        self,
        llm: "LlmGatewayClient",
        sessions: "SessionsClient",
        files: "FilesClient",
        payments: "PaymentsClient",
        agent_checkpointer: BaseCheckpointSaver | None,
    ) -> None:
        self._llm = llm
        self._sessions = sessions
        self._files = files
        self._payments = payments
        self._checkpointer = agent_checkpointer

    async def prepare(self, user: CurrentUser, request: ChatRequest) -> PreparedChat:
        session_id = await self._sessions.ensure_session(user, request.session_id)
        file_context = await self._file_context(user, request.file_ids)
        return PreparedChat(session_id=session_id, file_context=file_context)

    async def chat(self, user: CurrentUser, prepared: PreparedChat, message: str) -> ChatResponse:
        agent = self._build_agent(user, prepared.session_id)
        try:
            agent_state = await agent.ainvoke(
                {"messages": _input_messages(message, prepared.file_context)},
                config=thread_config(prepared.session_id),
            )
        except Exception as agent_error:
            logger.exception("chat_agent_failed", session_id=prepared.session_id)
            raise AgentProviderError from agent_error
        return ChatResponse(
            reply=last_reply_text(agent_state),
            session_id=prepared.session_id,
            payments_run_id=_scheduled_run_id(agent_state["messages"]),
        )

    async def stream_chat(
        self, user: CurrentUser, prepared: PreparedChat, message: str
    ) -> AsyncIterator[ChatStreamEvent]:
        agent = self._build_agent(user, prepared.session_id)
        try:
            async for event in agent.astream_events(
                {"messages": _input_messages(message, prepared.file_context)},
                thread_config(prepared.session_id),
                version=STREAM_EVENTS_VERSION,
            ):
                stream_event = _to_stream_event(event)
                if stream_event is not None:
                    yield stream_event
        except Exception:
            logger.exception("chat_stream_failed", session_id=prepared.session_id)
            yield ChatStreamEvent(type="error", data={"message": "agent stream failed"})
            return
        yield ChatStreamEvent(type="done", data={"session_id": str(prepared.session_id)})

    async def _file_context(self, user: CurrentUser, file_ids: list[UUID]) -> str:
        if not file_ids:
            return ""
        return await self._files.get_context(user, file_ids)

    def _build_agent(self, user: CurrentUser, session_id: UUID) -> CompiledStateGraph:
        initiate_payments = build_initiate_payments_tool(self._payments, user, session_id)
        return create_deep_agent(
            model=self._llm.model("main"),
            system_prompt=get_prompt("main_agent"),
            tools=[initiate_payments],
            checkpointer=self._checkpointer,
        )


def _input_messages(message: str, file_context: str) -> list[BaseMessage]:
    if not file_context:
        return [HumanMessage(content=message)]
    return [
        SystemMessage(content=f"{FILE_CONTEXT_PREAMBLE}\n{file_context}"),
        HumanMessage(content=message),
    ]


def _scheduled_run_id(messages: list[BaseMessage]) -> UUID | None:
    for message in reversed(messages):
        is_payments_tool_output = (
            isinstance(message, ToolMessage) and message.name == INITIATE_PAYMENTS_TOOL_NAME
        )
        if not is_payments_tool_output:
            continue
        run_id = extract_run_id(message_text(message.content))
        if run_id is not None:
            return run_id
    return None


def _to_stream_event(event: StreamEvent) -> ChatStreamEvent | None:
    event_kind = event["event"]
    is_payments_tool_event = event["name"] == INITIATE_PAYMENTS_TOOL_NAME
    if event_kind == "on_chat_model_stream":
        return _token_event(event["data"]["chunk"])
    if event_kind == "on_tool_start" and is_payments_tool_event:
        return ChatStreamEvent(type="tool_started", data={"tool": INITIATE_PAYMENTS_TOOL_NAME})
    if event_kind == "on_tool_end" and is_payments_tool_event:
        return _payments_scheduled_event(event["data"].get("output"))
    return None


def _token_event(chunk: object) -> ChatStreamEvent | None:
    if not isinstance(chunk, AIMessageChunk):
        return None
    text = message_text(chunk.content)
    if not text:
        return None
    return ChatStreamEvent(type="token", data={"text": text})


def _payments_scheduled_event(tool_output: object) -> ChatStreamEvent | None:
    if not isinstance(tool_output, ToolMessage):
        return None
    run_id = extract_run_id(message_text(tool_output.content))
    if run_id is None:
        return None
    return ChatStreamEvent(type="payments_scheduled", data={"run_id": str(run_id)})
