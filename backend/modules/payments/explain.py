from decimal import Decimal

from contracts.payments import RuleEffect, RuleResult, Verdict
from modules.payments.budget import GLOBAL_SCOPE
from modules.payments.presentation import format_amount, format_usd
from modules.payments.rules import DecisionContext

EFFECT_ORDER = {RuleEffect.HOLD: 0, RuleEffect.REVIEW: 1}


def explain(verdict: Verdict, results: list[RuleResult], context: DecisionContext) -> str:
    failing = sorted(
        (result for result in results if result.effect is not RuleEffect.PASS),
        key=lambda result: EFFECT_ORDER[result.effect],
    )
    if verdict is Verdict.PAY:
        return f"{_paid_headline(results, failing)} {_payment_summary(context)}"
    blocking = [result for result in failing if result.effect is RuleEffect.HOLD]
    if verdict is Verdict.HOLD:
        headline = f"Frenada: {len(blocking)} regla(s) bloquean el pago."
        reasons = blocking
    else:
        headline = f"En revisión: {len(failing)} punto(s) necesitan una persona."
        reasons = failing
    return " ".join([headline, *(result.reason for result in reasons)])


def _paid_headline(results: list[RuleResult], failing: list[RuleResult]) -> str:
    if failing:
        return f"Pagada con aprobación humana: se aceptaron {len(failing)} punto(s) en revisión."
    return f"Pagada automáticamente: cumple las {len(results)} reglas."


def _payment_summary(context: DecisionContext) -> str:
    candidate = context.candidate
    payee_name = context.match.payee.display_name if context.match.payee else candidate.payee_name
    amount_text = (
        f"{candidate.currency} {format_amount(candidate.amount)}"
        if candidate.amount is not None and candidate.currency
        else "monto sin leer"
    )
    summary = f"{payee_name}: {amount_text}"
    if context.amount_usd is not None and candidate.currency != "USD":
        summary += f" (≈ {format_usd(context.amount_usd)})"
    if candidate.category:
        summary += f", categoría {candidate.category}"
    if context.amount_usd is not None:
        global_reserved = context.budget.get(GLOBAL_SCOPE, Decimal("0")) + context.amount_usd
        remaining = context.policy.monthly_budget_usd - global_reserved
        summary += f". Presupuesto mensual restante: {format_usd(remaining)}"
    return f"{summary}."
