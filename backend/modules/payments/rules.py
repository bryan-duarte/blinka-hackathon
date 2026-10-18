from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from contracts.bills import BillRecord, BillSourceRecord, BillSourceType, BillSummary
from contracts.memory import MemoryPrecedent
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
from core.tax_jurisdictions import tax_id_fits_country
from modules.payments.budget import budget_charges, describe_scope
from modules.payments.fx import names_currency_explicitly
from modules.payments.presentation import bill_label, format_usd, mask_account

logger = get_logger(__name__)

PERCENT = Decimal("100")
PROBABLE_DUPLICATE_TOLERANCE = Decimal("0.005")
SAME_CYCLE_DUE_DATE_DAYS = 10
EVIDENCE_QUOTE_MAX_CHARS = 160
REQUIRED_FIELD_LABELS = {
    "payee_name": "payee",
    "amount": "amount",
    "currency": "currency",
    "due_date": "due date",
}
CATEGORY_LIKE_KINDS = frozenset({PayeeKind.SERVICE, PayeeKind.COMPANY})
NO_USD_AMOUNT_REASON = "Not applicable: no USD amount."
MISSING_CURRENCY_PROBLEM = "the invoice does not state its currency explicitly; it is not inferred"
IMPLICIT_CURRENCY_PROBLEM = (
    "the currency read is not written explicitly on the invoice; it is not inferred"
)
CURRENCY_FIELD = "currency"
RULE_FAILURE_REASON = "The rule could not be evaluated; sending to review."
IDENTIFIER_LABELS = {
    IdentifierKind.TAX_ID: "The tax ID",
    IdentifierKind.BANK_ACCOUNT: "The account",
    IdentifierKind.SERVICE_ACCOUNT_ID: "The service account",
    IdentifierKind.EMAIL: "The email",
    IdentifierKind.DOMAIN: "The domain",
    IdentifierKind.ALIAS: "The name",
}
REVIEW_DATE_FORMAT = "%b %d"

RULE_NAMES = {
    "R01": "complete_data",
    "R02": "no_embedded_instructions",
    "R03": "not_blacklisted",
    "R04": "registered_payee",
    "R05": "consistent_identity",
    "R05b": "known_sender",
    "R06": "kind_matches",
    "R07": "category_allowed",
    "R08": "category_confident",
    "R09": "currency_allowed",
    "R11": "no_probable_duplicate",
    "R12": "hard_cap",
    "R13": "auto_pay_limit",
    "R14": "budget_available",
    "R17": "matches_agreement",
    "R18": "tax_identity_consistent",
    "CHK1": "checker_service_matches",
    "CHK2": "checker_impersonation",
    "CHK3": "checker_usual_amount",
    "DUP": "exact_duplicate",
    "PAY": "payment_execution",
    "ERR": "technical_error",
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
    precedents: tuple[MemoryPrecedent, ...] = ()


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
        f"missing {REQUIRED_FIELD_LABELS[field]}"
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
        problems.append(f"uncertain reading of {', '.join(uncertain_fields)}")
    classification = context.classification
    is_doubtful_classification = (
        classification is not None
        and Decimal(str(classification.confidence)) < policy.min_field_confidence
    )
    if is_doubtful_classification:
        problems.append("uncertain document classification")
    if problems:
        return rule_result("R01", RuleEffect.REVIEW, _sentence("; ".join(dict.fromkeys(problems))))
    return rule_result("R01", RuleEffect.PASS, "Payee, amount, currency and due date were read.")


def _no_embedded_instructions(context: DecisionContext) -> RuleResult:
    instructions = context.candidate.embedded_instructions
    if instructions:
        first_instruction = instructions[0][:EVIDENCE_QUOTE_MAX_CHARS]
        return rule_result(
            "R02",
            RuleEffect.HOLD,
            "The invoice contains instructions aimed at the agent; they are not followed.",
            {"instruction": first_instruction},
        )
    return rule_result("R02", RuleEffect.PASS, "No instructions aimed at the agent.")


def _not_blacklisted(context: DecisionContext) -> RuleResult:
    payee = context.match.payee
    if context.blacklist_hits:
        hit = context.blacklist_hits[0]
        shown_value = _shown_identifier(hit.kind, hit.normalized_value)
        return rule_result(
            "R03",
            RuleEffect.HOLD,
            f"{IDENTIFIER_LABELS[hit.kind]} {shown_value} is blacklisted: {hit.reason}.",
            {"kind": str(hit.kind), "value": shown_value},
        )
    if payee is not None and payee.status is PayeeStatus.BLACKLISTED:
        return rule_result(
            "R03", RuleEffect.HOLD, f"{payee.display_name} is blocked in the registry."
        )
    return rule_result("R03", RuleEffect.PASS, "No invoice detail is on the blacklist.")


def _registered_payee(context: DecisionContext) -> RuleResult:
    match = context.match
    if match.payee is not None:
        return rule_result("R04", RuleEffect.PASS, f"Registered payee: {match.payee.display_name}.")
    if _identifiers_have_several_owners(match):
        reason = "The identifiers point to several registered payees."
    elif match.name_candidates:
        names = ", ".join(payee.display_name for payee in match.name_candidates)
        reason = f"Matches {names} by name only, with no identifiers to confirm it."
    else:
        payee_name = context.candidate.payee_name or "unnamed"
        reason = f"The payee “{payee_name}” is not registered."
    return rule_result("R04", RuleEffect.REVIEW, reason)


def _consistent_identity(context: DecisionContext) -> RuleResult:
    match, candidate = context.match, context.candidate
    payee = match.payee
    if _identifiers_have_several_owners(match):
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            "The invoice identifiers belong to different payees.",
        )
    if payee is None:
        return rule_result("R05", RuleEffect.PASS, "No registered payee; evaluated by R04.")
    claimed_payee_ids = {name_candidate.payee_id for name_candidate in match.name_candidates}
    claims_other_payee = bool(claimed_payee_ids) and payee.payee_id not in claimed_payee_ids
    if claims_other_payee:
        claimed_name = match.name_candidates[0].display_name
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"The invoice claims to be from {claimed_name}, but its payment details belong to "
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
            f"Account {mask_account(account)} belongs to the person {payee.display_name}, "
            "but the invoice is from a service or company.",
        )
    if account and payee.payment_method is not PaymentMethod.BANK_TRANSFER:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"{payee.display_name} is paid by {payee.payment_method}; the invoice asks for a "
            f"transfer to account {mask_account(account)}.",
        )
    if account and account not in match.registered_bank_accounts:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"Account {mask_account(account)} is not the one registered for "
            f"{payee.display_name}. If the vendor changed accounts, register the new one and ask "
            "them to resend the invoice.",
        )
    has_unconfirmed_identifiers = match.matched_by is IdentifierKind.ALIAS and bool(
        match.unknown_identifiers
    )
    if has_unconfirmed_identifiers:
        return rule_result(
            "R05",
            RuleEffect.HOLD,
            f"The name matches {payee.display_name}, but its identifiers do not.",
        )
    return rule_result(
        "R05", RuleEffect.PASS, "Identifiers are consistent with the registered payee."
    )


