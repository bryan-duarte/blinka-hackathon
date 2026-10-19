from decimal import Decimal

from contracts.bills import BillRecord
from contracts.fx import USD, FxSource
from contracts.payments import RuleEffect, RuleResult, Verdict
from modules.payments.budget import GLOBAL_SCOPE
from modules.payments.presentation import format_amount, format_rate, format_usd
from modules.payments.rules import DecisionContext

EFFECT_ORDER = {RuleEffect.HOLD: 0, RuleEffect.REVIEW: 1}
FX_SOURCE_LABELS = {
    FxSource.IDENTITY: "USD",
    FxSource.OPEN_ER_API: "live rate",
    FxSource.CACHED: "cached rate",
    FxSource.STATIC_FALLBACK: "fallback rate",
    FxSource.SEED: "historical rate",
}
UNREAD_AMOUNT_TEXT = "amount not read"


def explain(verdict: Verdict, results: list[RuleResult], context: DecisionContext) -> str:
    failing = sorted(
        (result for result in results if result.effect is not RuleEffect.PASS),
        key=lambda result: EFFECT_ORDER[result.effect],
    )
    if verdict is Verdict.PAY:
        return f"{_paid_headline(results, failing)} {_payment_summary(context)}"
    blocking = [result for result in failing if result.effect is RuleEffect.HOLD]
    if verdict is Verdict.HOLD:
        headline = f"Held: {_count(len(blocking), 'rule blocks', 'rules block')} the payment."
        reasons = blocking
    else:
        headline = f"In review: {_count(len(failing), 'point needs', 'points need')} a person."
        reasons = failing
    return " ".join([headline, *(result.reason for result in reasons)])


def _count(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _paid_headline(results: list[RuleResult], failing: list[RuleResult]) -> str:
    if failing:
        accepted = _count(len(failing), "review point was", "review points were")
        return f"Paid with human approval: {accepted} accepted."
    return f"Paid automatically: passes all {len(results)} rules."


def _payment_summary(context: DecisionContext) -> str:
    candidate = context.candidate
    payee_name = context.match.payee.display_name if context.match.payee else candidate.payee_name
    has_amount = candidate.amount is not None and bool(candidate.currency)
    amount_text = (
        _amount_text(context.bill, candidate.amount, candidate.currency or "", context.amount_usd)
        if has_amount
        else UNREAD_AMOUNT_TEXT
    )
    summary = f"{payee_name}: {amount_text}"
    if candidate.category:
        summary += f", category {candidate.category}"
    if context.amount_usd is not None:
        global_reserved = context.budget.get(GLOBAL_SCOPE, Decimal("0")) + context.amount_usd
        remaining = context.policy.monthly_budget_usd - global_reserved
        summary += f". Monthly budget left: {format_usd(remaining)}"
    return f"{summary}."


def _amount_text(
    bill: BillRecord, amount: Decimal, currency: str, amount_usd: Decimal | None
) -> str:
    original = f"{format_amount(amount)} {currency}"
    has_conversion = (
        currency.upper() != USD
        and amount_usd is not None
        and bill.fx_usd_per_unit is not None
        and bill.fx_rate_date is not None
        and bill.fx_source is not None
    )
    if not has_conversion:
        return original
    return (
        f"{original} ≈ {format_usd(amount_usd)} (rate {format_rate(bill.fx_usd_per_unit)} on "
        f"{bill.fx_rate_date:%b %d, %Y}, {FX_SOURCE_LABELS[bill.fx_source]})"
    )
