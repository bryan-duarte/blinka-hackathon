from uuid import UUID

from contracts.auth import CurrentUser
from contracts.sessions import ExecutionRecord, ExecutionRecorded, SessionSummary
from modules.sessions.errors import SessionMissingError
from modules.sessions.immutable_repository import SessionsImmutableRepository
from modules.sessions.mutable_repository import SessionsMutableRepository

SUMMARY_MAX_CHARS = 500


class SessionsService:
    def __init__(
        self,
        mutable: SessionsMutableRepository,
        immutable: SessionsImmutableRepository,
    ) -> None:
        self._mutable = mutable
        self._immutable = immutable

    async def ensure_session(self, owner: CurrentUser, session_id: UUID | None) -> UUID:
        if session_id is None:
            return await self._mutable.create(owner.user_id)
        await self._require_owned_session(owner, session_id)
        await self._mutable.touch(session_id)
        return session_id

    async def record_execution(
        self,
        owner: CurrentUser,
        session_id: UUID,
        agent: str,
        input_summary: str,
        output_summary: str,
    ) -> ExecutionRecorded:
        await self._require_owned_session(owner, session_id)
        execution_id = await self._immutable.append(
            session_id,
            agent,
            _truncate(input_summary),
            _truncate(output_summary),
        )
        return ExecutionRecorded(execution_id=execution_id)

    async def list_sessions(self, owner: CurrentUser) -> list[SessionSummary]:
        return await self._mutable.list_by_owner(owner.user_id)

    async def get_executions(self, session_id: UUID, owner: CurrentUser) -> list[ExecutionRecord]:
        await self._require_owned_session(owner, session_id)
        return await self._immutable.list_by_session(session_id)

    async def _require_owned_session(self, owner: CurrentUser, session_id: UUID) -> None:
        owned_session = await self._mutable.get(session_id, owner.user_id)
        if owned_session is None:
            raise SessionMissingError


def _truncate(summary: str) -> str:
    return summary[:SUMMARY_MAX_CHARS]
