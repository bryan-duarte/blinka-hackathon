from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from contracts.bills import BillRecord, BillSourceRecord, BillSourceType, BillSummary
from contracts.payment_candidates import BillClassification, PaymentCandidateBase
from contracts.payment_policy import (
    BlacklistHit,
    IdentifierKind,
    PayeeKind,
    PayeeMatch,
    PayeeStatus,
    PaymentMethod,
    PaymentPolicy,
)
from contracts.payments import RuleEffect, RuleResult, Verdict
from core.logging_config import get_logger
from modules.payments.budget import budget_charges, describe_scope
from modules.payments.fx import names_currency_explicitly
from modules.payments.presentation import bill_label, format_usd, mask_account

logger = get_logger(__name__)

PERCENT = Decimal("100")
PROBABLE_DUPLICATE_TOLERANCE = Decimal("0.005")
SAME_CYCLE_DUE_DATE_DAYS = 10
EVIDENCE_QUOTE_MAX_CHARS = 160
REQUIRED_FIELD_LABELS = {
    "payee_name": "beneficiario",
    "amount": "monto",
    "currency": "moneda",
    "due_date": "fecha de vencimiento",
}
CATEGORY_LIKE_KINDS = frozenset({PayeeKind.SERVICE, PayeeKind.COMPANY})
NO_USD_AMOUNT_REASON = "No aplica: sin monto en USD."
MISSING_CURRENCY_PROBLEM = "la factura no indica la moneda de forma explícita; no se infiere"
IMPLICIT_CURRENCY_PROBLEM = (
    "la moneda leída no aparece escrita de forma explícita en la factura; no se infiere"
)
CURRENCY_FIELD = "currency"
RULE_FAILURE_REASON = "No se pudo evaluar la regla; se envía a revisión."
IDENTIFIER_LABELS = {
    IdentifierKind.TAX_ID: "El identificador tributario",
    IdentifierKind.BANK_ACCOUNT: "La cuenta",
    IdentifierKind.SERVICE_ACCOUNT_ID: "La cuenta de servicio",
    IdentifierKind.EMAIL: "El correo",
    IdentifierKind.DOMAIN: "El dominio",
    IdentifierKind.ALIAS: "El nombre",
}

RULE_NAMES = {
    "R01": "datos_completos",
    "R02": "sin_instrucciones",
    "R03": "no_bloqueado",
    "R04": "beneficiario_registrado",
    "R05": "identidad_consistente",
    "R05b": "remitente_conocido",
    "R06": "tipo_coincide",
    "R07": "categoria_permitida",
    "R08": "categoria_confiable",
    "R09": "moneda_permitida",
    "R11": "sin_duplicado_probable",
    "R12": "tope_por_pago",
    "R13": "tope_autopago",
    "R14": "presupuesto_disponible",
    "R17": "coincide_con_acuerdo",
    "CHK1": "servicio_coincide",
    "CHK2": "suplantacion",
    "CHK3": "monto_habitual",
    "DUP": "duplicado_exacto",
    "PAY": "pago_ejecutable",
    "ERR": "error_tecnico",
}

BudgetSnapshot = Mapping[str, Decimal]


@dataclass(frozen=True)
class DecisionContext:
    candidate: PaymentCandidateBase
    bill: BillRecord
    source: BillSourceRecord
    match: PayeeMatch
    policy: PaymentPolicy
    blacklist_hits: list[BlacklistHit]
    amount_usd: Decimal | None
    recent_bills: list[BillSummary]
    budget: BudgetSnapshot
    today: date
    classification: BillClassification | None = None
    waived_effects: frozenset[RuleEffect] = frozenset()


@dataclass(frozen=True)
class RuleEvaluation:
    verdict: Verdict
    results: list[RuleResult]


Rule = Callable[[DecisionContext], RuleResult]


def decide(context: DecisionContext) -> RuleEvaluation:
    results = [_safe(rule_id, rule, context) for rule_id, rule in RULES]
    return RuleEvaluation(verdict=verdict_for(results, context.waived_effects), results=results)


