from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from contracts.auth import CurrentUser
from contracts.bills import BillStatus
from contracts.inbox import (
    InboxEmailDetail,
    InboxEmailRecord,
    InboxEmailStatus,
    InboxEmailView,
    MailboxConnectionRecord,
    MailboxConnectionView,
    MailboxConnectStarted,
    SimulatedEmailKind,
)
from contracts.mail_gateway import MailAccountStatus, MailProvider
from contracts.payments import BillDecisionView, RunStatus, Verdict
from core.background import ExecutionRegistry
from core.logging_config import get_logger
from modules.inbox.errors import EmailMissingError, MailboxConnectionMissingError
from modules.inbox.pipeline import InboxDependencies, process_email
from modules.inbox.repository import InboxRepository
from modules.inbox.samples import SIMULATED_EMAILS

if TYPE_CHECKING:
    from clients.auth import AuthClient

logger = get_logger(__name__)

PREVIEW_CHARS = 140
SIMULATED_MESSAGE_PREFIX = "sim-"
VERDICT_INBOX_STATUS = {
    Verdict.PAY: InboxEmailStatus.PAID,
    Verdict.HOLD: InboxEmailStatus.HELD,
    Verdict.REVIEW: InboxEmailStatus.REVIEW,
}


class InboxService:
    def __init__(
        self,
        repository: InboxRepository,
        registry: ExecutionRegistry,
        dependencies: InboxDependencies,
        auth: "AuthClient",
        callback_url: str,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._dependencies = dependencies
        self._auth = auth
        self._callback_url = callback_url

    async def start_connection(
        self, owner: CurrentUser, provider: MailProvider
    ) -> MailboxConnectStarted:
        mailbox_link = await self._dependencies.mail_gateway.link_account(
            owner.user_id, provider, self._callback_url
        )
        connection = await self._repository.insert_connection(
            owner.user_id, provider, mailbox_link.connected_account_id
        )
        logger.info("mailbox_connection_started", connection_id=connection.connection_id)
        return MailboxConnectStarted(
            connection_id=connection.connection_id, redirect_url=mailbox_link.redirect_url
        )

    async def confirm_connection(
        self, owner: CurrentUser, connected_account_id: str
    ) -> MailboxConnectionView:
        connection = await self._repository.get_owned_connection(
            owner.user_id, connected_account_id
        )
        if connection is None:
            raise MailboxConnectionMissingError
        mail_gateway = self._dependencies.mail_gateway
        account_status = await mail_gateway.get_account_status(connected_account_id)
        await self._repository.update_connection(
            connection.connection_id, account_status, connection.trigger_id
        )
        needs_trigger = account_status == MailAccountStatus.ACTIVE and connection.trigger_id is None
        if needs_trigger:
            trigger_id = await mail_gateway.enable_new_mail_trigger(
                owner.user_id, connection.provider, connected_account_id
            )
            await self._repository.update_connection(
                connection.connection_id, account_status, trigger_id
            )
        return MailboxConnectionView(
            connection_id=connection.connection_id,
            provider=connection.provider,
            status=account_status,
            created_at=connection.created_at,
        )

    async def list_connections(self, owner: CurrentUser) -> list[MailboxConnectionView]:
        connections = await self._repository.list_connections(owner.user_id)
        return [_to_connection_view(connection) for connection in connections]

    async def ingest_webhook(self, body: bytes, headers: Mapping[str, str]) -> None:
        event = self._dependencies.mail_gateway.parse_webhook(body, headers)
        if event is None:
            return
        connection = await self._repository.get_connection_by_account(event.connected_account_id)
        if connection is None:
            logger.warning(
                "inbox_webhook_unknown_account", connected_account_id=event.connected_account_id
            )
            return
        owner = await self._auth.get_user(connection.owner_id)
        email_id = await self._repository.insert_email(
            connection.owner_id, event.provider, event.message_id, connection.connection_id
        )
        if email_id is None:
            logger.info("inbox_webhook_duplicate", message_id=event.message_id)
            return
        self._registry.spawn(email_id, process_email(email_id, owner, event, self._dependencies))
        logger.info("inbox_email_received", email_id=email_id, provider=event.provider)

    async def simulate(self, owner: CurrentUser, kind: SimulatedEmailKind) -> InboxEmailView:
        email_id = await self._repository.insert_email(
            owner.user_id, MailProvider.SIMULATED, f"{SIMULATED_MESSAGE_PREFIX}{uuid4()}"
        )
        assert email_id is not None
        simulated_email = SIMULATED_EMAILS[kind]
        self._registry.spawn(
            email_id, process_email(email_id, owner, simulated_email, self._dependencies)
        )
        logger.info("inbox_email_simulated", email_id=email_id, kind=kind)
        return InboxEmailView(
            email_id=email_id,
            provider=MailProvider.SIMULATED,
            sender=simulated_email.sender,
            subject=simulated_email.subject,
            preview=_preview(simulated_email.body),
            received_at=None,
            status=InboxEmailStatus.RECEIVED,
        )

    async def list_emails(self, owner: CurrentUser) -> list[InboxEmailView]:
        records = await self._repository.list_emails(owner.user_id)
        return [await self._to_view(owner, record) for record in records]

    async def get_email(self, owner: CurrentUser, email_id: UUID) -> InboxEmailDetail:
        record = await self._repository.get_email(email_id, owner.user_id)
        if record is None:
            raise EmailMissingError
        status, decision, error = await self._resolve_status(owner, record)
        email_view = _to_email_view(record, status, decision)
        return InboxEmailDetail(
            **dict(email_view),
            body=record.body,
            violations=record.violations,
            error=error,
            run_id=record.run_id,
        )

    async def fail_unfinished(self, reason: str) -> None:
        failed_count = await self._repository.fail_unfinished(reason)
        if failed_count:
            logger.warning("unfinished_inbox_emails_swept", failed_count=failed_count)

    async def shutdown(self) -> None:
        await self._registry.shutdown()

    async def _to_view(self, owner: CurrentUser, record: InboxEmailRecord) -> InboxEmailView:
        status, decision, _ = await self._resolve_status(owner, record)
        return _to_email_view(record, status, decision)

    async def _resolve_status(
        self, owner: CurrentUser, record: InboxEmailRecord
    ) -> tuple[InboxEmailStatus, BillDecisionView | None, str | None]:
        is_waiting_on_run = (
            record.status == InboxEmailStatus.ANALYZING and record.run_id is not None
        )
        if not is_waiting_on_run:
            return record.status, None, record.error
        run = await self._dependencies.payments.get_run(record.run_id, owner)
        if run.decision is not None:
            return _decision_status(run.decision), run.decision, None
        if run.status == RunStatus.FAILED:
            return InboxEmailStatus.ERROR, None, run.error
        if run.status != RunStatus.COMPLETED:
            return InboxEmailStatus.ANALYZING, None, None
        return InboxEmailStatus.NO_INVOICE, None, None


def _decision_status(decision: BillDecisionView) -> InboxEmailStatus:
    if decision.status is BillStatus.DUPLICATE:
        return InboxEmailStatus.DUPLICATE
    return VERDICT_INBOX_STATUS[decision.verdict]


def _to_email_view(
    record: InboxEmailRecord, status: InboxEmailStatus, decision: BillDecisionView | None
) -> InboxEmailView:
    return InboxEmailView(
        email_id=record.email_id,
        provider=record.provider,
        sender=record.sender,
        subject=record.subject,
        preview=_preview(record.body),
        received_at=record.received_at,
        status=status,
        decision=decision,
    )


def _preview(body: str) -> str:
    return " ".join(body.split())[:PREVIEW_CHARS]


def _to_connection_view(connection: MailboxConnectionRecord) -> MailboxConnectionView:
    return MailboxConnectionView(
        connection_id=connection.connection_id,
        provider=connection.provider,
        status=connection.status,
        created_at=connection.created_at,
    )
