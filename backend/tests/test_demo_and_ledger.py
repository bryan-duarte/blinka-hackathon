import io
import zipfile
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from contracts.accountability import (
    DecisionLedgerRow,
    InboxLedgerRow,
    LedgerEntryView,
    LedgerOutcome,
)
from contracts.bills import BillSourceType, BillStatus
from contracts.demo import KitDestinations
from contracts.inbox import InboxEmailStatus
from contracts.payments import DecisionActor, RunStatus, Verdict
from modules.accountability.csv_export import write_ledger_csv
from modules.accountability.service import to_decision_outcome, to_inbox_outcome
from modules.demo.catalog import DEMO_SCENARIOS, SCENARIOS_BY_ID, LaunchContext
from modules.demo.kit import build_kit_zip, kit_nonce
from modules.demo.seed_data import (
    ANDRES,
    AWS,
    DEMO_PAYEES_BY_NAME,
    DEMO_POLICY,
    history,
    month_start,
)
from modules.fx import STATIC_USD_PER_UNIT

TODAY = date(2026, 10, 17)
EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


def _decision_row(**changes: object) -> DecisionLedgerRow:
    fields = {
        "decision_id": uuid4(),
        "decided_at": datetime(2026, 10, 17, 10),
        "actor": DecisionActor.AGENT,
        "verdict": Verdict.PAY,
        "rule_results": [],
        "explanation": "",
        "note": None,
        "run_id": None,
        "bill_id": uuid4(),
        "bill_status": BillStatus.PAID,
        "duplicate_of_bill_id": None,
        "payee_id": None,
        "payee_name": None,
        "payee_kind": None,
        "category": None,
        "amount": None,
        "currency": None,
        "amount_usd": None,
        "fx_usd_per_unit": None,
        "fx_rate_date": None,
        "fx_source": None,
        "source_type": None,
        "inbox_email_id": None,
        "subject": None,
    }
    return DecisionLedgerRow(**{**fields, **changes})


def _inbox_row(**changes: object) -> InboxLedgerRow:
    fields = {
        "inbox_email_id": uuid4(),
        "occurred_at": datetime(2026, 10, 17, 10),
        "status": InboxEmailStatus.ANALYZING,
        "violations": [],
        "error": None,
        "subject": "",
        "source_type": BillSourceType.EMAIL,
        "run_id": uuid4(),
        "run_status": RunStatus.COMPLETED,
        "has_extraction_failed": False,
    }
    return InboxLedgerRow(**{**fields, **changes})


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, LedgerOutcome.PAID),
        ({"verdict": Verdict.REVIEW}, LedgerOutcome.ESCALATED),
        ({"verdict": Verdict.HOLD}, LedgerOutcome.HELD),
        (
            {
                "verdict": Verdict.HOLD,
                "duplicate_of_bill_id": uuid4(),
                "rule_results": [{"rule_id": "DUP", "effect": "hold"}],
            },
            LedgerOutcome.DUPLICATE,
        ),
        ({"actor": DecisionActor.HUMAN}, LedgerOutcome.APPROVED_BY_HUMAN),
        (
            {
                "actor": DecisionActor.HUMAN,
                "verdict": Verdict.HOLD,
                "bill_status": BillStatus.REJECTED,
            },
            LedgerOutcome.REJECTED_BY_HUMAN,
        ),
        (
            {"actor": DecisionActor.HUMAN, "verdict": Verdict.HOLD, "bill_status": BillStatus.HELD},
            LedgerOutcome.HELD,
        ),
    ],
)
def test_decision_outcomes(changes: dict, expected: LedgerOutcome):
    assert to_decision_outcome(_decision_row(**changes)) is expected


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"status": InboxEmailStatus.BLOCKED, "run_id": None}, LedgerOutcome.BLOCKED),
        ({"status": InboxEmailStatus.DUPLICATE, "run_id": None}, LedgerOutcome.DUPLICATE),
        ({"run_status": RunStatus.FAILED}, LedgerOutcome.ERROR),
        ({"has_extraction_failed": True}, LedgerOutcome.MISSING_INFO),
        ({}, LedgerOutcome.NOT_AN_INVOICE),
    ],
)
def test_inbox_outcomes(changes: dict, expected: LedgerOutcome):
    assert to_inbox_outcome(_inbox_row(**changes)) is expected


