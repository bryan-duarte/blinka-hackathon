import asyncio
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillSourceIntake, BillSourceType
from contracts.files import FileParseStatus, FileUploadResult
from contracts.guardrails import GuardrailCheckRequest, GuardrailViolation
from contracts.inbox import InboxEmailStatus
from contracts.mail_gateway import FetchedEmail, MailTriggerEvent
from contracts.payments import PaymentRunTrigger
from core.logging_config import get_logger
from modules.guardrails import GuardrailUnavailableError
from modules.inbox.repository import InboxRepository
from modules.mail_gateway import MailProviderError

if TYPE_CHECKING:
    from clients.bills import BillsClient
    from clients.files import FilesClient
    from clients.guardrails import GuardrailsClient
    from clients.mail_gateway import MailGatewayClient
    from clients.payments import PaymentsClient

logger = get_logger(__name__)

SHUTDOWN_CANCELLATION_REASON = "cancelled on shutdown"
GUARD_TEXT_SEPARATOR = "\n\n"
GENERIC_FAILURE_REASON = "processing failed"
UNREADABLE_ATTACHMENT_VIOLATION = GuardrailViolation(
    code="attachment.unreadable", message="PDF attachment has no extractable text to screen"
)
KNOWN_FAILURE_REASONS: dict[type[Exception], str] = {
    GuardrailUnavailableError: "guardrail unavailable",
    MailProviderError: "mail provider unavailable",
}


@dataclass(frozen=True)
class InboxDependencies:
    repository: InboxRepository
    files: "FilesClient"
    guardrails: "GuardrailsClient"
    payments: "PaymentsClient"
    mail_gateway: "MailGatewayClient"
    bills: "BillsClient"


async def process_email(
    email_id: UUID,
    owner: CurrentUser,
    source: MailTriggerEvent | FetchedEmail,
    dependencies: InboxDependencies,
) -> None:
    repository = dependencies.repository
    await repository.set_status(email_id, InboxEmailStatus.PROCESSING)
    try:
        await _analyze(email_id, owner, source, dependencies)
    except asyncio.CancelledError:
        await repository.set_status(
            email_id, InboxEmailStatus.ERROR, error=SHUTDOWN_CANCELLATION_REASON
        )
        raise
    except Exception as pipeline_error:
        logger.exception("inbox_email_failed", email_id=email_id)
        await repository.set_status(
            email_id, InboxEmailStatus.ERROR, error=_failure_reason(pipeline_error)
        )


async def _analyze(
    email_id: UUID,
    owner: CurrentUser,
    source: MailTriggerEvent | FetchedEmail,
    dependencies: InboxDependencies,
) -> None:
    repository = dependencies.repository
    email = await _resolve_email(source, dependencies)
    await repository.store_content(email_id, email)
    attachment_file = await _store_attachment(owner, email, dependencies.files)
    attachment_file_id = attachment_file.file_id if attachment_file else None
    is_unscreenable_attachment = (
        attachment_file is not None and attachment_file.parse_status != FileParseStatus.PARSED
    )
    if is_unscreenable_attachment:
        await repository.mark_blocked(
            email_id, attachment_file_id, [UNREADABLE_ATTACHMENT_VIOLATION]
        )
        logger.info("inbox_email_blocked", email_id=email_id, reason="attachment unreadable")
        return
    guard_text = await _guard_text(owner, email, attachment_file, dependencies.files)
    verdict = await dependencies.guardrails.check(GuardrailCheckRequest(context=guard_text))
    if not verdict.allowed:
        await repository.mark_blocked(email_id, attachment_file_id, verdict.violations)
        logger.info("inbox_email_blocked", email_id=email_id)
        return
    registration = await dependencies.bills.register_source(
        await _bill_source_intake(email_id, owner, email, attachment_file_id, repository)
    )
    if not registration.is_new:
        await repository.mark_duplicate(email_id, attachment_file_id)
        logger.info("inbox_email_duplicate", email_id=email_id)
        return
    accepted_run = await dependencies.payments.start_run(
        PaymentRunTrigger(bill_source_id=registration.source.source_id), owner
    )
    await repository.mark_analyzing(email_id, attachment_file_id, accepted_run.run_id)
    logger.info("inbox_email_analyzing", email_id=email_id, run_id=accepted_run.run_id)


async def _bill_source_intake(
    email_id: UUID,
    owner: CurrentUser,
    email: FetchedEmail,
    attachment_file_id: UUID | None,
    repository: InboxRepository,
) -> BillSourceIntake:
    provider, external_message_id = await repository.get_email_ref(email_id)
    attachment = email.attachments[0] if email.attachments else None
    return BillSourceIntake(
        owner_id=owner.user_id,
        source_type=BillSourceType.EMAIL,
        source_ref=f"{provider}:{external_message_id}",
        sender=email.sender,
        body_text=f"{email.subject}\n\n{email.body}",
        file_id=attachment_file_id,
        attachment_sha256=sha256(attachment.content).hexdigest() if attachment else None,
        inbox_email_id=email_id,
        received_at=email.received_at,
    )


async def _resolve_email(
    source: MailTriggerEvent | FetchedEmail, dependencies: InboxDependencies
) -> FetchedEmail:
    if isinstance(source, FetchedEmail):
        return source
    return await dependencies.mail_gateway.fetch_email(source)


async def _store_attachment(
    owner: CurrentUser, email: FetchedEmail, files: "FilesClient"
) -> FileUploadResult | None:
    if not email.attachments:
        return None
    attachment = email.attachments[0]
    return await files.upload(owner, attachment.filename, attachment.mime, attachment.content)


async def _guard_text(
    owner: CurrentUser,
    email: FetchedEmail,
    attachment_file: FileUploadResult | None,
    files: "FilesClient",
) -> str:
    attachment_text = ""
    if attachment_file is not None:
        attachment_text = await files.get_context(owner, [attachment_file.file_id])
    guarded_parts = (email.subject, email.body, attachment_text)
    return GUARD_TEXT_SEPARATOR.join(part for part in guarded_parts if part)


def _failure_reason(pipeline_error: Exception) -> str:
    for error_type, reason in KNOWN_FAILURE_REASONS.items():
        if isinstance(pipeline_error, error_type):
            return reason
    return GENERIC_FAILURE_REASON
