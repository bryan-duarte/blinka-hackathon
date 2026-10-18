import asyncio
from collections.abc import Mapping
from operator import attrgetter
from time import monotonic
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from contracts.auth import CurrentUser
from contracts.bills import BillStatus
from contracts.inbox import (
    PROVIDERS_BY_CHANNEL,
    SOURCE_TYPE_BY_PROVIDER,
    InboxChannel,
    InboxEmailDetail,
    InboxEmailRecord,
    InboxEmailStatus,
    InboxEmailView,
    MailboxConnectionRecord,
    MailboxConnectionView,
    MailboxConnectStarted,
    QueuedEmail,
)
from contracts.mail_gateway import FetchedEmail, MailAccountStatus, MailProvider
from contracts.payments import BillDecisionView, PaymentRunStatus, RunStatus, Verdict
from contracts.pipeline import PipelineStage
from contracts.whatsapp_gateway import (
    ConfirmWhatsAppRequest,
    WhatsAppConnectionMode,
    WhatsAppDocumentEvent,
    WhatsAppSandboxView,
)
from core.background import ExecutionRegistry
from core.config import KapsoSettings
from core.logging_config import get_logger
from core.work_queue import QueueLimits, QueueWorker
from modules.inbox.errors import (
    EmailMissingError,
    MailboxConnectionMissingError,
    WhatsAppPhoneTakenError,
)
from modules.inbox.pipeline import (
    InboxDependencies,
    InboxSource,
    dump_source,
    load_source,
    process_email,
)
from modules.inbox.repository import InboxRepository
from modules.mail_gateway import MailProviderError
from modules.whatsapp_gateway import normalize_user_phone

if TYPE_CHECKING:
    from clients.auth import AuthClient

logger = get_logger(__name__)

