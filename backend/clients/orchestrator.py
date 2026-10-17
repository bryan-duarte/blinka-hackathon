from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from contracts.auth import CurrentUser
from contracts.chat import ChatRequest, ChatResponse, ChatStreamEvent, PreparedChat

if TYPE_CHECKING:
    from modules.orchestrator.service import OrchestratorService


class OrchestratorClient:
    def __init__(self, service: "OrchestratorService") -> None:
        self._service = service

    async def prepare(self, user: CurrentUser, request: ChatRequest) -> PreparedChat:
        return await self._service.prepare(user, request)

    async def chat(self, user: CurrentUser, prepared: PreparedChat, message: str) -> ChatResponse:
        return await self._service.chat(user, prepared, message)

    def stream_chat(
        self, user: CurrentUser, prepared: PreparedChat, message: str
    ) -> AsyncIterator[ChatStreamEvent]:
        return self._service.stream_chat(user, prepared, message)