def test_csv_export_neutralizes_formulas():
    entry = LedgerEntryView(
        entry_id=uuid4(),
        occurred_at=datetime(2026, 10, 17, 10),
        outcome=LedgerOutcome.BLOCKED,
        actor=DecisionActor.AGENT,
        payee_id=None,
        payee_name='=HYPERLINK("http://evil")',
        payee_kind=None,
        category=None,
        amount=None,
        currency=None,
        amount_usd=None,
        fx_usd_per_unit=None,
        fx_rate_date=None,
        fx_source=None,
        reasons=[],
        explanation="-2+3",
        note="@SUM(A1)",
        channel=BillSourceType.EMAIL,
        subject="+cmd",
        bill_id=None,
        run_id=None,
        inbox_email_id=None,
        is_seeded=False,
    )

    data_row = write_ledger_csv([entry]).splitlines()[1]

    for unsafe in ("=HYPERLINK", "-2+3", "@SUM", "+cmd"):
        assert f"'{unsafe}" in data_row


def test_seed_history_leaves_room_for_the_limit_scenarios():
    current_month = month_start(TODAY, 0)
    current_bills = [bill for bill in history(TODAY) if bill.paid_at.date() >= current_month]
    usd_by_payee = {bill.payee_name: bill.amount_usd for bill in current_bills}
    andres_limit = DEMO_PAYEES_BY_NAME[ANDRES].monthly_budget_usd

    assert usd_by_payee[ANDRES] <= andres_limit
    assert usd_by_payee[ANDRES] > andres_limit - Decimal("1")
    assert usd_by_payee[AWS] < DEMO_POLICY.category_monthly_budgets_usd["cloud"]


def test_seed_history_dates_stay_inside_their_month_on_month_edges():
    for today in (date(2026, 10, 1), date(2026, 3, 31), date(2027, 1, 1)):
        bills = history(today)
        current_month = month_start(today, 0)
        assert all(bill.paid_at.date() <= today for bill in bills)
        assert sum(bill.paid_at.date() >= current_month for bill in bills) == 3


def test_every_scenario_builds_and_duplicate_steps_reuse_the_same_file():
    context = LaunchContext(today=TODAY, nonce=4321)

    for scenario in DEMO_SCENARIOS:
        for step in scenario.steps:
            assert step.build(context).sender

    resend = SCENARIOS_BY_ID["dup_exact_resend"].steps
    first, second = (step.build(context).attachments[0].content for step in resend)
    assert first == second


def test_kit_is_deterministic_and_never_ships_the_eicar_file():
    destinations = KitDestinations(email_address="demo@inbox.test", whatsapp_number=None)

    kit = build_kit_zip(list(DEMO_SCENARIOS), TODAY, destinations, is_guardrail_enforced=True)

    with zipfile.ZipFile(io.BytesIO(kit)) as archive:
        contents = b"".join(archive.read(name) for name in archive.namelist())
        readme = archive.read("demo-kit/README.md").decode()
    assert EICAR_MARKER not in contents
    assert "demo@inbox.test" in readme
    assert kit_nonce(DEMO_SCENARIOS[0]) == 7000
    assert kit == build_kit_zip(list(DEMO_SCENARIOS), TODAY, destinations, True)


def test_professional_services_budget_fits_every_scenario_in_the_category():
    seeded_usd = sum(
        bill.amount_usd
        for bill in history(TODAY)
        if bill.paid_at.date() >= month_start(TODAY, 0) and bill.category == "professional_services"
    )
    scenario_amounts = {
        "CLP": ["1180000", "1050000", "1100000", "1249500", "450000"],
        "EUR": ["1850", "3000"],
        "MXN": ["33250"],
    }
    scenario_usd = sum(
        Decimal(amount) * STATIC_USD_PER_UNIT[currency]
        for currency, amounts in scenario_amounts.items()
        for amount in amounts
    )

    budget = DEMO_POLICY.category_monthly_budgets_usd["professional_services"]
    assert seeded_usd + scenario_usd < budget
