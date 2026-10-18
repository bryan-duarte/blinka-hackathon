from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from contracts.bills import BillRecord, BillSourceRecord, BillSourceType, BillStatus, BillSummary
from contracts.payment_candidates import FieldEvidence, PersonCandidate, ServiceCandidate
from contracts.payment_policy import (
    BlacklistHit,
    IdentifierKind,
    PayeeKind,
    PayeeMatch,
    PayeeRecord,
    PayeeStatus,
    PaymentCategory,
    PaymentMethod,
    PaymentPolicy,
)
from contracts.payments import (
    CheckerAnswer,
    CheckerAssessment,
    DecisionActor,
    DecisionRecord,
    RuleEffect,
    RuleResult,
    Verdict,
)
from modules.bills import BillStateConflictError
from modules.fx import STATIC_USD_PER_UNIT
from modules.payments import rules, settlement
from modules.payments.checker import apply_checker
from modules.payments.errors import BudgetExhaustedError
from modules.payments.rules import DecisionContext, decide

OWNER_ID = uuid4()
TODAY = date(2026, 10, 17)
NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _policy() -> PaymentPolicy:
    return PaymentPolicy(
        policy_id=uuid4(),
        owner_id=OWNER_ID,
        version=1,
        hard_cap_per_payment_usd=Decimal("5000"),
        auto_pay_max_usd=Decimal("1000"),
        monthly_budget_usd=Decimal("12000"),
        category_monthly_budgets_usd={PaymentCategory.SAAS: Decimal("1500")},
        allowed_categories=[
            PaymentCategory.SAAS,
            PaymentCategory.CLOUD,
            PaymentCategory.CONTRACTOR,
        ],
        allowed_currencies=["USD", "CLP"],
        duplicate_window_days=45,
        min_field_confidence=Decimal("0.80"),
        min_category_confidence=Decimal("0.70"),
        checker_review_low=Decimal("0.20"),
        checker_review_high=Decimal("0.80"),
        created_at=NOW,
    )


def _payee(
    kind: PayeeKind = PayeeKind.SERVICE,
    name: str = "ACME Cloud",
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER,
    category: PaymentCategory = PaymentCategory.SAAS,
    agreed: Decimal | None = Decimal("120"),
    monthly_budget: Decimal | None = None,
) -> PayeeRecord:
    return PayeeRecord(
        payee_id=uuid4(),
        owner_id=OWNER_ID,
        kind=kind,
        display_name=name,
        normalized_name=name.lower(),
        status=PayeeStatus.ALLOWED,
        payment_method=method,
        default_category=category,
        currency="USD",
        per_payment_max_usd=None,
        monthly_budget_usd=monthly_budget,
        agreed_amount_usd=agreed,
        agreed_tolerance_pct=Decimal("5"),
        attributes={},
        version=1,
    )


def _candidate(**changes: object) -> ServiceCandidate:
    fields = {
        "payee_name": "ACME Cloud Inc.",
        "amount": Decimal("120.00"),
        "currency": "USD",
        "issue_date": date(2026, 10, 1),
        "due_date": date(2026, 10, 31),
        "invoice_number": "INV-2048",
        "description": "Suscripción SaaS",
        "bank_account": "000123456789",
        "payee_email": None,
        "category": PaymentCategory.SAAS,
        "category_confidence": 0.95,
        "evidence": [
            FieldEvidence(field="amount", quote="Total: USD 120.00", confidence=0.99),
            FieldEvidence(field="currency", quote="Total: USD 120.00", confidence=0.99),
        ],
        "provider_domain": "acmecloud.io",
        "service_account_id": None,
        "billing_period_start": None,
        "billing_period_end": None,
    }
    return ServiceCandidate(**{**fields, **changes})


def _match(payee: PayeeRecord | None, **changes: object) -> PayeeMatch:
    fields = {
        "payee": payee,
        "matched_by": IdentifierKind.BANK_ACCOUNT if payee else None,
        "identifier_owners": {"bank_account:000123456789": payee.payee_id} if payee else {},
        "unknown_identifiers": [],
        "name_candidates": [payee] if payee else [],
        "registered_bank_accounts": ["000123456789"],
        "registered_senders": ["acmecloud.io"],
        "normalized_payee_name": "acme cloud",
        "bill_bank_account": "000123456789",
        "sender_email": "billing@acmecloud.io",
        "sender_domain": "acmecloud.io",
    }
    return PayeeMatch(**{**fields, **changes})


