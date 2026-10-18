from uuid import UUID

from contracts.bills import BillRecord, BillStatus
from contracts.payment_policy import PaymentPolicy
from contracts.payments import (
    CheckerAssessment,
    DecisionActor,
    DecisionRecord,
    RuleEffect,
    RuleResult,
    Verdict,
)
from core.logging_config import get_logger
from modules.bills import BillStateConflictError
from modules.payments.budget import budget_charges, describe_scope
from modules.payments.dependencies import PaymentRunDependencies
from modules.payments.errors import BudgetExhaustedError
from modules.payments.explain import explain
from modules.payments.fx import current_period
from modules.payments.ledger_repository import ReservationRequest
from modules.payments.presentation import bill_label
from modules.payments.rules import DecisionContext, RuleEvaluation, rule_result

logger = get_logger(__name__)

VERDICT_STATUS = {
    Verdict.PAY: BillStatus.PAID,
    Verdict.HOLD: BillStatus.HELD,
    Verdict.REVIEW: BillStatus.REVIEW,
}
BILL_STATUS_WORDS = {
    BillStatus.DECIDING: "being decided",
    BillStatus.PAID: "paid",
    BillStatus.HELD: "held",
    BillStatus.REVIEW: "in review",
    BillStatus.APPROVING: "being approved",
    BillStatus.REJECTED: "rejected",
    BillStatus.DUPLICATE: "a duplicate",
}
UNPAYABLE_REASON = (
    "It cannot be paid without a confirmed positive amount and currency; fix the invoice and "
    "resend it."
)
TECHNICAL_ERROR_EXPLANATION = (
    "In review: a technical error happened while deciding, and the agent does not pay without "
    "finishing its checks."
)
RESTART_INTERRUPTION_EXPLANATION = (
    "In review: the decision was interrupted by a restart before it finished."
)
RECOVERED_PAYMENT_EXPLANATION = "Paid: the reserved payment completed after an interruption."
DUPLICATE_DATE_FORMAT = "%b %d, %Y"


async def settle(
    dependencies: PaymentRunDependencies,
    run_id: UUID | None,
    bill: BillRecord,
    context: DecisionContext,
    evaluation: RuleEvaluation,
    actor: DecisionActor,
    from_status: BillStatus,
    checker: CheckerAssessment | None = None,
    actor_user_id: UUID | None = None,
    note: str | None = None,
) -> DecisionRecord:
    verdict, results = evaluation.verdict, list(evaluation.results)
    reservation = None
    if verdict is Verdict.PAY:
        planned_payment = _reservation_for(bill, context)
        if isinstance(planned_payment, RuleResult):
            verdict, results = Verdict.HOLD, [*results, planned_payment]
        else:
            reservation = planned_payment
    decision = DecisionRecord(
        bill_id=bill.bill_id,
        run_id=run_id,
        actor=actor,
        actor_user_id=actor_user_id,
        verdict=verdict,
        rule_results=results,
        checker=checker,
        explanation=explain(verdict, results, context),
        policy_id=context.policy.policy_id,
        policy_version=context.policy.version,
        note=note,
    )
    ledger = dependencies.ledger
    try:
        settled = await ledger.commit_settlement(
            bill.owner_id, bill.bill_id, from_status, VERDICT_STATUS[verdict], reservation, decision
        )
    except BudgetExhaustedError as exhausted:
        logger.info("budget_exhausted", bill_id=bill.bill_id, scope=exhausted.scope)
        held_decision = _held_for_budget(decision, exhausted, context)
        settled = await ledger.commit_settlement(
            bill.owner_id, bill.bill_id, from_status, BillStatus.HELD, None, held_decision
        )
    logger.info("bill_decided", bill_id=bill.bill_id, verdict=settled.verdict, actor=actor)
    return settled


async def record_duplicate(
    dependencies: PaymentRunDependencies,
    run_id: UUID,
    bill: BillRecord,
    original: BillRecord,
    policy: PaymentPolicy,
) -> DecisionRecord:
    original_label = bill_label(original.invoice_number, original.bill_id)
    duplicate_reason = (
        f"This invoice ({original_label}) was already received on "
        f"{original.created_at:{DUPLICATE_DATE_FORMAT}}; the original is "
        f"{BILL_STATUS_WORDS[original.status]}."
    )
    duplicate_result = rule_result(
        "DUP", RuleEffect.HOLD, duplicate_reason, {"original_bill": str(original.bill_id)}
    )
    return await dependencies.ledger.append_decision(
        DecisionRecord(
            bill_id=bill.bill_id,
            run_id=run_id,
            actor=DecisionActor.AGENT,
            actor_user_id=None,
            verdict=Verdict.HOLD,
            rule_results=[duplicate_result],
            checker=None,
            explanation=f"Held: exact duplicate. {duplicate_reason}",
            policy_id=policy.policy_id,
            policy_version=policy.version,
        )
    )