def verdict_for(
    results: list[RuleResult], waived_effects: frozenset[RuleEffect] = frozenset()
) -> Verdict:
    effective = [
        result
        for result in results
        if result.effect is not RuleEffect.PASS and result.effect not in waived_effects
    ]
    if any(result.effect is RuleEffect.HOLD for result in effective):
        return Verdict.HOLD
    if effective:
        return Verdict.REVIEW
    return Verdict.PAY


def rule_result(
    rule_id: str, effect: RuleEffect, reason: str, evidence: dict[str, str] | None = None
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        name=RULE_NAMES.get(rule_id, rule_id.lower()),
        effect=effect,
        reason=reason,
        evidence=evidence or {},
    )


def _safe(rule_id: str, rule: Rule, context: DecisionContext) -> RuleResult:
    try:
        return rule(context)
    except Exception:
        logger.exception("rule_evaluation_failed", rule_id=rule_id, bill_id=context.bill.bill_id)
        return rule_result(rule_id, RuleEffect.REVIEW, RULE_FAILURE_REASON)


def _complete_data(context: DecisionContext) -> RuleResult:
    candidate, policy = context.candidate, context.policy
    has_positive_amount = candidate.amount is not None and candidate.amount > 0
    present = {
        "payee_name": bool(candidate.payee_name),
        "amount": has_positive_amount,
        "due_date": candidate.due_date is not None,
    }
    problems = [
        f"falta {REQUIRED_FIELD_LABELS[field]}"
        for field, is_present in present.items()
        if not is_present
    ]
    if not candidate.currency:
        problems.append(MISSING_CURRENCY_PROBLEM)
    elif not _currency_has_explicit_evidence(candidate):
        problems.append(IMPLICIT_CURRENCY_PROBLEM)
    uncertain_fields = sorted(
        {
            REQUIRED_FIELD_LABELS[evidence.field]
            for evidence in candidate.evidence
            if evidence.field in REQUIRED_FIELD_LABELS
            and Decimal(str(evidence.confidence)) < policy.min_field_confidence
        }
    )
    if uncertain_fields:
        problems.append(f"lectura dudosa de {', '.join(uncertain_fields)}")
    classification = context.classification
    is_doubtful_classification = (
        classification is not None
        and Decimal(str(classification.confidence)) < policy.min_field_confidence
    )
    if is_doubtful_classification:
        problems.append("clasificación dudosa del documento")
    if problems:
        return rule_result("R01", RuleEffect.REVIEW, _sentence("; ".join(dict.fromkeys(problems))))
    return rule_result("R01", RuleEffect.PASS, "Beneficiario, monto, moneda y vencimiento leídos.")


def _no_embedded_instructions(context: DecisionContext) -> RuleResult:
    instructions = context.candidate.embedded_instructions
    if instructions:
        first_instruction = instructions[0][:EVIDENCE_QUOTE_MAX_CHARS]
        return rule_result(
            "R02",
            RuleEffect.HOLD,
            "La factura contiene instrucciones dirigidas al agente; no se siguen.",
            {"instruccion": first_instruction},
        )
    return rule_result("R02", RuleEffect.PASS, "Sin instrucciones dirigidas al agente.")


def _not_blacklisted(context: DecisionContext) -> RuleResult:
    payee = context.match.payee
    if context.blacklist_hits:
        hit = context.blacklist_hits[0]
        shown_value = _shown_identifier(hit.kind, hit.normalized_value)
        return rule_result(
            "R03",
            RuleEffect.HOLD,
            f"{IDENTIFIER_LABELS[hit.kind]} {shown_value} está en la lista negra: {hit.reason}.",
            {"tipo": str(hit.kind), "valor": shown_value},
        )
    if payee is not None and payee.status is PayeeStatus.BLACKLISTED:
        return rule_result(
            "R03", RuleEffect.HOLD, f"{payee.display_name} está bloqueado en el registro."
        )
    return rule_result("R03", RuleEffect.PASS, "Ningún dato de la factura está en la lista negra.")