def _bill(invoice_number: str | None = "INV2048") -> BillRecord:
    return BillRecord(
        bill_id=uuid4(),
        owner_id=OWNER_ID,
        kind=PayeeKind.SERVICE,
        payee_id=None,
        payee_name="ACME Cloud Inc.",
        invoice_number=invoice_number,
        amount=Decimal("120"),
        currency="USD",
        amount_usd=Decimal("120"),
        category=PaymentCategory.SAAS,
        due_date=TODAY,
        candidate={},
        document_sha256=None,
        fingerprint=None,
        duplicate_of_bill_id=None,
        status=BillStatus.DECIDING,
        version=1,
        created_at=NOW.replace(tzinfo=None),
        updated_at=NOW.replace(tzinfo=None),
    )


def _source() -> BillSourceRecord:
    return BillSourceRecord(
        source_id=uuid4(),
        owner_id=OWNER_ID,
        source_type=BillSourceType.EMAIL,
        source_ref="simulated:sim-1",
        sender="billing@acmecloud.io",
        body_text="",
        file_id=None,
        content_sha256="0" * 64,
        attachment_sha256=None,
        inbox_email_id=None,
        bill_id=None,
        received_at=None,
        created_at=NOW.replace(tzinfo=None),
    )


def _context(
    candidate: ServiceCandidate | PersonCandidate | None = None,
    match: PayeeMatch | None = None,
    **changes: object,
) -> DecisionContext:
    resolved_candidate = candidate or _candidate()
    context = DecisionContext(
        candidate=resolved_candidate,
        bill=_bill(),
        source=_source(),
        match=match or _match(_payee()),
        policy=_policy(),
        blacklist_hits=[],
        amount_usd=_static_usd(resolved_candidate.amount, resolved_candidate.currency),
        recent_bills=[],
        budget={},
        today=TODAY,
    )
    return replace(context, **changes)


def _static_usd(amount: Decimal | None, currency: str | None) -> Decimal | None:
    usd_per_unit = STATIC_USD_PER_UNIT.get((currency or "").upper())
    if amount is None or usd_per_unit is None:
        return None
    return (amount * usd_per_unit).quantize(Decimal("0.01"))


def _failed(context: DecisionContext) -> dict[str, RuleEffect]:
    evaluation = decide(context)
    return {
        result.rule_id: result.effect
        for result in evaluation.results
        if result.effect is not RuleEffect.PASS
    }


def test_clean_registered_bill_is_paid():
    evaluation = decide(_context())

    assert evaluation.verdict is Verdict.PAY
    assert all(result.effect is RuleEffect.PASS for result in evaluation.results)


def test_aws_named_bill_paying_into_a_person_account_is_held():
    aws = _payee(name="Amazon Web Services", method=PaymentMethod.CARD_ON_FILE)
    maria = _payee(kind=PayeeKind.PERSON, name="María José Pérez", agreed=None)
    candidate = _candidate(payee_name="Amazon Web Services", bank_account="CL-BE-99887766")
    match = _match(
        maria,
        name_candidates=[aws],
        identifier_owners={"bank_account:CLBE99887766": maria.payee_id},
        registered_bank_accounts=["CLBE99887766"],
        registered_senders=[],
        bill_bank_account="CLBE99887766",
        sender_email="billing@aws-invoices.net",
        sender_domain="aws-invoices.net",
    )

    evaluation = decide(_context(candidate, match))

    assert evaluation.verdict is Verdict.HOLD
    assert _failed(_context(candidate, match))["R05"] is RuleEffect.HOLD


def test_card_on_file_payee_asking_for_transfer_is_held():
    aws = _payee(name="Amazon Web Services", method=PaymentMethod.CARD_ON_FILE)
    match = _match(aws, bill_bank_account="999", registered_bank_accounts=[])

    assert _failed(_context(match=match))["R05"] is RuleEffect.HOLD


