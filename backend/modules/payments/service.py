from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from contracts.auth import CurrentUser
from contracts.bills import (
    BillRecord,
    BillSourceIntake,
    BillSourceRecord,
    BillSourceType,
    BillSourceView,
    BillStatus,
)
from contracts.files import EvidenceFileView, EvidenceIntakeStatus
from contracts.payments import (
    BillDecisionView,
    BillDetail,
    BudgetUsageView,
    DecisionActor,
    DecisionRecord,
    PaymentRecord,
    PaymentRunAccepted,
    PaymentRunEvent,
    PaymentRunRecord,
    PaymentRunStatus,
    PaymentRunTrigger,
    PaymentView,
    ReviewActionRequest,
    RuleEffect,
    RunStatus,
    RunTraceView,
    Verdict,
)
from contracts.prompts import PromptId
from core.agents import thread_config
from core.background import ExecutionRegistry
from core.logging_config import get_logger
from modules.files import FileQuarantinedError, UnsafeArchiveError
from modules.payments.budget import CATEGORY_SCOPE_PREFIX, GLOBAL_SCOPE, PAYEE_SCOPE_PREFIX
from modules.payments.context_builder import parse_candidate, rebuild_context
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.errors import (
    BillNotReviewableError,
    DecisionMissingError,
    RunNotFoundError,
)
from modules.payments.events import EXTRACTION_FAILED_STEP, NOT_A_BILL_STEP
from modules.payments.fx import current_period
from modules.payments.repository import RunsRepository
from modules.payments.rules import decide
from modules.payments.runner import PAYMENTS_AGENT_NAME, run_execution
from modules.payments.settlement import (
    RESTART_INTERRUPTION_EXPLANATION,
    fail_closed,
    settle,
)
from modules.payments.trace import serialize_messages

if TYPE_CHECKING:
    from clients.files import FilesClient

logger = get_logger(__name__)

INTERRUPTED_BILL_STATUSES = (BillStatus.DECIDING, BillStatus.APPROVING)
REVIEW_WAIVED_EFFECTS = frozenset({RuleEffect.REVIEW})
REJECTION_EXPLANATION_PREFIX = "Rejected by a person: "
NO_RESERVED_USD = Decimal("0")
QUARANTINED_INTAKE_STATUSES = frozenset(
    {EvidenceIntakeStatus.MALWARE, EvidenceIntakeStatus.SCAN_FAILED}
)
CHECKPOINT_MESSAGES_CHANNEL = "messages"


