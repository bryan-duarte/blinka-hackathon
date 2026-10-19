from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from contracts.bills import BillStatus
from contracts.fx import USD, FxQuote, FxSource
from contracts.payment_candidates import CompanyCandidate, PersonCandidate, ServiceCandidate
from contracts.payment_policy import (
    BlacklistEntryCreate,
    IdentifierKind,
    PayeeCreate,
    PayeeIdentifierCreate,
    PayeeKind,
    PaymentCategory,
    PaymentMethod,
    PaymentPolicyUpdate,
    TrustedForwarderCreate,
    TrustedForwarderKind,
)
from contracts.payments import DecisionActor, RuleEffect, RuleResult, Verdict
from modules.payments.presentation import format_amount, format_usd
from modules.payments.rules import RULES, rule_result

COMPANY_BILL_TO = "Andescape Labs, Inc. · 251 Little Falls Dr, Wilmington, DE 19808, USA"
HISTORY_MONTH_OFFSETS = (-3, -2, -1)
PAYMENT_TERM_DAYS = 15
DECISION_HOUR = 10
HUMAN_REVIEW_DELAY = timedelta(days=1)
EXTRACTION_CONFIDENCE = 0.97
CATEGORY_CONFIDENCE = 0.95
CHECKER_RULE_IDS = ("CHK1", "CHK2", "CHK3")

AWS = "Amazon Web Services"
ACME = "ACME Cloud"
NUBIO = "Nubio Software Ltda"
SISUR = "Servicios Integrales del Sur SpA"
BRAVA = "Agencia Brava S.A. de C.V."
KESSLER = "Kessler Consulting GmbH"
PROVIDENCIA = "Inmobiliaria Providencia Ltda"
MARIA = "María José Pérez"
ANDRES = "Andrés Felipe Gómez"
LUCIA = "Lucía Hernández"
DATACORP = "Datacorp Chile SpA"
IMPOSTOR_NAME = "Amaz0n Web Services"

DEMO_CHECKER_REVIEW_HIGH = Decimal("0.70")
DUPLICATE_AGAINST_HISTORY_INVOICE = "F-6188"
DUPLICATE_AGAINST_HISTORY_AMOUNT = Decimal("1149540")

DEMO_POLICY = PaymentPolicyUpdate(
    hard_cap_per_payment_usd=Decimal("8000"),
    auto_pay_max_usd=Decimal("2500"),
    monthly_budget_usd=Decimal("30000"),
    category_monthly_budgets_usd={
        PaymentCategory.CLOUD: Decimal("4000"),
        PaymentCategory.SAAS: Decimal("1500"),
        PaymentCategory.CONTRACTOR: Decimal("9000"),
        PaymentCategory.PROFESSIONAL_SERVICES: Decimal("16000"),
        PaymentCategory.RENT: Decimal("1500"),
        PaymentCategory.UTILITIES: Decimal("500"),
    },
    allowed_categories=[
        PaymentCategory.CLOUD,
        PaymentCategory.SAAS,
        PaymentCategory.CONTRACTOR,
        PaymentCategory.PROFESSIONAL_SERVICES,
        PaymentCategory.RENT,
        PaymentCategory.UTILITIES,
    ],
    allowed_currencies=["USD", "CLP", "CLF", "MXN", "COP", "BRL", "EUR"],
    checker_review_high=DEMO_CHECKER_REVIEW_HIGH,
)


def _identifiers(*pairs: tuple[IdentifierKind, str]) -> list[PayeeIdentifierCreate]:
    return [PayeeIdentifierCreate(kind=kind, value=value) for kind, value in pairs]


