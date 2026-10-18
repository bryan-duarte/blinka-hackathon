import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from time import monotonic
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillSourceIntake
from contracts.files import EvidenceIntake, EvidenceIntakeStatus
from contracts.guardrails import GuardrailCheckRequest, GuardrailViolation
from contracts.inbox import SOURCE_TYPE_BY_PROVIDER, InboxEmailStatus
from contracts.mail_gateway import FetchedEmail, MailTriggerEvent
from contracts.payments import PaymentRunTrigger
from contracts.pipeline import PipelineStage
from contracts.whatsapp_gateway import WhatsAppDocumentEvent
from core.logging_config import get_logger
from modules.guardrails import GuardrailUnavailableError
from modules.inbox.notifier import InboxNotifier
from modules.inbox.repository import InboxRepository
from modules.mail_gateway import MailProviderError
from modules.whatsapp_gateway import WhatsAppProviderError

if TYPE_CHECKING:
    from clients.bills import BillsClient
    from clients.files import FilesClient
    from clients.guardrails import GuardrailsClient
    from clients.mail_gateway import MailGatewayClient
    from clients.payments import PaymentsClient
    from clients.whatsapp_gateway import WhatsAppGatewayClient

logger = get_logger(__name__)

SHUTDOWN_CANCELLATION_REASON = "cancelled on shutdown"
GUARD_TEXT_SEPARATOR = "\n\n"
GENERIC_FAILURE_REASON = "processing failed"
INTAKE_VIOLATIONS = {
    EvidenceIntakeStatus.UNREADABLE: GuardrailViolation(
        code="attachment.unreadable",
        message="The attachment could not be opened safely (damaged ZIP, protected, or no PDF/XML)",
    ),
    EvidenceIntakeStatus.MALWARE: GuardrailViolation(
        code="attachment.malware", message="The file did not pass the AWS malware scan"
    ),
    EvidenceIntakeStatus.SCAN_FAILED: GuardrailViolation(
        code="attachment.scan_failed",
        message="The AWS malware scan did not finish in time; the file was not opened",
    ),
}
KNOWN_FAILURE_REASONS: dict[type[Exception], str] = {
    GuardrailUnavailableError: "guardrail unavailable",
    MailProviderError: "mail provider unavailable",
    WhatsAppProviderError: "whatsapp provider unavailable",
}

MILLISECONDS_PER_SECOND = 1000
GUARDRAIL_ALLOWED_ACTION = "allowed"
GUARDRAIL_BLOCKED_ACTION = "blocked"

InboxSource = MailTriggerEvent | WhatsAppDocumentEvent | FetchedEmail
SOURCE_KIND_BY_TYPE: dict[type[InboxSource], str] = {
    MailTriggerEvent: "mail_trigger",
    WhatsAppDocumentEvent: "whatsapp_document",
    FetchedEmail: "fetched_email",
}
SOURCE_TYPE_BY_KIND = {kind: source_type for source_type, kind in SOURCE_KIND_BY_TYPE.items()}


@dataclass(frozen=True)
class InboxDependencies:
    repository: InboxRepository
    files: "FilesClient"
    guardrails: "GuardrailsClient"
    payments: "PaymentsClient"
    mail_gateway: "MailGatewayClient"
    whatsapp_gateway: "WhatsAppGatewayClient"
    bills: "BillsClient"
    notifier: InboxNotifier


def dump_source(source: InboxSource) -> dict:
    return {"kind": SOURCE_KIND_BY_TYPE[type(source)], "data": json.loads(source.model_dump_json())}


def load_source(source_payload: dict) -> InboxSource:
    source_type = SOURCE_TYPE_BY_KIND[source_payload["kind"]]
    return source_type.model_validate_json(json.dumps(source_payload["data"]))


async def process_email(
    email_id: UUID,
    owner: CurrentUser,
    source: InboxSource,
    dependencies: InboxDependencies,
) -> None:
    repository = dependencies.repository
    notifier = dependencies.notifier
    try:
        await notifier.stage(owner.user_id, email_id, PipelineStage.QUEUED, "finished")
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.PROCESSING)
        await _analyze(email_id, owner, source, dependencies)
    except asyncio.CancelledError:
        await repository.set_status(
            email_id, InboxEmailStatus.ERROR, error=SHUTDOWN_CANCELLATION_REASON
        )
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.ERROR)
        raise
    except Exception as pipeline_error:
        logger.exception("inbox_email_failed", email_id=email_id)
        await repository.set_status(
            email_id, InboxEmailStatus.ERROR, error=_failure_reason(pipeline_error)
        )
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.ERROR)