def _known_sender(context: DecisionContext) -> RuleResult:
    match = context.match
    if match.is_trusted_forwarder:
        return rule_result(
            "R05b",
            RuleEffect.PASS,
            f"Forwarded by trusted forwarder {match.sender_email}; identity checked from the "
            "document.",
        )
    registered_senders = match.registered_senders
    is_checkable_email = context.source.source_type is BillSourceType.EMAIL and bool(
        registered_senders
    )
    if not is_checkable_email:
        return rule_result("R05b", RuleEffect.PASS, "No registered senders to compare.")
    if _sender_is_registered(match.sender_email, match.sender_domain, registered_senders):
        return rule_result("R05b", RuleEffect.PASS, "Sender is registered for the payee.")
    sender = match.sender_email or "unknown"
    payee_name = match.payee.display_name if match.payee else "the payee"
    return rule_result(
        "R05b",
        RuleEffect.REVIEW,
        f"Sender {sender} is not one of the registered senders for {payee_name}.",
    )


def _kind_matches(context: DecisionContext) -> RuleResult:
    payee = context.match.payee
    if payee is None or payee.kind == context.candidate.kind:
        return rule_result("R06", RuleEffect.PASS, "The payee kind matches.")
    return rule_result(
        "R06",
        RuleEffect.REVIEW,
        f"The invoice looks like a {context.candidate.kind}, but {payee.display_name} is "
        f"registered as a {payee.kind}.",
    )


def _tax_identity_consistent(context: DecisionContext) -> RuleResult:
    candidate = context.candidate
    tax_id = getattr(candidate, "tax_id", None) or getattr(candidate, "national_id", None)
    tax_country = candidate.issuer_tax_country
    if not tax_country or not tax_id:
        return rule_result(
            "R18", RuleEffect.PASS, "Not applicable: no tax country or no identifier."
        )
    evidence = {"identifier": tax_id, "tax_country": tax_country}
    if tax_id_fits_country(tax_id, tax_country) is False:
        return rule_result(
            "R18",
            RuleEffect.REVIEW,
            f"Tax ID {tax_id} does not have the {tax_country} format, the country of the "
            "invoice standard.",
            evidence,
        )
    return rule_result(
        "R18", RuleEffect.PASS, f"Tax ID is consistent with {tax_country}.", evidence
    )


