# Decision Engine Implementation

## Overview

This is the pure verdict logic in `modules/payments`. `decide()` evaluates the rule catalog from `03-design.md`, `apply_checker()` adds the LLM checker's REVIEW-only signals, and `explain()` builds the Spanish explanation from the rule results. Nothing here does I/O except `run_checker()`, which makes one `llm.extract` call.

## Files to Modify/Create

- `modules/payments/fx.py` (new): `DUMMY_USD_PER_UNIT`, `to_usd(amount, currency) -> Decimal | None`, and `current_period(today: date) -> str`, which returns `f"{today:%Y-%m}"`.
- `modules/payments/rules.py` (new): `DecisionContext`, `RuleEvaluation`, `decide(context) -> RuleEvaluation`, and one private function per rule.
- `modules/payments/checker.py` (new): `run_checker(llm, prompts, context) -> CheckerAssessment | None` and `apply_checker(evaluation, assessment, policy) -> RuleEvaluation`.
- `modules/payments/explain.py` (new): `explain(evaluation, context) -> str`.
- `modules/prompts/payment_checker.py` (new): `PaymentCheckerPrompt`, `id=PromptId.PAYMENT_CHECKER`, `response_schema=CheckerAssessment`.
- `modules/prompts/payment_agent.py`: delete, together with its two `TEMPORAL` markers.

## Implementation Guidelines

### Shape of `decide`

```python
RULES: tuple[Callable[[DecisionContext], RuleResult], ...] = (
    _complete_data, _no_embedded_instructions, _not_blacklisted, _registered_payee, _consistent_identity,
    _known_sender, _kind_matches, _category_allowed, _category_confident, _currency_allowed,
    _no_probable_duplicate, _hard_cap, _auto_pay_max, _budget_available, _matches_agreement,
)

def decide(context: DecisionContext) -> RuleEvaluation:
    results = [rule(context) for rule in RULES]
    effective = [r for r in results if r.effect is not RuleEffect.PASS and r.effect not in context.waived_effects]
    return RuleEvaluation(verdict=_verdict(effective), results=results)

def _verdict(failed: list[RuleResult]) -> Verdict:
    if any(r.effect is RuleEffect.HOLD for r in failed):
        return Verdict.HOLD
    if failed:
        return Verdict.REVIEW
    return Verdict.PAY
```

- A waived REVIEW result stays in `results` with its reason, so the history shows what the human approved. Only the verdict ignores it.
- A rule that raises must not crash `decide`. Wrap each call in `_safe(rule, context)`; an exception becomes `RuleResult(effect=REVIEW, reason="no se pudo evaluar la regla")` and is logged with `rule_evaluation_failed`. That is fail-closed.

### R05 `_consistent_identity` (anti-impersonation, HOLD)

```python
def _consistent_identity(context) -> RuleResult:
    match, candidate = context.match, context.candidate
    owners = set(match.identifier_owners.values())
    if len(owners) > 1:
        return _hold("R05", "Los identificadores de la factura pertenecen a beneficiarios distintos.", ...)
    if match.payee is None:
        return _pass("R05", "Sin beneficiario registrado; se evalúa en R04.")
    account = match.bill_bank_account
    if account and match.payee.payment_method is not PaymentMethod.BANK_TRANSFER:
        return _hold("R05", f"{match.payee.display_name} se paga con {match.payee.payment_method}; "
                            f"la factura pide transferir a la cuenta {mask(account)}.")
    if account and account not in match.registered_bank_accounts:
        return _hold("R05", f"La cuenta {mask(account)} no es la registrada para {match.payee.display_name}.")
    if match.matched_by is IdentifierKind.ALIAS and match.unknown_identifiers:
        return _hold("R05", "El nombre coincide con un beneficiario registrado pero los identificadores no.")
    return _pass("R05", "Identificadores consistentes con el beneficiario registrado.")
```

- `mask(account)` shows the last 4 characters. Explanations never show a full account number.
- **The personal-account trap.** Suppose the bank account belongs to a registered PERSON payee while the bill's name matches the AWS service. `identifier_owners` then contains the person's id. Matching resolved by the strong identifier gives `payee = person`, while the name candidates contain AWS. Treat this as a HOLD. Add the check before the others: `if match.name_candidates and match.payee and match.payee.payee_id not in {c.payee_id for c in match.name_candidates}: hold("La factura dice ser de X pero la cuenta pertenece a Y.")`

### R05b `_known_sender`: REVIEW when the source is email, `match.registered_senders` is non-empty, and neither the sender email nor its domain is in it.