def _registered_payee(context: DecisionContext) -> RuleResult:
    match = context.match
    if match.payee is not None:
        return rule_result(
            "R04", RuleEffect.PASS, f"Beneficiario registrado: {match.payee.display_name}."
        )
    if _identifiers_have_several_owners(match):
        reason = "Los identificadores apuntan a varios beneficiarios registrados."
    elif match.name_candidates:
        names = ", ".join(payee.display_name for payee in match.name_candidates)
        reason = f"Coincide por nombre con {names}, sin identificadores que lo confirmen."
    else:
        payee_name = context.candidate.payee_name or "sin nombre"
        reason = f"El beneficiario «{payee_name}» no está registrado."
    return rule_result("R04", RuleEffect.REVIEW, reason)


def _consistent_identity(context: DecisionContext) -> RuleResult:
    match, candidate = context.match, context.candidate
    payee = match.payee
    if _identifiers_have_several_owners(match):
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            "Los identificadores de la factura pertenecen a beneficiarios distintos.",
        )
    if payee is None:
        return rule_result("R05", RuleEffect.PASS, "Sin beneficiario registrado; se evalúa en R04.")
    claimed_payee_ids = {name_candidate.payee_id for name_candidate in match.name_candidates}
    claims_other_payee = bool(claimed_payee_ids) and payee.payee_id not in claimed_payee_ids
    if claims_other_payee:
        claimed_name = match.name_candidates[0].display_name
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"La factura dice ser de {claimed_name}, pero sus datos de pago pertenecen a "
            f"{payee.display_name}.",
        )
    account = match.bill_bank_account
    pays_business_into_personal_account = (
        account is not None
        and candidate.kind in CATEGORY_LIKE_KINDS
        and payee.kind is PayeeKind.PERSON
        and match.matched_by is IdentifierKind.BANK_ACCOUNT
    )
    if pays_business_into_personal_account:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"La cuenta {mask_account(account)} pertenece a la persona {payee.display_name}, "
            "pero la factura es de un servicio o empresa.",
        )
    if account and payee.payment_method is not PaymentMethod.BANK_TRANSFER:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"{payee.display_name} se paga con {payee.payment_method}; la factura pide "
            f"transferir a la cuenta {mask_account(account)}.",
        )
    if account and account not in match.registered_bank_accounts:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"La cuenta {mask_account(account)} no es la registrada para {payee.display_name}. "
            "Si el proveedor cambió de cuenta, registra la nueva y pide reenviar la factura.",
        )
    has_unconfirmed_identifiers = match.matched_by is IdentifierKind.ALIAS and bool(
        match.unknown_identifiers
    )
    if has_unconfirmed_identifiers:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"El nombre coincide con {payee.display_name}, pero sus identificadores no.",
        )
    return rule_result(
        "R05", RuleEffect.PASS, "Identificadores consistentes con el beneficiario registrado."
    )


def _known_sender(context: DecisionContext) -> RuleResult:
    match = context.match
    registered_senders = match.registered_senders
    is_checkable_email = context.source.source_type is BillSourceType.EMAIL and bool(
        registered_senders
    )
    if not is_checkable_email:
        return rule_result("R05b", RuleEffect.PASS, "Sin remitentes registrados que comparar.")
    if _sender_is_registered(match.sender_email, match.sender_domain, registered_senders):
        return rule_result("R05b", RuleEffect.PASS, "Remitente registrado para el beneficiario.")
    sender = match.sender_email or "desconocido"
    payee_name = match.payee.display_name if match.payee else "el beneficiario"
    return rule_result(
        "R05b",
        RuleEffect.REVIEW,
        f"El remitente {sender} no es uno de los registrados para {payee_name}.",
    )


def _kind_matches(context: DecisionContext) -> RuleResult:
    payee = context.match.payee
    if payee is None or payee.kind == context.candidate.kind:
        return rule_result("R06", RuleEffect.PASS, "El tipo de beneficiario coincide.")
    return rule_result(
        "R06",
        RuleEffect.REVIEW,
        f"La factura parece de tipo {context.candidate.kind}, pero {payee.display_name} está "
        f"registrado como {payee.kind}.",
    )