async def _analyze(
    email_id: UUID,
    owner: CurrentUser,
    source: InboxSource,
    dependencies: InboxDependencies,
) -> None:
    repository = dependencies.repository
    notifier = dependencies.notifier
    timed_stage = partial(_timed_stage, notifier, owner.user_id, email_id)
    async with timed_stage(PipelineStage.FETCH):
        email = await _resolve_email(source, dependencies)
        await repository.store_content(email_id, email)
    async with timed_stage(PipelineStage.MALWARE_SCAN) as scan_detail:
        intake = await dependencies.files.ingest_attachments(owner, email.attachments)
        scan_detail.update(files=len(email.attachments), scan_status=intake.status)
    intake_violation = INTAKE_VIOLATIONS.get(intake.status)
    if intake_violation is not None:
        await repository.mark_blocked(email_id, intake.flagged_file_id, [intake_violation])
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.BLOCKED)
        logger.info("inbox_email_blocked", email_id=email_id, reason=intake.status)
        return
    primary_file_id = intake.primary_file_id
    async with timed_stage(PipelineStage.GUARDRAIL) as guardrail_detail:
        guard_text = await _guard_text(owner, email, primary_file_id, dependencies.files)
        verdict = await dependencies.guardrails.check(GuardrailCheckRequest(context=guard_text))
        guardrail_action = GUARDRAIL_ALLOWED_ACTION if verdict.allowed else GUARDRAIL_BLOCKED_ACTION
        guardrail_detail.update(
            guardrail_action=guardrail_action,
            violations=[violation.code for violation in verdict.violations],
        )
    if not verdict.allowed:
        await repository.mark_blocked(email_id, primary_file_id, verdict.violations)
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.BLOCKED)
        logger.info("inbox_email_blocked", email_id=email_id)
        return
    async with timed_stage(PipelineStage.DEDUP) as dedup_detail:
        registration = await dependencies.bills.register_source(
            await _bill_source_intake(email_id, owner, email, intake, repository)
        )
        dedup_detail.update(duplicate=not registration.is_new)
    if not registration.is_new:
        await repository.mark_duplicate(email_id, primary_file_id)
        await notifier.item_changed(owner.user_id, email_id, InboxEmailStatus.DUPLICATE)
        logger.info("inbox_email_duplicate", email_id=email_id)
        return
    async with timed_stage(PipelineStage.HANDOFF):
        accepted_run = await dependencies.payments.start_run(
            PaymentRunTrigger(
                bill_source_id=registration.source.source_id, evidence=intake.evidence
            ),
            owner,
        )
        await repository.mark_analyzing(email_id, primary_file_id, accepted_run.run_id)
    await notifier.item_changed(
        owner.user_id, email_id, InboxEmailStatus.ANALYZING, accepted_run.run_id
    )
    logger.info("inbox_email_analyzing", email_id=email_id, run_id=accepted_run.run_id)


@asynccontextmanager
async def _timed_stage(
    notifier: InboxNotifier, owner_id: UUID, email_id: UUID, stage: PipelineStage
) -> AsyncIterator[dict]:
    started_at = monotonic()
    stage_detail: dict = {}
    await notifier.stage(owner_id, email_id, stage, "started")
    try:
        yield stage_detail
    except Exception:
        await notifier.stage(
            owner_id, email_id, stage, "failed", _elapsed_ms(started_at), stage_detail
        )
        raise
    await notifier.stage(
        owner_id, email_id, stage, "finished", _elapsed_ms(started_at), stage_detail
    )


async def _bill_source_intake(
    email_id: UUID,
    owner: CurrentUser,
    email: FetchedEmail,
    intake: EvidenceIntake,
    repository: InboxRepository,
) -> BillSourceIntake:
    provider, external_message_id = await repository.get_email_ref(email_id)
    return BillSourceIntake(
        owner_id=owner.user_id,
        source_type=SOURCE_TYPE_BY_PROVIDER[provider],
        source_ref=f"{provider}:{external_message_id}",
        sender=email.sender,
        body_text=f"{email.subject}\n\n{email.body}",
        file_id=intake.primary_file_id,
        attachment_sha256=intake.primary_sha256,
        inbox_email_id=email_id,
        received_at=email.received_at,
    )


async def _resolve_email(source: InboxSource, dependencies: InboxDependencies) -> FetchedEmail:
    if isinstance(source, FetchedEmail):
        return source
    if isinstance(source, WhatsAppDocumentEvent):
        return await dependencies.whatsapp_gateway.fetch_message(source)
    return await dependencies.mail_gateway.fetch_email(source)


async def _guard_text(
    owner: CurrentUser,
    email: FetchedEmail,
    primary_file_id: UUID | None,
    files: "FilesClient",
) -> str:
    attachment_text = ""
    if primary_file_id is not None:
        attachment_text = await files.get_context(owner, [primary_file_id])
    guarded_parts = (email.subject, email.body, attachment_text)
    return GUARD_TEXT_SEPARATOR.join(part for part in guarded_parts if part)


def _failure_reason(pipeline_error: Exception) -> str:
    for error_type, reason in KNOWN_FAILURE_REASONS.items():
        if isinstance(pipeline_error, error_type):
            return reason
    return GENERIC_FAILURE_REASON


def _elapsed_ms(started_at: float) -> int:
    return round((monotonic() - started_at) * MILLISECONDS_PER_SECOND)
