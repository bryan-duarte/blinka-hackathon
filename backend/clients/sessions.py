from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.sessions import ExecutionRecord, ExecutionRecorded, SessionSummary

if TYPE_CHECKING:
    from modules.sessions.service import SessionsService


class SessionsClient:
    def __init__(self, service: "SessionsService") -> None:
        self._service = service

    async def ensure_session(self, owner: CurrentUser, session_id: UUID | None) -> UUID:
        return await self._service.ensure_session(owner, session_id)

    async def record_execution(
        self,
        owner: CurrentUser,
        session_id: UUID,
        agent: str,
        input_summary: str,
        output_summary: str,
    ) -> ExecutionRecorded:
        return await self._service.record_execution(
            owner, session_id, agent, input_summary, output_summary
        )

    async def list_sessions(self, owner: CurrentUser) -> list[SessionSummary]:
        return await self._service.list_sessions(owner)

    async def get_executions(self, session_id: UUID, owner: CurrentUser) -> list[ExecutionRecord]:
        return await self._service.get_executions(session_id, owner)