def _category_allowed(context: DecisionContext) -> RuleResult:
    category = context.candidate.category
    if category is None:
        return rule_result(
            "R07", RuleEffect.REVIEW, "No se pudo determinar la categoría del gasto."
        )
    if category not in context.policy.allowed_categories:
        return rule_result(
            "R07", RuleEffect.REVIEW, f"La categoría {category} no está permitida por la política."
        )
    return rule_result("R07", RuleEffect.PASS, f"Categoría permitida: {category}.")


def _category_confident(context: DecisionContext) -> RuleResult:
    candidate, payee = context.candidate, context.match.payee
    confidence = Decimal(str(candidate.category_confidence))
    if confidence < context.policy.min_category_confidence:
        return rule_result(
            "R08",
            RuleEffect.REVIEW,
            f"La categoría {candidate.category} se infirió con baja confianza ({confidence:.2f}).",
        )
    has_conflicting_category = (
        payee is not None
        and payee.default_category is not None
        and candidate.category != payee.default_category
    )
    if has_conflicting_category:
        return rule_result(
            "R08",
            RuleEffect.REVIEW,
            f"La factura se clasificó como {candidate.category}, pero {payee.display_name} "
            f"está registrado en {payee.default_category}.",
        )
    return rule_result("R08", RuleEffect.PASS, "Categoría consistente con el registro.")


def _currency_allowed(context: DecisionContext) -> RuleResult:
    currency = context.candidate.currency
    if currency is None:
        return rule_result("R09", RuleEffect.PASS, "Sin moneda; se evalúa en R01.")
    if currency.upper() not in context.policy.allowed_currencies:
        return rule_result(
            "R09", RuleEffect.REVIEW, f"La moneda {currency} no está permitida por la política."
        )
    if context.amount_usd is None:
        return rule_result(
            "R09", RuleEffect.REVIEW, f"No hay tipo de cambio para {currency}; no se convierte."
        )
    return rule_result("R09", RuleEffect.PASS, f"Moneda permitida: {currency}.")


