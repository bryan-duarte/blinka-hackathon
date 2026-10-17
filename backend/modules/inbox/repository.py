from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.guardrails import GuardrailViolation
from contracts.inbox import InboxEmailRecord, InboxEmailStatus, MailboxConnectionRecord
from contracts.mail_gateway import FetchedEmail, MailAccountStatus, MailProvider
from modules.inbox.models import InboxEmail, MailboxConnection

UNFINISHED_STATUSES = (InboxEmailStatus.RECEIVED, InboxEmailStatus.PROCESSING)
INBOX_EMAIL_LIST_LIMIT = 50


class InboxRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def insert_connection(
        self, owner_id: UUID, provider: MailProvider, connected_account_id: str
    ) -> MailboxConnectionRecord:
        connection = MailboxConnection(
            owner_id=owner_id,
            provider=provider,
            connected_account_id=connected_account_id,
            status=MailAccountStatus.INITIATED,
        )
        async with self._sessionmaker() as session:
            session.add(connection)
            await session.commit()
            await session.refresh(connection)
        return _to_connection_record(connection)

    async def get_connection_by_account(
        self, connected_account_id: str
    ) -> MailboxConnectionRecord | None:
        statement = select(MailboxConnection).where(
            MailboxConnection.connected_account_id == connected_account_id
        )
        return await self._one_connection(statement)

    async def get_owned_connection(
        self, owner_id: UUID, connected_account_id: str
    ) -> MailboxConnectionRecord | None:
        statement = select(MailboxConnection).where(
            MailboxConnection.connected_account_id == connected_account_id,
            MailboxConnection.owner_id == owner_id,
        )
        return await self._one_connection(statement)

    async def list_connections(self, owner_id: UUID) -> list[MailboxConnectionRecord]:
        statement = (
            select(MailboxConnection)
            .where(MailboxConnection.owner_id == owner_id)
            .order_by(MailboxConnection.created_at.desc())
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            connections = result.scalars().all()
        return [_to_connection_record(connection) for connection in connections]

    async def update_connection(
        self, connection_id: UUID, status: MailAccountStatus, trigger_id: str | None
    ) -> None:
        statement = (
            update(MailboxConnection)
            .where(MailboxConnection.id == connection_id)
            .values(status=status, trigger_id=trigger_id, updated_at=func.now())
        )
        await self._execute(statement)

    async def insert_email(
        self,
        owner_id: UUID,
        provider: MailProvider,
        external_message_id: str,
        connection_id: UUID | None = None,
    ) -> UUID | None:
        statement = (
            insert(InboxEmail)
            .values(
                owner_id=owner_id,
                provider=provider,
                external_message_id=external_message_id,
                connection_id=connection_id,
                status=InboxEmailStatus.RECEIVED,
                violations=[],
            )
            .on_conflict_do_nothing(index_elements=["provider", "external_message_id"])
            .returning(InboxEmail.id)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            await session.commit()
            return result.scalar_one_or_none()

    async def store_content(self, email_id: UUID, email: FetchedEmail) -> None:
        await self._update_email(
            email_id,
            sender=email.sender,
            subject=email.subject,
            body=email.body,
            received_at=email.received_at,
        )

    async def set_status(
        self, email_id: UUID, status: InboxEmailStatus, error: str | None = None
    ) -> None:
        await self._update_email(email_id, status=status, error=error)

    async def mark_blocked(
        self, email_id: UUID, file_id: UUID | None, violations: list[GuardrailViolation]
    ) -> None:
        await self._update_email(
            email_id,
            status=InboxEmailStatus.BLOCKED,
            file_id=file_id,
            violations=[violation.model_dump() for violation in violations],
        )

    async def mark_analyzing(self, email_id: UUID, file_id: UUID | None, run_id: UUID) -> None:
        await self._update_email(
            email_id, status=InboxEmailStatus.ANALYZING, file_id=file_id, run_id=run_id
        )

    async def mark_duplicate(self, email_id: UUID, file_id: UUID | None) -> None:
        await self._update_email(email_id, status=InboxEmailStatus.DUPLICATE, file_id=file_id)

    async def get_email_ref(self, email_id: UUID) -> tuple[MailProvider, str]:
        statement = select(InboxEmail.provider, InboxEmail.external_message_id).where(
            InboxEmail.id == email_id
        )
        async with self._sessionmaker() as session:
            provider, external_message_id = (await session.execute(statement)).one()
        return MailProvider(provider), external_message_id

    async def get_email(self, email_id: UUID, owner_id: UUID) -> InboxEmailRecord | None:
        statement = select(InboxEmail).where(
            InboxEmail.id == email_id, InboxEmail.owner_id == owner_id
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            email = result.scalar_one_or_none()
        if email is None:
            return None
        return _to_email_record(email)

    async def list_emails(
        self, owner_id: UUID, limit: int = INBOX_EMAIL_LIST_LIMIT
    ) -> list[InboxEmailRecord]:
        statement = (
            select(InboxEmail)
            .where(InboxEmail.owner_id == owner_id)
            .order_by(InboxEmail.created_at.desc())
            .limit(limit)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            emails = result.scalars().all()
        return [_to_email_record(email) for email in emails]

    async def fail_unfinished(self, reason: str) -> int:
        statement = (
            update(InboxEmail)
            .where(InboxEmail.status.in_(UNFINISHED_STATUSES))
            .values(status=InboxEmailStatus.ERROR, error=reason, updated_at=func.now())
            .returning(InboxEmail.id)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            await session.commit()
            return len(result.scalars().all())

    async def _update_email(self, email_id: UUID, **changed_columns: object) -> None:
        statement = (
            update(InboxEmail)
            .where(InboxEmail.id == email_id)
            .values(**changed_columns, updated_at=func.now())
        )
        await self._execute(statement)

    async def _one_connection(self, statement) -> MailboxConnectionRecord | None:
        async with self._sessionmaker() as session:
            result = await session.execute(statement)
            connection = result.scalar_one_or_none()
        if connection is None:
            return None
        return _to_connection_record(connection)

    async def _execute(self, statement) -> None:
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()


def _to_connection_record(connection: MailboxConnection) -> MailboxConnectionRecord:
    return MailboxConnectionRecord(
        connection_id=connection.id,
        owner_id=connection.owner_id,
        provider=MailProvider(connection.provider),
        connected_account_id=connection.connected_account_id,
        trigger_id=connection.trigger_id,
        status=MailAccountStatus(connection.status),
        created_at=connection.created_at,
    )


def _to_email_record(email: InboxEmail) -> InboxEmailRecord:
    return InboxEmailRecord(
        email_id=email.id,
        owner_id=email.owner_id,
        provider=MailProvider(email.provider),
        sender=email.sender,
        subject=email.subject,
        body=email.body,
        received_at=email.received_at,
        status=InboxEmailStatus(email.status),
        violations=[GuardrailViolation.model_validate(violation) for violation in email.violations],
        run_id=email.run_id,
        error=email.error,
    )
