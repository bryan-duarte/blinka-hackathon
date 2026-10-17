import asyncio
import re
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import BillClaim, BillDocument, BillFields, BillSourceRecord, BillStatus
from contracts.payment_candidates import BillClassification, PaymentCandidateBase
from contracts.payment_policy import PayeeMatch, PaymentPolicy
from contracts.payments import DecisionActor, DecisionRecord, RunStatus, Verdict
from core.logging_config import get_logger
from modules.invoice_ingestor import InvoiceParseError
from modules.payments.checker import apply_checker, run_checker
from modules.payments.context_builder import build_context
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.fx import to_usd
from modules.payments.rules import decide
from modules.payments.settlement import fail_closed, record_duplicate, settle

logger = get_logger(__name__)

PAYMENTS_AGENT_NAME = "payments"
ISO_CURRENCY_CODE = re.compile(r"[A-Z]{3}")
SHUTDOWN_CANCELLATION_REASON = "cancelled on shutdown"
EXECUTION_SUMMARY_MAX_CHARS = 500

STARTED_STEP = "started"
CLASSIFIED_STEP = "classified"
NOT_A_BILL_STEP = "not_a_bill"
EXTRACTED_STEP = "extracted"
EXTRACTION_FAILED_STEP = "extraction_failed"
CLAIMED_STEP = "claimed"
DECIDED_STEP = "decided"
DECISION_FAILED_STEP = "decision_failed"
COMPLETED_STEP = "completed"
CANCELLED_STEP = "cancelled"
FAILED_STEP = "failed"


async def run_execution(
    run_id: UUID,
    owner: CurrentUser,
    bill_source_id: UUID,
    session_id: UUID | None,
    dependencies: PaymentRunDependencies,
) -> None:
    repository = dependencies.repository
    await repository.insert_event(run_id, STARTED_STEP, {})
    await repository.update_status(run_id, RunStatus.RUNNING)
    await repository.attach_run_to_evidence(bill_source_id, run_id)
    try:
        decision = await _decide_source(run_id, owner, bill_source_id, dependencies)
        await repository.insert_event(run_id, COMPLETED_STEP, {})
        await repository.update_status(run_id, RunStatus.COMPLETED)
        logger.info("payment_run_completed", run_id=run_id)
    except asyncio.CancelledError:
        await repository.insert_event(run_id, CANCELLED_STEP, {})
        await repository.update_status(run_id, RunStatus.FAILED, error=SHUTDOWN_CANCELLATION_REASON)
        raise
    except Exception as execution_error:
        logger.exception("payment_run_failed", run_id=run_id)
        await repository.insert_event(run_id, FAILED_STEP, {"error": str(execution_error)})
        await repository.update_status(run_id, RunStatus.FAILED, error=str(execution_error))
        return
    try:
        await _record_execution(dependencies, owner, session_id, decision)
    except Exception:
        logger.exception("payment_run_session_record_failed", run_id=run_id)