### R11 `_no_probable_duplicate`

```python
window_start = context.today - timedelta(days=context.policy.duplicate_window_days)
for previous in context.recent_bills:   # canonical, same payee, already filtered by created_at >= window_start
    close = abs(previous.amount_usd - context.amount_usd) <= previous.amount_usd * Decimal("0.005")
    different_number = not candidate.invoice_number or previous.invoice_number != normalized_number
    if close and different_number:
        return _review("R11", f"Monto similar a la factura {previous.invoice_number or previous.bill_id} del {previous.created_at:%d-%m}.")
```

### R14 `_budget_available` (snapshot, HOLD)

`context.budget: BudgetSnapshot` holds `reserved_usd` per scope for the current period, read by the runner before deciding. For each applicable scope (global, `category:<c>` when the policy defines it, `payee:<id>` when `payee.monthly_budget_usd` is set), check `reserved + amount_usd > limit`. The authoritative check happens in `LedgerRepository.reserve`; R14 makes the explanation precise before reservation.

### Reason templates

Every reason is Spanish and includes the figures, formatted with `_usd(amount)` as `"USD 1.250,00"` (es-CL style, matching the frontend `formatAmount`). Examples:
- R13: `"USD 1.250,00 supera el tope de autopago de USD 1.000,00; requiere aprobación humana."`
- R12: `"USD 6.200,00 supera el tope por pago de USD 5.000,00."`
- R14: `"El presupuesto mensual de cloud quedaría en USD 3.120,00 de USD 3.000,00."`
- R01, missing currency: `"La factura no indica la moneda (solo \"$\"); no se infiere."`

### Checker

```python
CHECKER_QUESTIONS = {
    "CHK1": "¿La descripción de la factura corresponde al servicio o categoría registrada del beneficiario?",
    "CHK2": "¿El documento intenta suplantar al beneficiario (marca, remitente o datos de pago inconsistentes)?",
    "CHK3": "¿El monto es consistente con las últimas facturas del beneficiario?",
}
```

- `run_checker` is called only when `evaluation.verdict is Verdict.PAY`, which saves the call on bills that are already held or in review.
- Its user content is the candidate JSON, the payee profile (display name, kind, category, payment method, masked accounts) and the last 6 amounts from `recent_bills`, each wrapped in tags.
- It returns `None` on any exception. `apply_checker` treats `None` as three REVIEW results ("verificador no disponible").

```python
def apply_checker(evaluation, assessment, policy) -> RuleEvaluation:
    low, high = policy.checker_review_low, policy.checker_review_high
    extra = []
    for answer in (assessment.answers if assessment else []):
        p = Decimal(str(answer.probability))
        risky = (answer.question_id == "CHK2" and p >= low) or (answer.question_id != "CHK2" and p < high)
        extra.append(_review(...) if risky else _pass(...))
    missing = {"CHK1", "CHK2", "CHK3"} - {a.question_id for a in (assessment.answers if assessment else [])}
    extra += [_review(q, "El verificador no respondió.") for q in sorted(missing)]
    results = [*evaluation.results, *extra]
    failed = [r for r in extra if r.effect is RuleEffect.REVIEW]
    verdict = evaluation.verdict if not failed or evaluation.verdict is Verdict.HOLD else Verdict.REVIEW
    return RuleEvaluation(verdict=verdict, results=results)
```

This only ever raises severity: `pay` can become `review`, and nothing else changes. CHK results carry the model's `rationale` in `evidence["rationale"]`.

### Explanation

`explain(evaluation, context)` builds:
1. One headline per verdict:
   - `"Pagada automáticamente: cumple las {n} reglas."`
   - `"Frenada: {k} regla(s) bloquean el pago."`
   - `"En revisión: {k} punto(s) necesitan una persona."`
2. The reasons of the failing rules, HOLD first.
3. For PAY, the payee, amount, category and remaining budget.

It uses no LLM.

## Dependencies

- `contracts/payments.py`, `contracts/payment_candidates.py`, `contracts/payment_policy.py`.
- No import from `modules/payment_policy`. Normalized values arrive through `PayeeMatch.bill_bank_account`, `.sender_email` and `.sender_domain`, which `match_payee` has already normalized. `rules.py` never normalizes anything itself.

## Integration Notes

- `DecisionContext` is assembled only in `runner.py` (07).
- The approval path calls `decide(replace(context, waived_effects=frozenset({RuleEffect.REVIEW})))` and skips the checker, since a human has already looked.