PREVIEW_CHARS = 140
SIMULATED_MESSAGE_PREFIX = "sim-"
SANDBOX_ACCOUNT_PREFIX = "sandbox:"
SETUP_LINK_ACCOUNT_PREFIX = "setup:"
INBOX_QUEUE_NAME = "inbox_emails"
UNPROCESSABLE_CLAIM_REASON = "queued message could not be read"
OWNER_CANCELLATION_REASON = "cancelled before it started"
MAIL_RECONCILE_TTL_SECONDS = 60
RECONCILED_PROVIDERS = frozenset({MailProvider.GMAIL, MailProvider.OUTLOOK})
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
        kapso: KapsoSettings,
        queue_limits: QueueLimits,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._dependencies = dependencies
        self._auth = auth
        self._callback_url = callback_url
        self._kapso = kapso
        self._worker = QueueWorker(
            INBOX_QUEUE_NAME,
            claim=repository.claim_received_emails,
            handle=self.process_claimed,
            work_id=attrgetter("email_id"),
            registry=registry,
            limits=queue_limits,
        )
        self._mail_reconciled_at: dict[UUID, float] = {}

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
        return _to_connection_view(connection.model_copy(update={"status": account_status}))

    async def register_whatsapp_sandbox(
        self, owner: CurrentUser, raw_phone: str
    ) -> WhatsAppSandboxView:
        phone_number = normalize_user_phone(raw_phone)
        connection = await self._repository.get_active_sandbox_connection(phone_number)
        if connection is not None and connection.owner_id != owner.user_id:
            raise WhatsAppPhoneTakenError
        if connection is None:
            await self._repository.expire_sandbox_connections(owner.user_id)
            connection = await self._repository.insert_connection(
                owner.user_id,
                MailProvider.WHATSAPP,
                f"{SANDBOX_ACCOUNT_PREFIX}{uuid4()}",
                mode=WhatsAppConnectionMode.SANDBOX,
                phone_number=phone_number,
                status=MailAccountStatus.ACTIVE,
            )
            logger.info("whatsapp_sandbox_registered", connection_id=connection.connection_id)
        return WhatsAppSandboxView(
            connection_id=connection.connection_id,
            phone_number=phone_number,
            sandbox_number=self._kapso.sandbox_display_number,
            status=connection.status,
        )

    async def start_whatsapp_connection(self, owner: CurrentUser) -> MailboxConnectStarted:
        whatsapp_gateway = self._dependencies.whatsapp_gateway
        customer_id = await self._repository.get_owner_whatsapp_customer_id(owner.user_id)
        if customer_id is None:
            customer_id = await whatsapp_gateway.ensure_customer(owner.user_id, owner.email)
        setup_link = await whatsapp_gateway.create_setup_link(customer_id)
        connection = await self._repository.insert_connection(
            owner.user_id,
            MailProvider.WHATSAPP,
            f"{SETUP_LINK_ACCOUNT_PREFIX}{setup_link.setup_link_id}",
            mode=WhatsAppConnectionMode.OWN_NUMBER,
            external_ref=customer_id,
        )
        logger.info("whatsapp_connection_started", connection_id=connection.connection_id)
        return MailboxConnectStarted(
            connection_id=connection.connection_id, redirect_url=setup_link.url
        )

    async def confirm_whatsapp_connection(
        self, owner: CurrentUser, request: ConfirmWhatsAppRequest
    ) -> MailboxConnectionView:
        connection = await self._repository.get_owned_connection(
            owner.user_id, f"{SETUP_LINK_ACCOUNT_PREFIX}{request.setup_link_id}"
        )
        if connection is None or connection.external_ref is None:
            return await self._confirmed_whatsapp_connection(owner, request.phone_number_id)
        whatsapp_gateway = self._dependencies.whatsapp_gateway
        phone_number = await whatsapp_gateway.get_phone_number(
            connection.external_ref, request.phone_number_id
        )
        webhook_id = connection.trigger_id or await whatsapp_gateway.register_message_webhook(
            phone_number.phone_number_id
        )
        await self._repository.activate_whatsapp_number(
            connection.connection_id,
            phone_number.phone_number_id,
            webhook_id,
            phone_number.display_phone_number,
        )
        await self._repository.expire_sandbox_connections(owner.user_id)
        logger.info("whatsapp_connection_confirmed", connection_id=connection.connection_id)
        return _to_connection_view(
            connection.model_copy(
                update={
                    "status": MailAccountStatus.ACTIVE,
                    "phone_number": phone_number.display_phone_number,
                }
            )
        )

    async def list_connections(self, owner: CurrentUser) -> list[MailboxConnectionView]:
        stored_connections = await self._repository.list_connections(owner.user_id)
        connections = await self._reconcile_mail_connections(stored_connections)
        return [
            _to_connection_view(connection, self._kapso.sandbox_display_number)
            for connection in connections
        ]

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
        email_id = await self._receive(connection, event.provider, event.message_id, event)
        if email_id is not None:
            logger.info("inbox_email_received", email_id=email_id, provider=event.provider)

    async def ingest_whatsapp_webhook(self, body: bytes, headers: Mapping[str, str]) -> None:
        for event in self._dependencies.whatsapp_gateway.parse_webhook(body, headers):
            connection = await self._whatsapp_connection_for(event)
            if connection is None:
                logger.warning(
                    "whatsapp_webhook_unknown_sender", phone_number_id=event.phone_number_id
                )
                continue
            email_id = await self._receive(
                connection, MailProvider.WHATSAPP, event.message_id, event
            )
            if email_id is not None:
                logger.info("inbox_whatsapp_received", email_id=email_id)

    async def inject(
        self, owner: CurrentUser, message: FetchedEmail, channel: InboxChannel
    ) -> InboxEmailView:
        provider = MailProvider.WHATSAPP if channel == "whatsapp" else MailProvider.SIMULATED
        email_id = await self._repository.insert_email(
            owner.user_id, provider, f"{SIMULATED_MESSAGE_PREFIX}{uuid4()}", dump_source(message)
        )
        assert email_id is not None
        await self._accept(email_id, owner)
        logger.info("inbox_email_injected", email_id=email_id, channel=channel)
        return InboxEmailView(
            email_id=email_id,
            provider=provider,
            sender=message.sender,
            subject=message.subject,
            preview=_preview(message.body),
            received_at=None,
            status=InboxEmailStatus.RECEIVED,
            source_type=SOURCE_TYPE_BY_PROVIDER[provider],
        )

    async def get_email_status(self, owner: CurrentUser, email_id: UUID) -> InboxEmailStatus:
        record = await self._repository.get_email(email_id, owner.user_id)
        if record is None:
            raise EmailMissingError
        run = await self._linked_run(owner, record) if _is_waiting_on_run(record) else None
        status, _, _ = _resolve_status(record, run)
        return status

    async def cancel_owner(self, owner_id: UUID) -> int:
        abandoned_count = await self._repository.abandon_received_emails(
            owner_id, OWNER_CANCELLATION_REASON
        )
        cancelled_count = await self._registry.cancel_owner(owner_id)
        if cancelled_count or abandoned_count:
            logger.info(
                "inbox_items_cancelled",
                owner_id=owner_id,
                count=cancelled_count,
                abandoned_count=abandoned_count,
            )
        return cancelled_count

    async def list_emails(
        self, owner: CurrentUser, source: InboxChannel | None
    ) -> list[InboxEmailView]:
        providers = PROVIDERS_BY_CHANNEL[source] if source is not None else None
        records = await self._repository.list_emails(owner.user_id, providers)
        return [await self._to_view(owner, record) for record in records]

    async def get_email(self, owner: CurrentUser, email_id: UUID) -> InboxEmailDetail:
        record = await self._repository.get_email(email_id, owner.user_id)
        if record is None:
            raise EmailMissingError
        run = await self._linked_run(owner, record)
        status, decision, error = _resolve_status(record, run)
        email_view = _to_email_view(record, status, decision)
        return InboxEmailDetail(
            **dict(email_view),
            body=record.body,
            violations=record.violations,
            error=error,
            run_id=record.run_id,
            evidence=run.evidence if run else [],
            pipeline_stages=record.pipeline_stages,
        )

    async def fail_unfinished(self, reason: str) -> None:
        failed_count = await self._repository.fail_unfinished(reason)
        if failed_count:
            logger.warning("unfinished_inbox_emails_swept", failed_count=failed_count)

    def start_worker(self) -> None:
        self._worker.start()

    async def process_claimed(self, email: QueuedEmail) -> None:
        try:
            owner = await self._auth.get_user(email.owner_id)
            source = load_source(email.source_payload)
        except Exception:
            logger.exception("inbox_claim_unprocessable", email_id=email.email_id)
            await self._repository.set_status(
                email.email_id, InboxEmailStatus.ERROR, error=UNPROCESSABLE_CLAIM_REASON
            )
            return
        await process_email(email.email_id, owner, source, self._dependencies)

    async def shutdown(self) -> None:
        await self._worker.stop()
        await self._registry.shutdown()

    async def _receive(
        self,
        connection: MailboxConnectionRecord,
        provider: MailProvider,
        message_id: str,
        source: InboxSource,
    ) -> UUID | None:
        owner = await self._auth.get_user(connection.owner_id)
        email_id = await self._repository.insert_email(
            connection.owner_id, provider, message_id, dump_source(source), connection.connection_id
        )
        if email_id is None:
            logger.info("inbox_webhook_duplicate", message_id=message_id)
            return None
        await self._accept(email_id, owner)
        return email_id

    async def _accept(self, email_id: UUID, owner: CurrentUser) -> None:
        notifier = self._dependencies.notifier
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.RECEIVED)
        await notifier.stage(owner.user_id, email_id, PipelineStage.QUEUED, "started")
        self._worker.notify()

    async def _reconcile_mail_connections(
        self, connections: list[MailboxConnectionRecord]
    ) -> list[MailboxConnectionRecord]:
        due_connections = [
            connection for connection in connections if self._is_reconcile_due(connection)
        ]
        refresh_outcomes = await asyncio.gather(
            *(self._refresh_mail_status(connection) for connection in due_connections),
            return_exceptions=True,
        )
        refreshed_by_id: dict[UUID, MailboxConnectionRecord] = {}
        for connection, outcome in zip(due_connections, refresh_outcomes, strict=True):
            if isinstance(outcome, MailboxConnectionRecord):
                refreshed_by_id[connection.connection_id] = outcome
            elif isinstance(outcome, Exception):
                logger.error(
                    "mailbox_reconcile_crashed",
                    connection_id=connection.connection_id,
                    exc_info=outcome,
                )
        return [
            refreshed_by_id.get(connection.connection_id, connection) for connection in connections
        ]

    def _is_reconcile_due(self, connection: MailboxConnectionRecord) -> bool:
        last_reconciled_at = self._mail_reconciled_at.get(connection.connection_id)
        is_stale = (
            last_reconciled_at is None
            or monotonic() - last_reconciled_at >= MAIL_RECONCILE_TTL_SECONDS
        )
        return (
            connection.provider in RECONCILED_PROVIDERS
            and connection.status is MailAccountStatus.ACTIVE
            and is_stale
        )

    async def _refresh_mail_status(
        self, connection: MailboxConnectionRecord
    ) -> MailboxConnectionRecord:
        self._mail_reconciled_at[connection.connection_id] = monotonic()
        try:
            account_status = await self._dependencies.mail_gateway.get_account_status(
                connection.connected_account_id
            )
        except MailProviderError:
            logger.warning(
                "mailbox_reconcile_failed", connection_id=connection.connection_id, exc_info=True
            )
            return connection
        if account_status is connection.status:
            return connection
        await self._repository.set_connection_status(connection.connection_id, account_status)
        logger.warning(
            "mailbox_status_changed", connection_id=connection.connection_id, status=account_status
        )
        return connection.model_copy(update={"status": account_status})

    async def _whatsapp_connection_for(
        self, event: WhatsAppDocumentEvent
    ) -> MailboxConnectionRecord | None:
        is_sandbox_message = event.phone_number_id == self._kapso.sandbox_phone_number_id
        if is_sandbox_message:
            return await self._repository.get_active_sandbox_connection(event.sender_phone)
        connection = await self._repository.get_connection_by_account(event.phone_number_id)
        is_active_connection = (
            connection is not None and connection.status == MailAccountStatus.ACTIVE
        )
        return connection if is_active_connection else None

    async def _confirmed_whatsapp_connection(
        self, owner: CurrentUser, phone_number_id: str
    ) -> MailboxConnectionView:
        connection = await self._repository.get_owned_connection(owner.user_id, phone_number_id)
        if connection is None:
            raise MailboxConnectionMissingError
        return _to_connection_view(connection)

    async def _to_view(self, owner: CurrentUser, record: InboxEmailRecord) -> InboxEmailView:
        run = await self._linked_run(owner, record) if _is_waiting_on_run(record) else None
        status, decision, _ = _resolve_status(record, run)
        return _to_email_view(record, status, decision)

    async def _linked_run(
        self, owner: CurrentUser, record: InboxEmailRecord
    ) -> PaymentRunStatus | None:
        if record.run_id is None:
            return None
        return await self._dependencies.payments.get_run(record.run_id, owner)