async def _decide_source(
    run_id: UUID,
    owner: CurrentUser,
    bill_source_id: UUID,
    dependencies: PaymentRunDependencies,
) -> DecisionRecord | None:
    repository = dependencies.repository
    source = await dependencies.bills.get_source(owner.user_id, bill_source_id)
    document = BillDocument(
        body_text=source.body_text, file_id=source.file_id, sender=source.sender
    )
    classification = await dependencies.invoice_ingestor.classify(owner, document)
    await repository.insert_event(run_id, CLASSIFIED_STEP, classification.model_dump(mode="json"))
    is_payable_bill = classification.is_bill and classification.kind is not None
    if not is_payable_bill:
        await repository.insert_event(run_id, NOT_A_BILL_STEP, {"reason": classification.reason})
        return None
    try:
        extraction = await dependencies.invoice_ingestor.extract_candidate(
            owner, document, classification.kind
        )
    except InvoiceParseError as extraction_error:
        await repository.insert_event(
            run_id,
            EXTRACTION_FAILED_STEP,
            {"reason": str(extraction_error), "methods_tried": extraction_error.methods_tried},
        )
        logger.info("payment_run_no_info", run_id=run_id)
        return None
    candidate = extraction.candidate
    await repository.insert_event(
        run_id,
        EXTRACTED_STEP,
        {
            **candidate.model_dump(mode="json"),
            "method": extraction.method,
            "document_origin": (
                extraction.origin.model_dump(mode="json") if extraction.origin else None
            ),
        },
    )
    policy = await dependencies.policy.get_policy(owner)
    match = await dependencies.policy.match_payee(owner.user_id, candidate, source.sender)
    claim = await dependencies.bills.claim_bill(
        owner.user_id, source, _bill_fields(candidate, match)
    )
    try:
        await repository.set_run_bill(run_id, claim.bill.bill_id)
        await repository.insert_event(run_id, CLAIMED_STEP, _claim_payload(claim))
        if claim.duplicate_of is not None:
            return await record_duplicate(
                dependencies, run_id, claim.bill, claim.duplicate_of, policy
            )
        decision = await _decide_bill(
            run_id, claim, source, candidate, match, policy, classification, dependencies
        )
    except Exception:
        logger.exception("bill_decision_failed", run_id=run_id, bill_id=claim.bill.bill_id)
        if claim.duplicate_of is not None:
            raise
        await repository.insert_event(run_id, DECISION_FAILED_STEP, {})
        await fail_closed(dependencies, run_id, claim.bill, policy)
        return None
    await repository.insert_event(
        run_id, DECIDED_STEP, {"verdict": decision.verdict, "bill_id": str(decision.bill_id)}
    )
    return decision


async def _decide_bill(
    run_id: UUID,
    claim: BillClaim,
    source: BillSourceRecord,
    candidate: PaymentCandidateBase,
    match: PayeeMatch,
    policy: PaymentPolicy,
    classification: BillClassification,
    dependencies: PaymentRunDependencies,
) -> DecisionRecord:
    context = await build_context(
        dependencies, claim.bill, source, candidate, match, policy, classification
    )
    evaluation = decide(context)
    assessment = None
    if evaluation.verdict is Verdict.PAY:
        assessment = await run_checker(dependencies.llm_gateway, dependencies.prompts, context)
        evaluation = apply_checker(evaluation, assessment, context)
    return await settle(
        dependencies,
        run_id,
        claim.bill,
        context,
        evaluation,
        actor=DecisionActor.AGENT,
        from_status=BillStatus.DECIDING,
        checker=assessment,
    )


def _bill_fields(candidate: PaymentCandidateBase, match: PayeeMatch) -> BillFields:
    return BillFields(
        kind=candidate.kind,
        payee_id=match.payee.payee_id if match.payee else None,
        payee_name=candidate.payee_name,
        normalized_payee_name=match.normalized_payee_name,
        invoice_number=candidate.invoice_number,
        amount=candidate.amount,
        currency=_iso_currency(candidate.currency),
        amount_usd=to_usd(candidate.amount, candidate.currency),
        category=candidate.category,
        due_date=candidate.due_date,
        candidate=candidate.model_dump(mode="json"),
    )


def _iso_currency(currency: str | None) -> str | None:
    normalized_currency = (currency or "").strip().upper()
    return normalized_currency if ISO_CURRENCY_CODE.fullmatch(normalized_currency) else None


def _claim_payload(claim: BillClaim) -> dict:
    return {
        "bill_id": str(claim.bill.bill_id),
        "duplicate_of": str(claim.duplicate_of.bill_id) if claim.duplicate_of else None,
    }


async def _record_execution(
    dependencies: PaymentRunDependencies,
    owner: CurrentUser,
    session_id: UUID | None,
    decision: DecisionRecord | None,
) -> None:
    if session_id is None or decision is None:
        return
    bill = await dependencies.bills.get_bill(owner.user_id, decision.bill_id)
    await dependencies.sessions.record_execution(
        owner,
        session_id,
        PAYMENTS_AGENT_NAME,
        f"{bill.kind} {bill.payee_name} {bill.amount} {bill.currency}",
        decision.explanation[:EXECUTION_SUMMARY_MAX_CHARS],
    )