def test_over_auto_pay_max_goes_to_review():
    evidence = [FieldEvidence(field="currency", quote="Total: CLP 1.400.000", confidence=0.95)]
    candidate = _candidate(amount=Decimal("1400000"), currency="CLP", evidence=evidence)
    payee = _payee(agreed=None)

    evaluation = decide(_context(candidate, _match(payee)))

    assert evaluation.verdict is Verdict.REVIEW
    assert _failed(_context(candidate, _match(payee))) == {"R13": RuleEffect.REVIEW}


def test_over_hard_cap_is_held_even_when_review_is_waived():
    candidate = _candidate(amount=Decimal("6200"))
    context = _context(candidate, waived_effects=frozenset({RuleEffect.REVIEW}))

    assert decide(context).verdict is Verdict.HOLD


def test_missing_currency_is_never_inferred():
    context = _context(_candidate(currency=None))

    assert decide(context).verdict is Verdict.REVIEW
    assert _failed(context) == {"R01": RuleEffect.REVIEW}


def test_currency_without_explicit_marker_is_not_trusted():
    evidence = [FieldEvidence(field="currency", quote="Total: $119.000", confidence=0.9)]
    context = _context(_candidate(amount=Decimal("119000"), currency="CLP", evidence=evidence))

    assert _failed(context) == {"R01": RuleEffect.REVIEW}


def test_budget_snapshot_over_limit_is_held():
    context = _context(budget={"category:saas": Decimal("1450")})

    assert decide(context).verdict is Verdict.HOLD
    assert _failed(context)["R14"] is RuleEffect.HOLD


def test_amount_exactly_at_the_limit_is_allowed():
    context = _context(budget={"category:saas": Decimal("1380")})

    assert decide(context).verdict is Verdict.PAY


def test_blacklist_hit_wins_over_registered_payee():
    hit = BlacklistHit(kind=IdentifierKind.DOMAIN, normalized_value="acmecloud.io", reason="test")

    assert decide(_context(blacklist_hits=[hit])).verdict is Verdict.HOLD


def test_probable_duplicate_goes_to_review():
    previous = BillSummary(
        bill_id=uuid4(),
        invoice_number="INV2047",
        amount_usd=Decimal("120.30"),
        due_date=date(2026, 10, 30),
        status=BillStatus.PAID,
        created_at=NOW.replace(tzinfo=None),
    )

    assert _failed(_context(recent_bills=[previous])) == {"R11": RuleEffect.REVIEW}


def test_recurring_monthly_bill_is_not_a_probable_duplicate():
    last_month = BillSummary(
        bill_id=uuid4(),
        invoice_number="INV2010",
        amount_usd=Decimal("120.00"),
        due_date=date(2026, 9, 30),
        status=BillStatus.PAID,
        created_at=NOW.replace(tzinfo=None),
    )

    assert decide(_context(recent_bills=[last_month])).verdict is Verdict.PAY


def test_approved_non_positive_amount_is_never_paid():
    context = _context(_candidate(amount=Decimal("-500")))

    planned_payment = settlement._reservation_for(context.bill, context)

    assert isinstance(planned_payment, RuleResult)
    assert planned_payment.effect is RuleEffect.HOLD


def test_human_approval_waives_only_review_rules():
    context = _context(_candidate(amount=Decimal("1200")), _match(_payee(agreed=None)))
    approved = replace(context, waived_effects=frozenset({RuleEffect.REVIEW}))

    assert decide(context).verdict is Verdict.REVIEW
    assert decide(approved).verdict is Verdict.PAY


def test_checker_can_only_raise_severity():
    context = _context()
    paid = decide(context)
    risky = CheckerAssessment(
        answers=[
            CheckerAnswer(question_id="CHK1", probability=0.95, rationale="ok"),
            CheckerAnswer(question_id="CHK2", probability=0.6, rationale="sospechoso"),
        ]
    )
    reassuring = CheckerAssessment(
        answers=[
            CheckerAnswer(question_id="CHK1", probability=0.99, rationale="ok"),
            CheckerAnswer(question_id="CHK2", probability=0.01, rationale="ok"),
        ]
    )
    held = decide(_context(_candidate(amount=Decimal("6200"))))

    assert apply_checker(paid, risky, context).verdict is Verdict.REVIEW
    assert apply_checker(paid, reassuring, context).verdict is Verdict.PAY
    assert apply_checker(paid, None, context).verdict is Verdict.REVIEW
    assert apply_checker(held, reassuring, context).verdict is Verdict.HOLD