async def fail_closed(
    dependencies: PaymentRunDependencies,
    run_id: UUID | None,
    bill: BillRecord,
    policy: PaymentPolicy | None,
    explanation: str = TECHNICAL_ERROR_EXPLANATION,
) -> None:
    payment = await dependencies.ledger.payment_for_bill(bill.bill_id)
    if payment is not None:
        await dependencies.ledger.execute(payment.payment_id)
        await record_recovered_payment(dependencies, bill)
        return
    await record_technical_review(dependencies, run_id, bill, policy, explanation)


async def record_technical_review(
    dependencies: PaymentRunDependencies,
    run_id: UUID | None,
    bill: BillRecord,
    policy: PaymentPolicy | None,
    explanation: str = TECHNICAL_ERROR_EXPLANATION,
) -> None:
    await dependencies.ledger.append_decision(
        DecisionRecord(
            bill_id=bill.bill_id,
            run_id=run_id,
            actor=DecisionActor.AGENT,
            actor_user_id=None,
            verdict=Verdict.REVIEW,
            rule_results=[rule_result("ERR", RuleEffect.REVIEW, explanation)],
            checker=None,
            explanation=explanation,
            policy_id=policy.policy_id if policy else None,
            policy_version=policy.version if policy else None,
        )
    )
    try:
        await dependencies.bills.transition(
            bill.owner_id, bill.bill_id, bill.status, BillStatus.REVIEW
        )
    except BillStateConflictError:
        logger.warning("bill_review_transition_skipped", bill_id=bill.bill_id)


async def record_recovered_payment(dependencies: PaymentRunDependencies, bill: BillRecord) -> None:
    await dependencies.ledger.append_decision(
        DecisionRecord(
            bill_id=bill.bill_id,
            run_id=None,
            actor=DecisionActor.AGENT,
            actor_user_id=None,
            verdict=Verdict.PAY,
            rule_results=[rule_result("PAY", RuleEffect.PASS, RECOVERED_PAYMENT_EXPLANATION)],
            checker=None,
            explanation=RECOVERED_PAYMENT_EXPLANATION,
            policy_id=None,
            policy_version=None,
        )
    )
    await dependencies.bills.transition(bill.owner_id, bill.bill_id, bill.status, BillStatus.PAID)


def _reservation_for(bill: BillRecord, context: DecisionContext) -> ReservationRequest | RuleResult:
    candidate = context.candidate
    is_payable = (
        context.amount_usd is not None
        and context.amount_usd > 0
        and candidate.amount is not None
        and candidate.amount > 0
        and candidate.currency is not None
    )
    if not is_payable:
        return rule_result("PAY", RuleEffect.HOLD, UNPAYABLE_REASON)
    payee = context.match.payee
    return ReservationRequest(
        owner_id=bill.owner_id,
        bill_id=bill.bill_id,
        payee_id=payee.payee_id if payee else None,
        amount=candidate.amount,
        currency=bill.currency,
        amount_usd=context.amount_usd,
        fx_usd_per_unit=bill.fx_usd_per_unit,
        fx_rate_date=bill.fx_rate_date,
        fx_source=bill.fx_source,
        category=candidate.category,
        period=current_period(context.today),
        charges=budget_charges(context.policy, payee, candidate.category),
    )


def _held_for_budget(
    decision: DecisionRecord, exhausted: BudgetExhaustedError, context: DecisionContext
) -> DecisionRecord:
    scope_description = describe_scope(exhausted.scope, context.match.payee)
    budget_blocker = rule_result(
        "R14",
        RuleEffect.HOLD,
        f"{scope_description.capitalize()} budget exhausted while reserving the payment.",
        {"scope": exhausted.scope},
    )
    held_results = [*decision.rule_results, budget_blocker]
    return decision.model_copy(
        update={
            "verdict": Verdict.HOLD,
            "rule_results": held_results,
            "explanation": explain(Verdict.HOLD, held_results, context),
        }
    )