def _no_probable_duplicate(context: DecisionContext) -> RuleResult:
    amount_usd = context.amount_usd
    if amount_usd is None:
        return rule_result("R11", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    invoice_number = context.bill.invoice_number
    for previous in context.recent_bills:
        if previous.amount_usd is None:
            continue
        is_close_amount = (
            abs(previous.amount_usd - amount_usd)
            <= previous.amount_usd * PROBABLE_DUPLICATE_TOLERANCE
        )
        has_same_number = invoice_number is not None and previous.invoice_number == invoice_number
        is_same_billing_cycle = _due_dates_overlap(previous.due_date, context.candidate.due_date)
        is_probable_duplicate = (is_close_amount and is_same_billing_cycle) or has_same_number
        if is_probable_duplicate:
            previous_label = bill_label(previous.invoice_number, previous.bill_id)
            return rule_result(
                "R11",
                RuleEffect.REVIEW,
                f"Se parece a la factura {previous_label} del {previous.created_at:%d-%m} "
                f"por {format_usd(previous.amount_usd)}.",
                {"factura_previa": str(previous.bill_id)},
            )
    return rule_result(
        "R11", RuleEffect.PASS, "Sin facturas parecidas en la ventana de duplicados."
    )


def _hard_cap(context: DecisionContext) -> RuleResult:
    amount_usd = context.amount_usd
    if amount_usd is None:
        return rule_result("R12", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    payee = context.match.payee
    cap = context.policy.hard_cap_per_payment_usd
    if payee is not None and payee.per_payment_max_usd is not None:
        cap = min(cap, payee.per_payment_max_usd)
    if amount_usd > cap:
        return rule_result(
            "R12",
            RuleEffect.HOLD,
            f"{format_usd(amount_usd)} supera el tope por pago de {format_usd(cap)}.",
        )
    return rule_result("R12", RuleEffect.PASS, f"Dentro del tope por pago de {format_usd(cap)}.")


def _auto_pay_max(context: DecisionContext) -> RuleResult:
    amount_usd = context.amount_usd
    if amount_usd is None:
        return rule_result("R13", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    auto_pay_max = context.policy.auto_pay_max_usd
    if amount_usd > auto_pay_max:
        return rule_result(
            "R13",
            RuleEffect.REVIEW,
            f"{format_usd(amount_usd)} supera el tope de autopago de {format_usd(auto_pay_max)}; "
            "requiere aprobación humana.",
        )
    return rule_result(
        "R13", RuleEffect.PASS, f"Dentro del tope de autopago de {format_usd(auto_pay_max)}."
    )


def _budget_available(context: DecisionContext) -> RuleResult:
    amount_usd = context.amount_usd
    if amount_usd is None:
        return rule_result("R14", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    charges = budget_charges(context.policy, context.match.payee, context.candidate.category)
    exceeded = []
    for charge in charges:
        projected = context.budget.get(charge.scope, Decimal("0")) + amount_usd
        if projected > charge.limit_usd:
            exceeded.append(
                f"el presupuesto {describe_scope(charge.scope, context.match.payee)} quedaría en "
                f"{format_usd(projected)} de {format_usd(charge.limit_usd)}"
            )
    if exceeded:
        return rule_result("R14", RuleEffect.HOLD, _sentence("; ".join(exceeded)))
    return rule_result("R14", RuleEffect.PASS, "Hay presupuesto disponible en el periodo.")


def _matches_agreement(context: DecisionContext) -> RuleResult:
    amount_usd, payee = context.amount_usd, context.match.payee
    if amount_usd is None:
        return rule_result("R17", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    if payee is None or payee.agreed_amount_usd is None:
        return rule_result("R17", RuleEffect.PASS, "Sin monto acordado registrado.")
    agreed = payee.agreed_amount_usd
    tolerance_pct = payee.agreed_tolerance_pct or Decimal("0")
    tolerance = agreed * tolerance_pct / PERCENT
    if abs(amount_usd - agreed) > tolerance:
        return rule_result(
            "R17",
            RuleEffect.REVIEW,
            f"{format_usd(amount_usd)} no cuadra con lo acordado: {format_usd(agreed)} "
            f"± {tolerance_pct:.0f} %.",
        )
    return rule_result("R17", RuleEffect.PASS, f"Coincide con lo acordado ({format_usd(agreed)}).")


def _identifiers_have_several_owners(match: PayeeMatch) -> bool:
    return len(set(match.identifier_owners.values())) > 1


def _due_dates_overlap(previous_due: date | None, current_due: date | None) -> bool:
    if previous_due is None or current_due is None:
        return True
    return abs((previous_due - current_due).days) <= SAME_CYCLE_DUE_DATE_DAYS


def _currency_has_explicit_evidence(candidate: PaymentCandidateBase) -> bool:
    currency_quotes = [
        evidence.quote for evidence in candidate.evidence if evidence.field == CURRENCY_FIELD
    ]
    return any(
        names_currency_explicitly(quote, candidate.currency or "") for quote in currency_quotes
    )


def _sender_is_registered(
    sender_email: str | None, sender_domain: str | None, registered_senders: list[str]
) -> bool:
    if sender_email and sender_email in registered_senders:
        return True
    if not sender_domain:
        return False
    return any(
        sender_domain == registered or sender_domain.endswith(f".{registered}")
        for registered in registered_senders
    )


def _shown_identifier(kind: IdentifierKind, normalized_value: str) -> str:
    if kind is IdentifierKind.BANK_ACCOUNT:
        return mask_account(normalized_value)
    return normalized_value


def _sentence(text: str) -> str:
    return f"{text[0].upper()}{text[1:]}."


RULES: tuple[tuple[str, Rule], ...] = (
    ("R01", _complete_data),
    ("R02", _no_embedded_instructions),
    ("R03", _not_blacklisted),
    ("R04", _registered_payee),
    ("R05", _consistent_identity),
    ("R05b", _known_sender),
    ("R06", _kind_matches),
    ("R07", _category_allowed),
    ("R08", _category_confident),
    ("R09", _currency_allowed),
    ("R11", _no_probable_duplicate),
    ("R12", _hard_cap),
    ("R13", _auto_pay_max),
    ("R14", _budget_available),
    ("R17", _matches_agreement),
)