def _is_waiting_on_run(record: InboxEmailRecord) -> bool:
    return record.status == InboxEmailStatus.ANALYZING and record.run_id is not None


def _resolve_status(
    record: InboxEmailRecord, run: PaymentRunStatus | None
) -> tuple[InboxEmailStatus, BillDecisionView | None, str | None]:
    if run is None or not _is_waiting_on_run(record):
        return record.status, None, record.error
    if run.decision is not None:
        return _decision_status(run.decision), run.decision, None
    if run.status == RunStatus.FAILED:
        return InboxEmailStatus.ERROR, None, run.error
    if run.status != RunStatus.COMPLETED:
        return InboxEmailStatus.ANALYZING, None, None
    if run.extraction_failed:
        return InboxEmailStatus.NO_INFO, None, None
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
        source_type=SOURCE_TYPE_BY_PROVIDER[record.provider],
    )


def _preview(body: str) -> str:
    return " ".join(body.split())[:PREVIEW_CHARS]


def _to_connection_view(
    connection: MailboxConnectionRecord, sandbox_number: str | None = None
) -> MailboxConnectionView:
    is_sandbox_connection = connection.mode == WhatsAppConnectionMode.SANDBOX
    return MailboxConnectionView(
        connection_id=connection.connection_id,
        provider=connection.provider,
        status=connection.status,
        created_at=connection.created_at,
        mode=connection.mode,
        phone_number=connection.phone_number,
        sandbox_number=sandbox_number if is_sandbox_connection else None,
    )