class PaymentsService:
    def __init__(
        self,
        repository: RunsRepository,
        registry: ExecutionRegistry,
        dependencies: PaymentRunDependencies,
        files: "FilesClient",
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._dependencies = dependencies
        self._files = files

    async def start_run(self, trigger: PaymentRunTrigger, owner: CurrentUser) -> PaymentRunAccepted:
        source = await self._dependencies.bills.get_source(owner.user_id, trigger.bill_source_id)
        await self._repository.link_source_files(source.source_id, trigger.evidence)
        previous_run = await self._decided_run(source)
        if previous_run is not None:
            return PaymentRunAccepted(
                run_id=previous_run.run_id, status=previous_run.status, duplicate=True
            )
        run_id, is_new_run = await self._repository.insert_run(
            agent=PAYMENTS_AGENT_NAME,
            owner_id=owner.user_id,
            file_id=source.file_id,
            bill_source_id=source.source_id,
        )
        if is_new_run:
            self._registry.spawn(
                run_id,
                run_execution(run_id, owner, source.source_id, self._dependencies),
                owner_id=owner.user_id,
            )
            logger.info("payment_run_started", run_id=run_id, bill_source_id=source.source_id)
        return PaymentRunAccepted(run_id=run_id, status=RunStatus.PENDING, duplicate=not is_new_run)

    async def start_file_run(
        self,
        owner: CurrentUser,
        file_id: UUID,
        source_type: BillSourceType,
        source_ref: str,
        body_text: str = "",
    ) -> PaymentRunAccepted:
        intake = await self._files.ingest_stored_file(owner, file_id)
        if intake.status in QUARANTINED_INTAKE_STATUSES:
            raise FileQuarantinedError
        if intake.status is EvidenceIntakeStatus.UNREADABLE:
            raise UnsafeArchiveError
        registration = await self._dependencies.bills.register_source(
            BillSourceIntake(
                owner_id=owner.user_id,
                source_type=source_type,
                source_ref=source_ref,
                sender=owner.email,
                body_text=body_text,
                file_id=intake.primary_file_id,
                attachment_sha256=intake.primary_sha256,
            )
        )
        accepted = await self.start_run(
            PaymentRunTrigger(
                bill_source_id=registration.source.source_id,
                evidence=intake.evidence if registration.is_new else [],
            ),
            owner,
        )
        is_duplicate = not registration.is_new or accepted.duplicate
        return accepted.model_copy(update={"duplicate": is_duplicate})

    async def get_run(self, run_id: UUID, owner: CurrentUser) -> PaymentRunStatus:
        run = await self._repository.get_run(run_id, owner.user_id)
        if run is None:
            raise RunNotFoundError
        events = await self._repository.list_events(run_id)
        decision = await self._bill_decision(owner, run.bill_id) if run.bill_id else None
        source_ids = [run.bill_source_id] if run.bill_source_id else []
        return PaymentRunStatus(
            run_id=run.run_id,
            status=run.status,
            error=run.error,
            events=events,
            decision=decision,
            is_bill=_is_bill(run, events),
            extraction_failed=_has_step(events, EXTRACTION_FAILED_STEP),
            evidence=await self._evidence(owner, source_ids),
        )

    async def list_bills(
        self, owner: CurrentUser, status: BillStatus | None
    ) -> list[BillDecisionView]:
        bills = await self._dependencies.bills.list_bills(owner.user_id, status)
        decisions = await self._dependencies.ledger.latest_decisions(
            [bill.bill_id for bill in bills]
        )
        return [
            _to_decision_view(bill, decisions[bill.bill_id])
            for bill in bills
            if bill.bill_id in decisions
        ]

    async def get_bill(self, owner: CurrentUser, bill_id: UUID) -> BillDetail:
        bill = await self._dependencies.bills.get_bill(owner.user_id, bill_id)
        history = await self._dependencies.ledger.decision_history(bill_id)
        if not history:
            raise DecisionMissingError
        sources = await self._dependencies.bills.list_sources_for_bill(owner.user_id, bill_id)
        payment = await self._dependencies.ledger.payment_for_bill(bill_id)
        return BillDetail(
            decision=_to_decision_view(bill, history[0]),
            history=[_to_decision_view(bill, decision) for decision in history],
            sources=[_to_source_view(source) for source in sources],
            payment=_to_payment_view(payment) if payment else None,
            evidence=await self._evidence(owner, [source.source_id for source in sources]),
        )

    async def approve(
        self, owner: CurrentUser, bill_id: UUID, request: ReviewActionRequest
    ) -> BillDecisionView:
        bill = await self._claim_review(owner, bill_id, BillStatus.APPROVING)
        policy = None
        try:
            policy = await self._dependencies.policy.get_policy(owner)
            context = await rebuild_context(self._dependencies, bill, policy)
            evaluation = decide(replace(context, waived_effects=REVIEW_WAIVED_EFFECTS))
            decision = await settle(
                self._dependencies,
                None,
                bill,
                context,
                evaluation,
                actor=DecisionActor.HUMAN,
                from_status=BillStatus.APPROVING,
                actor_user_id=owner.user_id,
                note=request.note,
            )
        except Exception:
            logger.exception("bill_review_approval_failed", bill_id=bill_id)
            await fail_closed(self._dependencies, None, bill, policy)
        else:
            logger.info("bill_review_approved", bill_id=bill_id, verdict=decision.verdict)
        return await self._require_bill_decision(owner, bill_id)

    async def reject(
        self, owner: CurrentUser, bill_id: UUID, request: ReviewActionRequest
    ) -> BillDecisionView:
        await self._claim_review(owner, bill_id, BillStatus.REJECTED)
        latest = await self._dependencies.ledger.latest_decision(bill_id)
        await self._dependencies.ledger.append_decision(
            DecisionRecord(
                bill_id=bill_id,
                run_id=None,
                actor=DecisionActor.HUMAN,
                actor_user_id=owner.user_id,
                verdict=Verdict.HOLD,
                rule_results=latest.rule_results if latest else [],
                checker=latest.checker if latest else None,
                explanation=f"{REJECTION_EXPLANATION_PREFIX}{request.note}",
                policy_id=latest.policy_id if latest else None,
                policy_version=latest.policy_version if latest else None,
                note=request.note,
            )
        )
        logger.info("bill_review_rejected", bill_id=bill_id)
        return await self._require_bill_decision(owner, bill_id)

    async def budget_usage(self, owner: CurrentUser, period: str | None) -> list[BudgetUsageView]:
        usage_period = period or current_period(datetime.now(UTC).date())
        policy = await self._dependencies.policy.get_policy(owner)
        payees = await self._dependencies.policy.list_payees(owner)
        reserved = await self._dependencies.ledger.budget_usage(owner.user_id, usage_period)
        limits: dict[str, Decimal | None] = {GLOBAL_SCOPE: policy.monthly_budget_usd}
        for category, budget in policy.category_monthly_budgets_usd.items():
            limits[f"{CATEGORY_SCOPE_PREFIX}{category}"] = budget
        for payee in payees:
            if payee.monthly_budget_usd is not None:
                limits[f"{PAYEE_SCOPE_PREFIX}{payee.payee_id}"] = payee.monthly_budget_usd
        scopes = list(dict.fromkeys([*limits, *reserved]))
        return [
            BudgetUsageView(
                scope=scope,
                limit_usd=limits.get(scope),
                reserved_usd=reserved.get(scope, NO_RESERVED_USD),
            )
            for scope in scopes
        ]

    async def recover_unfinished_payments(self) -> None:
        ledger = self._dependencies.ledger
        reserved_payments = await ledger.reserved_payments()
        for payment in reserved_payments:
            await ledger.execute(payment.payment_id)
        interrupted_bills = await self._dependencies.bills.stuck_bills(INTERRUPTED_BILL_STATUSES)
        failed_count = 0
        for bill in interrupted_bills:
            try:
                await fail_closed(
                    self._dependencies, None, bill, None, RESTART_INTERRUPTION_EXPLANATION
                )
            except Exception:
                failed_count += 1
                logger.exception("unfinished_bill_recovery_failed", bill_id=bill.bill_id)
        if reserved_payments or interrupted_bills:
            logger.warning(
                "unfinished_bills_recovered",
                executed_payments=len(reserved_payments),
                interrupted_bills=len(interrupted_bills),
                failed_count=failed_count,
            )

    async def fail_unfinished(self, reason: str) -> None:
        failed_count = await self._repository.fail_unfinished(reason)
        if failed_count:
            logger.warning("unfinished_runs_swept", failed_count=failed_count)

    async def run_trace(self, owner: CurrentUser, run_id: UUID) -> RunTraceView:
        await self.get_run(run_id, owner)
        checkpointer = self._dependencies.checkpointer
        checkpoint_tuple = (
            await checkpointer.aget_tuple(thread_config(run_id)) if checkpointer else None
        )
        if checkpoint_tuple is None:
            return RunTraceView(run_id=run_id, is_available=False, checkpoint_id=None, messages=[])
        messages = checkpoint_tuple.checkpoint["channel_values"].get(
            CHECKPOINT_MESSAGES_CHANNEL, []
        )
        system_prompt = self._dependencies.prompts.get_text_prompt(PromptId.PAYMENTS_AGENT)
        return RunTraceView(
            run_id=run_id,
            is_available=True,
            checkpoint_id=checkpoint_tuple.config["configurable"].get("checkpoint_id"),
            messages=serialize_messages(messages, system_prompt),
        )

    async def cancel_owner(self, owner_id: UUID) -> int:
        cancelled_count = await self._registry.cancel_owner(owner_id)
        if cancelled_count:
            logger.info("payment_runs_cancelled", owner_id=owner_id, count=cancelled_count)
        return cancelled_count

    async def purge_run_threads(self, run_ids: list[UUID]) -> int:
        checkpointer = self._dependencies.checkpointer
        if checkpointer is None:
            return 0
        purged_count = 0
        for run_id in run_ids:
            try:
                await checkpointer.adelete_thread(str(run_id))
            except Exception:
                logger.warning("run_thread_purge_failed", run_id=run_id, exc_info=True)
                continue
            purged_count += 1
        return purged_count

    async def shutdown(self) -> None:
        await self._registry.shutdown()

    async def _evidence(
        self, owner: CurrentUser, bill_source_ids: list[UUID]
    ) -> list[EvidenceFileView]:
        evidence_links = await self._repository.list_evidence(bill_source_ids)
        return await self._files.evidence_views(owner, evidence_links)

    async def _decided_run(self, source: BillSourceRecord) -> PaymentRunRecord | None:
        if source.bill_id is None:
            return None
        return await self._repository.latest_run_for_source(source.source_id)

    async def _claim_review(
        self, owner: CurrentUser, bill_id: UUID, target: BillStatus
    ) -> BillRecord:
        bill = await self._dependencies.bills.get_bill(owner.user_id, bill_id)
        if bill.status is not BillStatus.REVIEW:
            raise BillNotReviewableError
        return await self._dependencies.bills.transition(
            owner.user_id, bill_id, BillStatus.REVIEW, target
        )

    async def _bill_decision(self, owner: CurrentUser, bill_id: UUID) -> BillDecisionView | None:
        bill = await self._dependencies.bills.get_bill(owner.user_id, bill_id)
        decision = await self._dependencies.ledger.latest_decision(bill_id)
        if decision is None:
            return None
        return _to_decision_view(bill, decision)

    async def _require_bill_decision(self, owner: CurrentUser, bill_id: UUID) -> BillDecisionView:
        decision_view = await self._bill_decision(owner, bill_id)
        if decision_view is None:
            raise DecisionMissingError
        return decision_view


def _has_step(events: list[PaymentRunEvent], step: str) -> bool:
    return any(event.step == step for event in events)


def _is_bill(run: PaymentRunRecord, events: list[PaymentRunEvent]) -> bool | None:
    if _has_step(events, NOT_A_BILL_STEP):
        return False
    if run.bill_id is not None:
        return True
    return None


def _to_decision_view(bill: BillRecord, decision: DecisionRecord) -> BillDecisionView:
    return BillDecisionView(
        bill_id=bill.bill_id,
        verdict=decision.verdict,
        status=bill.status,
        explanation=decision.explanation,
        rule_results=decision.rule_results,
        checker=decision.checker,
        candidate=parse_candidate(bill),
        payee_id=bill.payee_id,
        payee_name=bill.payee_name,
        amount=bill.amount,
        currency=bill.currency,
        amount_usd=bill.amount_usd,
        fx_usd_per_unit=bill.fx_usd_per_unit,
        fx_rate_date=bill.fx_rate_date,
        fx_source=bill.fx_source,
        category=bill.category,
        duplicate_of_bill_id=bill.duplicate_of_bill_id,
        actor=decision.actor,
        note=decision.note,
        decided_at=decision.created_at,
        can_approve=bill.status is BillStatus.REVIEW,
    )


def _to_source_view(source: BillSourceRecord) -> BillSourceView:
    return BillSourceView(
        source_id=source.source_id,
        source_type=source.source_type,
        source_ref=source.source_ref,
        sender=source.sender,
        file_id=source.file_id,
        inbox_email_id=source.inbox_email_id,
        received_at=source.received_at,
        created_at=source.created_at,
    )


def _to_payment_view(payment: PaymentRecord) -> PaymentView:
    return PaymentView(
        payment_id=payment.payment_id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        amount_usd=payment.amount_usd,
        fx_usd_per_unit=payment.fx_usd_per_unit,
        fx_rate_date=payment.fx_rate_date,
        fx_source=payment.fx_source,
        period=payment.period,
        rail_reference=payment.rail_reference,
        executed_at=payment.executed_at,
    )