def _crashing_rule(context: DecisionContext) -> None:
    raise RuntimeError


def test_rule_crash_fails_closed(monkeypatch):
    monkeypatch.setattr(rules, "RULES", (("R02", _crashing_rule), *rules.RULES[2:]))

    assert decide(_context()).verdict is Verdict.REVIEW


def _person_candidate(national_id: str, issuer_tax_country: str | None) -> PersonCandidate:
    base_fields = _candidate().model_dump(
        exclude={
            "kind",
            "provider_domain",
            "service_account_id",
            "billing_period_start",
            "billing_period_end",
        }
    )
    return PersonCandidate(
        **{**base_fields, "issuer_tax_country": issuer_tax_country},
        national_id=national_id,
        concept="honorarios",
    )


def _tax_identity_effect(candidate: ServiceCandidate | PersonCandidate) -> RuleEffect:
    evaluation = decide(_context(candidate))
    return next(result.effect for result in evaluation.results if result.rule_id == "R18")


def test_tax_id_contradicting_the_invoice_standard_goes_to_review():
    candidate = _person_candidate("900123456", issuer_tax_country="MX")

    assert _tax_identity_effect(candidate) is RuleEffect.REVIEW


def test_tax_id_matching_the_invoice_standard_passes():
    candidate = _person_candidate("EKU9003173C9", issuer_tax_country="MX")

    assert _tax_identity_effect(candidate) is RuleEffect.PASS


def test_tax_identity_rule_does_not_apply_without_tax_country():
    candidate = _person_candidate("900123456", issuer_tax_country=None)

    assert _tax_identity_effect(candidate) is RuleEffect.PASS


def test_unknown_sender_needs_review_unless_trusted_forwarder():
    forwarded = {"sender_email": "finance@andescape.com", "sender_domain": "andescape.com"}

    unknown = _failed(_context(match=_match(_payee(), **forwarded)))
    trusted = decide(
        _context(match=_match(_payee(), **forwarded, is_trusted_forwarder=True))
    ).results

    assert unknown == {"R05b": RuleEffect.REVIEW}
    sender_result = next(result for result in trusted if result.rule_id == "R05b")
    assert sender_result.effect is RuleEffect.PASS
    assert "trusted forwarder finance@andescape.com" in sender_result.reason


class _RecordingLedger:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.commits: list[dict] = []

    async def commit_settlement(
        self, owner_id, bill_id, from_status, target_status, reservation, decision
    ):
        self.commits.append(
            {"target_status": target_status, "reservation": reservation, "decision": decision}
        )
        if self.failure is not None:
            failure, self.failure = self.failure, None
            raise failure
        return decision


async def _settle(context: DecisionContext, ledger: _RecordingLedger) -> DecisionRecord:
    return await settlement.settle(
        SimpleNamespace(ledger=ledger),
        None,
        context.bill,
        context,
        decide(context),
        actor=DecisionActor.AGENT,
        from_status=BillStatus.DECIDING,
    )


async def test_settle_pays_in_a_single_commit():
    ledger = _RecordingLedger()

    decision = await _settle(_context(), ledger)

    assert decision.verdict is Verdict.PAY
    assert len(ledger.commits) == 1
    assert ledger.commits[0]["target_status"] is BillStatus.PAID
    assert ledger.commits[0]["reservation"] is not None


async def test_settle_holds_without_reservation_when_budget_runs_out_mid_commit():
    ledger = _RecordingLedger(failure=BudgetExhaustedError("global"))

    decision = await _settle(_context(), ledger)

    assert decision.verdict is Verdict.HOLD
    assert [commit["target_status"] for commit in ledger.commits] == [
        BillStatus.PAID,
        BillStatus.HELD,
    ]
    assert ledger.commits[1]["reservation"] is None
    assert decision.rule_results[-1].rule_id == "R14"


async def test_settle_propagates_bill_state_conflicts_without_retrying():
    ledger = _RecordingLedger(failure=BillStateConflictError())

    with pytest.raises(BillStateConflictError):
        await _settle(_context(), ledger)

    assert len(ledger.commits) == 1