def _category_allowed(context: DecisionContext) -> RuleResult:
    category = context.candidate.category
    if category is None:
        return rule_result(
            "R07", RuleEffect.REVIEW, "The spending category could not be determined."
        )
    if category not in context.policy.allowed_categories:
        return rule_result(
            "R07", RuleEffect.REVIEW, f"Category {category} is not allowed by the policy."
        )
    return rule_result("R07", RuleEffect.PASS, f"Allowed category: {category}.")


def _category_confident(context: DecisionContext) -> RuleResult:
    candidate, payee = context.candidate, context.match.payee
    confidence = Decimal(str(candidate.category_confidence))
    if confidence < context.policy.min_category_confidence:
        return rule_result(
            "R08",
            RuleEffect.REVIEW,
            f"Category {candidate.category} was inferred with low confidence ({confidence:.2f}).",
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
            f"The invoice was classified as {candidate.category}, but {payee.display_name} "
            f"is registered under {payee.default_category}.",
        )
    return rule_result("R08", RuleEffect.PASS, "Category is consistent with the registry.")


def _currency_allowed(context: DecisionContext) -> RuleResult:
    currency = context.candidate.currency
    if currency is None:
        return rule_result("R09", RuleEffect.PASS, "No currency; evaluated by R01.")
    if currency.upper() not in context.policy.allowed_currencies:
        return rule_result(
            "R09", RuleEffect.REVIEW, f"Currency {currency} is not allowed by the policy."
        )
    if context.amount_usd is None:
        return rule_result(
            "R09", RuleEffect.REVIEW, f"No exchange rate available for {currency}; escalating."
        )
    return rule_result("R09", RuleEffect.PASS, f"Allowed currency: {currency}.")


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
                f"Looks like invoice {previous_label} from "
                f"{previous.created_at:{REVIEW_DATE_FORMAT}} for "
                f"{format_usd(previous.amount_usd)}.",
                {"previous_bill": str(previous.bill_id)},
            )
    return rule_result("R11", RuleEffect.PASS, "No similar invoices in the duplicate window.")


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
            f"{format_usd(amount_usd)} exceeds the per-payment cap of {format_usd(cap)}.",
        )
    return rule_result("R12", RuleEffect.PASS, f"Within the per-payment cap of {format_usd(cap)}.")


def _auto_pay_max(context: DecisionContext) -> RuleResult:
    amount_usd = context.amount_usd
    if amount_usd is None:
        return rule_result("R13", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    auto_pay_max = context.policy.auto_pay_max_usd
    if amount_usd > auto_pay_max:
        return rule_result(
            "R13",
            RuleEffect.REVIEW,
            f"{format_usd(amount_usd)} exceeds the auto-pay limit of {format_usd(auto_pay_max)}; "
            "a person must approve.",
        )
    return rule_result(
        "R13", RuleEffect.PASS, f"Within the auto-pay limit of {format_usd(auto_pay_max)}."
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
                f"the {describe_scope(charge.scope, context.match.payee)} budget would reach "
                f"{format_usd(projected)} of {format_usd(charge.limit_usd)}"
            )
    if exceeded:
        return rule_result("R14", RuleEffect.HOLD, _sentence("; ".join(exceeded)))
    return rule_result("R14", RuleEffect.PASS, "Budget is available for the period.")


def _matches_agreement(context: DecisionContext) -> RuleResult:
    amount_usd, payee = context.amount_usd, context.match.payee
    if amount_usd is None:
        return rule_result("R17", RuleEffect.PASS, NO_USD_AMOUNT_REASON)
    if payee is None or payee.agreed_amount_usd is None:
        return rule_result("R17", RuleEffect.PASS, "No agreed amount registered.")
    agreed = payee.agreed_amount_usd
    tolerance_pct = payee.agreed_tolerance_pct or Decimal("0")
    tolerance = agreed * tolerance_pct / PERCENT
    if abs(amount_usd - agreed) > tolerance:
        return rule_result(
            "R17",
            RuleEffect.REVIEW,
            f"{format_usd(amount_usd)} does not match the agreement: {format_usd(agreed)} "
            f"± {tolerance_pct:.0f}%.",
        )
    return rule_result("R17", RuleEffect.PASS, f"Matches the agreement ({format_usd(agreed)}).")


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
    ("R18", _tax_identity_consistent),
)