DEMO_PAYEES: tuple[PayeeCreate, ...] = (
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name=AWS,
        payment_method=PaymentMethod.CARD_ON_FILE,
        default_category=PaymentCategory.CLOUD,
        currency="USD",
        attributes={"country": "US"},
        identifiers=_identifiers(
            (IdentifierKind.DOMAIN, "aws.amazon.com"),
            (IdentifierKind.DOMAIN, "amazon.com"),
            (IdentifierKind.SERVICE_ACCOUNT_ID, "123456789012"),
            (IdentifierKind.ALIAS, "AWS"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name=ACME,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.SAAS,
        currency="USD",
        agreed_amount_usd=Decimal("120"),
        agreed_tolerance_pct=Decimal("5"),
        attributes={"country": "US"},
        identifiers=_identifiers(
            (IdentifierKind.DOMAIN, "acmecloud.io"),
            (IdentifierKind.BANK_ACCOUNT, "000123456789"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name=NUBIO,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.SAAS,
        currency="BRL",
        agreed_amount_usd=Decimal("95"),
        agreed_tolerance_pct=Decimal("8"),
        attributes={"country": "BR"},
        identifiers=_identifiers(
            (IdentifierKind.DOMAIN, "nubio.com.br"),
            (IdentifierKind.TAX_ID, "12.345.678/0001-90"),
            (IdentifierKind.EMAIL, "cobranca@nubio.com.br"),
            (IdentifierKind.BANK_ACCOUNT, "BR-ITAU-0341-12345-6"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.COMPANY,
        display_name=SISUR,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.PROFESSIONAL_SERVICES,
        currency="CLP",
        per_payment_max_usd=Decimal("3000"),
        attributes={"country": "CL"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "76.543.210-K"),
            (IdentifierKind.BANK_ACCOUNT, "CL-001-2233445566"),
            (IdentifierKind.EMAIL, "facturacion@sisur.cl"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.COMPANY,
        display_name=BRAVA,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.PROFESSIONAL_SERVICES,
        currency="MXN",
        agreed_amount_usd=Decimal("1800"),
        agreed_tolerance_pct=Decimal("6"),
        attributes={"country": "MX"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "ABR190312KX1"),
            (IdentifierKind.DOMAIN, "agenciabrava.mx"),
            (IdentifierKind.BANK_ACCOUNT, "012180001234567891"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.COMPANY,
        display_name=KESSLER,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.PROFESSIONAL_SERVICES,
        currency="EUR",
        attributes={"country": "DE"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "DE811234567"),
            (IdentifierKind.DOMAIN, "kessler-consulting.de"),
            (IdentifierKind.BANK_ACCOUNT, "DE89370400440532013000"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.COMPANY,
        display_name=PROVIDENCIA,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.RENT,
        currency="CLF",
        agreed_amount_usd=Decimal("1150"),
        agreed_tolerance_pct=Decimal("5"),
        attributes={"country": "CL"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "77.888.999-1"),
            (IdentifierKind.EMAIL, "arriendos@iprovidencia.cl"),
            (IdentifierKind.BANK_ACCOUNT, "CL-BCI-11223344"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.PERSON,
        display_name=MARIA,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.CONTRACTOR,
        currency="USD",
        monthly_budget_usd=Decimal("1500"),
        agreed_amount_usd=Decimal("900"),
        agreed_tolerance_pct=Decimal("0"),
        attributes={"country": "CL"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "15.234.567-8"),
            (IdentifierKind.BANK_ACCOUNT, "CL-BE-99887766"),
            (IdentifierKind.EMAIL, "maria.perez.dev@gmail.com"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.PERSON,
        display_name=ANDRES,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.CONTRACTOR,
        currency="COP",
        monthly_budget_usd=Decimal("2000"),
        agreed_amount_usd=Decimal("2000"),
        agreed_tolerance_pct=Decimal("3"),
        attributes={"country": "CO"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "1020456789"),
            (IdentifierKind.BANK_ACCOUNT, "CO-BANCOLOMBIA-45678901234"),
            (IdentifierKind.EMAIL, "andres.gomez.dev@gmail.com"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.PERSON,
        display_name=LUCIA,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.CONTRACTOR,
        currency="MXN",
        monthly_budget_usd=Decimal("1400"),
        agreed_amount_usd=Decimal("1200"),
        agreed_tolerance_pct=Decimal("3"),
        attributes={"country": "MX"},
        identifiers=_identifiers(
            (IdentifierKind.TAX_ID, "HELU920514AB3"),
            (IdentifierKind.BANK_ACCOUNT, "002180700112233445"),
            (IdentifierKind.EMAIL, "lucia.hdz.design@gmail.com"),
        ),
    ),
    PayeeCreate(
        kind=PayeeKind.SERVICE,
        display_name=DATACORP,
        payment_method=PaymentMethod.BANK_TRANSFER,
        default_category=PaymentCategory.UTILITIES,
        currency="CLP",
        attributes={"country": "CL"},
        identifiers=_identifiers(
            (IdentifierKind.DOMAIN, "datacorp.cl"),
            (IdentifierKind.EMAIL, "facturacion@datacorp.cl"),
            (IdentifierKind.TAX_ID, "96.555.444-3"),
            (IdentifierKind.BANK_ACCOUNT, "CL-SANT-55667788"),
        ),
    ),
)
DEMO_PAYEES_BY_NAME = {payee.display_name: payee for payee in DEMO_PAYEES}

DEMO_BLACKLIST: tuple[BlacklistEntryCreate, ...] = (
    BlacklistEntryCreate(
        kind=IdentifierKind.BANK_ACCOUNT, value="US-CHASE-55554444", reason="reported account"
    ),
    BlacklistEntryCreate(
        kind=IdentifierKind.DOMAIN, value="amaz0n-billing.com", reason="phishing domain"
    ),
    BlacklistEntryCreate(
        kind=IdentifierKind.ALIAS, value="Proveedor Fantasma", reason="non-existent vendor"
    ),
    BlacklistEntryCreate(
        kind=IdentifierKind.BANK_ACCOUNT,
        value="CO-NEQUI-3001112233",
        reason="account flagged in fraud report",
    ),
)

DEMO_TRUSTED_FORWARDERS: tuple[TrustedForwarderCreate, ...] = (
    TrustedForwarderCreate(
        kind=TrustedForwarderKind.EMAIL,
        value="finance@andescape.com",
        note="Andescape finance inbox",
    ),
)

SEED_USD_PER_UNIT_BY_MONTH: dict[int, dict[str, Decimal]] = {
    0: {
        "CLP": Decimal("0.001018"),
        "CLF": Decimal("40.23"),
        "EUR": Decimal("1.124"),
        "MXN": Decimal("0.05416"),
        "COP": Decimal("0.000314"),
        "BRL": Decimal("0.1965"),
    },
    -1: {
        "CLP": Decimal("0.001031"),
        "CLF": Decimal("40.05"),
        "EUR": Decimal("1.118"),
        "MXN": Decimal("0.05382"),
        "COP": Decimal("0.000309"),
        "BRL": Decimal("0.1948"),
    },
    -2: {
        "CLP": Decimal("0.001044"),
        "CLF": Decimal("39.88"),
        "EUR": Decimal("1.109"),
        "MXN": Decimal("0.05355"),
        "COP": Decimal("0.000305"),
        "BRL": Decimal("0.1931"),
    },
    -3: {
        "CLP": Decimal("0.001052"),
        "CLF": Decimal("39.71"),
        "EUR": Decimal("1.101"),
        "MXN": Decimal("0.05327"),
        "COP": Decimal("0.000301"),
        "BRL": Decimal("0.1915"),
    },
}

PASS_REASONS = {
    "R01": "Payee, amount, currency and due date were read.",
    "R02": "No instructions aimed at the agent.",
    "R03": "No invoice detail is on the blacklist.",
    "R04": "Registered payee: {payee}.",
    "R05": "Identifiers are consistent with the registered payee.",
    "R05b": "Sender is registered for the payee.",
    "R06": "The payee kind matches.",
    "R07": "Allowed category: {category}.",
    "R08": "Category is consistent with the registry.",
    "R09": "Allowed currency: {currency}.",
    "R11": "No similar invoices in the duplicate window.",
    "R12": "Within the per-payment cap of USD 8,000.00.",
    "R13": "Within the auto-pay limit of USD 2,500.00.",
    "R14": "Budget is available for the period.",
    "R17": "Matches the agreement or no agreed amount is registered.",
    "R18": "Tax ID is consistent with the payee's country.",
    "CHK1": "Checker (model): the description matches the payee's registered service.",
    "CHK2": "Checker (model): no sign of impersonation in brand, sender or payment details.",
    "CHK3": "Checker (model): the amount is in line with the payee's recent invoices.",
}


@dataclass(frozen=True)
class HistoricalDecision:
    actor: DecisionActor
    verdict: Verdict
    rule_results: tuple[RuleResult, ...]
    explanation: str
    decided_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class HistoricalBill:
    key: str
    payee_name: str
    is_registered_payee: bool
    kind: PayeeKind
    invoice_number: str
    amount: Decimal
    currency: str
    quote: FxQuote
    category: PaymentCategory
    issued_on: date
    due_on: date
    candidate: dict
    decisions: tuple[HistoricalDecision, ...]
    final_status: BillStatus
    is_paid: bool
    duplicate_of_key: str | None = None

    @property
    def amount_usd(self) -> Decimal:
        return self.quote.convert(self.amount)

    @property
    def paid_at(self) -> datetime:
        return self.decisions[-1].decided_at


@dataclass(frozen=True)
class _PaidBill:
    payee_name: str
    invoice_number: str
    amount: Decimal
    currency: str
    day: int
    description: str


def history(today: date) -> list[HistoricalBill]:
    bills: list[HistoricalBill] = []
    for offset in HISTORY_MONTH_OFFSETS:
        bills.extend(_paid(today, offset, paid_bill) for paid_bill in _monthly_bills(today, offset))
    bills.extend(_exception_bills(today, bills))
    bills.extend(_current_month_bills(today))
    return bills


def month_start(today: date, offset: int) -> date:
    month_index = today.year * 12 + today.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def month_day(today: date, offset: int, day: int) -> date:
    first_day = month_start(today, offset)
    last_day = monthrange(first_day.year, first_day.month)[1]
    return first_day.replace(day=min(day, last_day))


def _monthly_bills(today: date, offset: int) -> list[_PaidBill]:
    period = month_start(today, offset)
    yyyymm, mm = f"{period:%Y%m}", f"{period:%m}"
    month_number = offset + len(HISTORY_MONTH_OFFSETS)
    sisur_amounts = {
        -3: (Decimal("980000"), Decimal("1250000")),
        -2: (Decimal("720000"), Decimal("1180000")),
        -1: (Decimal("860000"), Decimal("1320000")),
    }[offset]
    aws_amounts = {-3: Decimal("3410"), -2: Decimal("3560"), -1: Decimal("3690")}[offset]
    aws_staging = {-3: Decimal("165"), -2: Decimal("172"), -1: Decimal("181")}[offset]
    return [
        _PaidBill(AWS, f"AWS-{yyyymm}-01", aws_amounts, USD, 3, "AWS production account"),
        _PaidBill(AWS, f"AWS-{yyyymm}-02", aws_staging, USD, 3, "AWS staging account"),
        _PaidBill(ACME, f"INV-19{mm}", Decimal("120"), USD, 4, "ACME Cloud Pro subscription"),
        _PaidBill(NUBIO, f"NF-{yyyymm}", Decimal("485"), "BRL", 6, "Nubio ERP licença mensal"),
        _PaidBill(SISUR, f"F-59{month_number}1", sisur_amounts[0], "CLP", 5, "Soporte de procesos"),
        _PaidBill(SISUR, f"F-59{month_number}2", sisur_amounts[1], "CLP", 8, "Consultoría"),
        _PaidBill(
            BRAVA, f"A-9{month_number}0", Decimal("33250"), "MXN", 5, "Consultoría estratégica"
        ),
        _PaidBill(PROVIDENCIA, f"ARR-{yyyymm}", Decimal("28.5"), "CLF", 1, "Arriendo oficina"),
        _PaidBill(MARIA, f"CC-MJP-{yyyymm}", Decimal("900"), USD, 7, "Honorarios desarrollo"),
        _PaidBill(ANDRES, f"CC-AFG-{yyyymm}", Decimal("6370000"), "COP", 7, "Honorarios backend"),
        _PaidBill(LUCIA, f"CC-LH-{yyyymm}", Decimal("22000"), "MXN", 7, "Honorarios diseño"),
        _PaidBill(DATACORP, f"10{yyyymm}", Decimal("89990"), "CLP", 2, "Internet fibra 1 Gbps"),
    ]


def _current_month_bills(today: date) -> list[HistoricalBill]:
    yyyymm = f"{today:%Y%m}"
    current_month_bills = (
        (6, _PaidBill(ANDRES, f"CC-AFG-{yyyymm}", Decimal("6369000"), "COP", 0, "Honorarios")),
        (4, _PaidBill(AWS, f"AWS-{yyyymm}-01", Decimal("3540"), USD, 0, "AWS production account")),
        (
            2,
            _PaidBill(
                SISUR,
                DUPLICATE_AGAINST_HISTORY_INVOICE,
                DUPLICATE_AGAINST_HISTORY_AMOUNT,
                "CLP",
                0,
                "Soporte mensual de procesos",
            ),
        ),
    )
    return [
        _paid(today, 0, paid_bill, issued_on=max(month_start(today, 0), today - timedelta(days)))
        for days, paid_bill in current_month_bills
    ]


def _exception_bills(today: date, paid_bills: list[HistoricalBill]) -> list[HistoricalBill]:
    acme_original = next(
        bill
        for bill in paid_bills
        if bill.payee_name == ACME and bill.issued_on.month == month_start(today, -3).month
    )
    return [
        _kessler_approved_by_cfo(today),
        _impostor_held(today),
        _acme_rejected(today),
        _acme_duplicate(today, acme_original),
    ]


def _paid(
    today: date, offset: int, paid_bill: _PaidBill, issued_on: date | None = None
) -> HistoricalBill:
    issue_date = issued_on or month_day(today, offset, paid_bill.day)
    payee = DEMO_PAYEES_BY_NAME[paid_bill.payee_name]
    quote = _seed_quote(paid_bill.currency, offset, issue_date)
    passing_results = _rule_results(payee, paid_bill.currency, include_checker=True)
    decision = HistoricalDecision(
        actor=DecisionActor.AGENT,
        verdict=Verdict.PAY,
        rule_results=passing_results,
        explanation=(
            f"Paid automatically: passes all {len(passing_results)} rules. {payee.display_name}: "
            f"{_amount_text(paid_bill.amount, paid_bill.currency, quote)}, "
            f"category {payee.default_category}."
        ),
        decided_at=_decision_time(issue_date),
    )
    return _bill(
        key=f"{paid_bill.payee_name}:{paid_bill.invoice_number}",
        payee=payee,
        invoice_number=paid_bill.invoice_number,
        amount=paid_bill.amount,
        currency=paid_bill.currency,
        quote=quote,
        issued_on=issue_date,
        description=paid_bill.description,
        decisions=(decision,),
        final_status=BillStatus.PAID,
        is_paid=True,
    )


def _kessler_approved_by_cfo(today: date) -> HistoricalBill:
    payee = DEMO_PAYEES_BY_NAME[KESSLER]
    issued_on = month_day(today, -2, 12)
    amount = Decimal("2900")
    quote = _seed_quote("EUR", -2, issued_on)
    over_limit_reason = (
        f"{format_usd(quote.convert(amount))} exceeds the auto-pay limit of USD 2,500.00; "
        "a person must approve."
    )
    review = HistoricalDecision(
        actor=DecisionActor.AGENT,
        verdict=Verdict.REVIEW,
        rule_results=_rule_results(
            payee, "EUR", overrides={"R13": (RuleEffect.REVIEW, over_limit_reason)}
        ),
        explanation=f"In review: 1 point needs a person. {over_limit_reason}",
        decided_at=_decision_time(issued_on),
    )
    approval = HistoricalDecision(
        actor=DecisionActor.HUMAN,
        verdict=Verdict.PAY,
        rule_results=review.rule_results,
        explanation=(
            "Paid with human approval: 1 review point was accepted. "
            f"{KESSLER}: {_amount_text(amount, 'EUR', quote)}, category professional_services."
        ),
        decided_at=review.decided_at + HUMAN_REVIEW_DELAY,
        note="Approved by CFO: quarterly workshop",
    )
    return _bill(
        key=f"{KESSLER}:KC-2026-118",
        payee=payee,
        invoice_number="KC-2026-118",
        amount=amount,
        currency="EUR",
        quote=quote,
        issued_on=issued_on,
        description="Quarterly strategy workshop",
        decisions=(review, approval),
        final_status=BillStatus.PAID,
        is_paid=True,
    )


def _impostor_held(today: date) -> HistoricalBill:
    issued_on = month_day(today, -1, 14)
    quote = _seed_quote(USD, -1, issued_on)
    blacklist_reason = "The domain amaz0n-billing.com is blacklisted: phishing domain."
    rule_results = _rule_results(
        None, USD, overrides={"R03": (RuleEffect.HOLD, blacklist_reason)}, payee_name=IMPOSTOR_NAME
    )
    decision = HistoricalDecision(
        actor=DecisionActor.AGENT,
        verdict=Verdict.HOLD,
        rule_results=rule_results,
        explanation=f"Held: 1 rule blocks the payment. {blacklist_reason}",
        decided_at=_decision_time(issued_on),
    )
    return HistoricalBill(
        key="impostor:AMZ-55120",
        payee_name=IMPOSTOR_NAME,
        is_registered_payee=False,
        kind=PayeeKind.SERVICE,
        invoice_number="AMZ-55120",
        amount=Decimal("1250"),
        currency=USD,
        quote=quote,
        category=PaymentCategory.CLOUD,
        issued_on=issued_on,
        due_on=issued_on + timedelta(days=PAYMENT_TERM_DAYS),
        candidate=ServiceCandidate(
            payee_name=IMPOSTOR_NAME,
            amount=Decimal("1250"),
            currency=USD,
            issue_date=issued_on,
            due_date=issued_on + timedelta(days=PAYMENT_TERM_DAYS),
            invoice_number="AMZ-55120",
            description="Cloud hosting",
            bank_account="US-CHASE-55554444",
            payee_email="billing@amaz0n-billing.com",
            category=PaymentCategory.CLOUD,
            category_confidence=CATEGORY_CONFIDENCE,
            provider_domain="amaz0n-billing.com",
            service_account_id=None,
            billing_period_start=None,
            billing_period_end=None,
        ).model_dump(mode="json"),
        decisions=(decision,),
        final_status=BillStatus.HELD,
        is_paid=False,
    )


def _acme_rejected(today: date) -> HistoricalBill:
    payee = DEMO_PAYEES_BY_NAME[ACME]
    issued_on = month_day(today, -1, 16)
    amount = Decimal("180")
    quote = _seed_quote(USD, -1, issued_on)
    mismatch_reason = "USD 180.00 does not match the agreement: USD 120.00 ± 5%."
    review = HistoricalDecision(
        actor=DecisionActor.AGENT,
        verdict=Verdict.REVIEW,
        rule_results=_rule_results(
            payee, USD, overrides={"R17": (RuleEffect.REVIEW, mismatch_reason)}
        ),
        explanation=f"In review: 1 point needs a person. {mismatch_reason}",
        decided_at=_decision_time(issued_on),
    )
    rejection = HistoricalDecision(
        actor=DecisionActor.HUMAN,
        verdict=Verdict.HOLD,
        rule_results=review.rule_results,
        explanation="Rejected by a person: Not the agreed price",
        decided_at=review.decided_at + HUMAN_REVIEW_DELAY,
        note="Not the agreed price",
    )
    return _bill(
        key=f"{ACME}:INV-1999",
        payee=payee,
        invoice_number="INV-1999",
        amount=amount,
        currency=USD,
        quote=quote,
        issued_on=issued_on,
        description="ACME Cloud Pro subscription (new price)",
        decisions=(review, rejection),
        final_status=BillStatus.REJECTED,
        is_paid=False,
    )


def _acme_duplicate(today: date, original: HistoricalBill) -> HistoricalBill:
    payee = DEMO_PAYEES_BY_NAME[ACME]
    issued_on = month_day(today, -3, 19)
    duplicate_reason = (
        f"This invoice ({original.invoice_number}) was already received on "
        f"{original.paid_at:%b %d, %Y}; the original is paid."
    )
    decision = HistoricalDecision(
        actor=DecisionActor.AGENT,
        verdict=Verdict.HOLD,
        rule_results=(rule_result("DUP", RuleEffect.HOLD, duplicate_reason),),
        explanation=f"Held: exact duplicate. {duplicate_reason}",
        decided_at=_decision_time(issued_on),
    )
    duplicate = _bill(
        key=f"{ACME}:{original.invoice_number}:resent",
        payee=payee,
        invoice_number=original.invoice_number,
        amount=original.amount,
        currency=USD,
        quote=original.quote,
        issued_on=original.issued_on,
        description="ACME Cloud Pro subscription (resent)",
        decisions=(decision,),
        final_status=BillStatus.DUPLICATE,
        is_paid=False,
    )
    return replace(duplicate, duplicate_of_key=original.key)


def _bill(
    key: str,
    payee: PayeeCreate,
    invoice_number: str,
    amount: Decimal,
    currency: str,
    quote: FxQuote,
    issued_on: date,
    description: str,
    decisions: tuple[HistoricalDecision, ...],
    final_status: BillStatus,
    is_paid: bool,
) -> HistoricalBill:
    due_on = issued_on + timedelta(days=PAYMENT_TERM_DAYS)
    category = payee.default_category or PaymentCategory.OTHER
    return HistoricalBill(
        key=key,
        payee_name=payee.display_name,
        is_registered_payee=True,
        kind=payee.kind,
        invoice_number=invoice_number,
        amount=amount,
        currency=currency,
        quote=quote,
        category=category,
        issued_on=issued_on,
        due_on=due_on,
        candidate=_candidate(
            payee, invoice_number, amount, currency, issued_on, due_on, description
        ),
        decisions=decisions,
        final_status=final_status,
        is_paid=is_paid,
    )


def _candidate(
    payee: PayeeCreate,
    invoice_number: str,
    amount: Decimal,
    currency: str,
    issued_on: date,
    due_on: date,
    description: str,
) -> dict:
    common_fields = {
        "payee_name": payee.display_name,
        "amount": amount,
        "currency": currency,
        "issue_date": issued_on,
        "due_date": due_on,
        "invoice_number": invoice_number,
        "description": description,
        "payee_country": payee.attributes.get("country"),
        "bank_account": _identifier(payee, IdentifierKind.BANK_ACCOUNT),
        "payee_email": _identifier(payee, IdentifierKind.EMAIL),
        "category": payee.default_category,
        "category_confidence": CATEGORY_CONFIDENCE,
        "evidence": [
            {
                "field": "amount",
                "quote": f"Total: {currency} {format_amount(amount)}",
                "confidence": EXTRACTION_CONFIDENCE,
            },
            {"field": "currency", "quote": currency, "confidence": EXTRACTION_CONFIDENCE},
        ],
    }
    if payee.kind is PayeeKind.SERVICE:
        candidate = ServiceCandidate(
            **common_fields,
            provider_domain=_identifier(payee, IdentifierKind.DOMAIN),
            service_account_id=_identifier(payee, IdentifierKind.SERVICE_ACCOUNT_ID),
            billing_period_start=issued_on.replace(day=1),
            billing_period_end=issued_on,
        )
    elif payee.kind is PayeeKind.PERSON:
        candidate = PersonCandidate(
            **common_fields,
            national_id=_identifier(payee, IdentifierKind.TAX_ID),
            concept=description,
        )
    else:
        candidate = CompanyCandidate(
            **common_fields,
            legal_name=payee.display_name,
            tax_id=_identifier(payee, IdentifierKind.TAX_ID),
            purchase_order=None,
        )
    return candidate.model_dump(mode="json")


def _rule_results(
    payee: PayeeCreate | None,
    currency: str,
    overrides: dict[str, tuple[RuleEffect, str]] | None = None,
    include_checker: bool = False,
    payee_name: str | None = None,
) -> tuple[RuleResult, ...]:
    rule_ids = [rule_id for rule_id, _ in RULES]
    if include_checker:
        rule_ids.extend(CHECKER_RULE_IDS)
    category = payee.default_category if payee else PaymentCategory.CLOUD
    name = payee.display_name if payee else payee_name
    overridden_rules = overrides or {}
    return tuple(
        rule_result(rule_id, *overridden_rules[rule_id])
        if rule_id in overridden_rules
        else rule_result(
            rule_id,
            RuleEffect.PASS,
            PASS_REASONS[rule_id].format(payee=name, category=category, currency=currency),
        )
        for rule_id in rule_ids
    )


def _seed_quote(currency: str, offset: int, rate_date: date) -> FxQuote:
    if currency == USD:
        return FxQuote(
            currency=USD, usd_per_unit=Decimal("1"), rate_date=rate_date, source=FxSource.IDENTITY
        )
    return FxQuote(
        currency=currency,
        usd_per_unit=SEED_USD_PER_UNIT_BY_MONTH[offset][currency],
        rate_date=rate_date,
        source=FxSource.SEED,
    )


def _amount_text(amount: Decimal, currency: str, quote: FxQuote) -> str:
    original = f"{format_amount(amount)} {currency}"
    if currency == USD:
        return original
    return f"{original} ≈ {format_usd(quote.convert(amount))} (historical rate)"


def _decision_time(day: date) -> datetime:
    return datetime.combine(day, time(hour=DECISION_HOUR))


def _identifier(payee: PayeeCreate, kind: IdentifierKind) -> str | None:
    return next(
        (identifier.value for identifier in payee.identifiers if identifier.kind is kind), None
    )
