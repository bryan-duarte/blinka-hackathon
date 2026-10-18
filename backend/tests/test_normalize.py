from datetime import date
from decimal import Decimal
from uuid import uuid4

from contracts.fx import FxQuote, FxSource
from contracts.payment_candidates import PersonCandidate
from contracts.payment_policy import IdentifierKind
from modules.bills.hashing import bill_fingerprint, normalize_invoice_number
from modules.payment_policy.normalize import (
    normalize_domain,
    normalize_identifier,
    normalize_name,
    strong_identifiers,
)
from modules.payments.fx import names_currency_explicitly
from modules.payments.presentation import format_usd, mask_account


def test_names_drop_accents_case_and_legal_suffixes():
    assert normalize_name("Servicios Integrales del Sur SpA") == "servicios integrales del sur"
    assert normalize_name("ACME Cloud, Inc.") == "acme cloud"
    assert normalize_name("María José Pérez") == "maria jose perez"
    assert normalize_name("Amaz0n Web Services") != normalize_name("Amazon Web Services")


def test_identifiers_normalize_to_comparable_values():
    assert normalize_identifier(IdentifierKind.TAX_ID, "76.543.210-k") == "76543210K"
    assert normalize_identifier(IdentifierKind.BANK_ACCOUNT, "CL-BE-99887766") == "CLBE99887766"
    assert normalize_identifier(IdentifierKind.EMAIL, "Billing <Billing@ACME.io>") == (
        "billing@acme.io"
    )
    assert normalize_domain("https://www.aws.amazon.com/billing") == "aws.amazon.com"
    assert normalize_domain("no-reply@aws.amazon.com") == "aws.amazon.com"


def test_strong_identifiers_include_bill_and_sender():
    candidate = PersonCandidate(
        payee_name="María",
        amount=Decimal("900"),
        currency="USD",
        issue_date=None,
        due_date=None,
        invoice_number=None,
        description=None,
        bank_account="CL-BE-99887766",
        payee_email=None,
        category=None,
        category_confidence=0.9,
        national_id="15.234.567-8",
        concept=None,
    )

    assert strong_identifiers(candidate, "maria@gmail.com") == [
        (IdentifierKind.BANK_ACCOUNT, "CLBE99887766"),
        (IdentifierKind.TAX_ID, "152345678"),
        (IdentifierKind.EMAIL, "maria@gmail.com"),
        (IdentifierKind.DOMAIN, "gmail.com"),
    ]


def test_fingerprint_uses_due_date_when_number_is_missing():
    owner_id = uuid4()
    first = bill_fingerprint(owner_id, "payee", None, date(2026, 10, 31), Decimal("900"), "USD")
    second = bill_fingerprint(owner_id, "payee", None, date(2026, 11, 15), Decimal("900"), "USD")
    same = bill_fingerprint(owner_id, "payee", None, date(2026, 10, 31), Decimal("900.00"), "USD")

    assert first != second
    assert first == same
    assert bill_fingerprint(owner_id, None, "A1", None, Decimal("1"), "USD") is None
    assert normalize_invoice_number("INV-2048") == normalize_invoice_number("inv 2048")


def test_money_formatting_and_conversion():
    clp_quote = FxQuote(
        currency="CLP",
        usd_per_unit=Decimal("0.00105"),
        rate_date=date(2026, 10, 17),
        source=FxSource.STATIC_FALLBACK,
    )
    assert clp_quote.convert(Decimal("1400000")) == Decimal("1470.00")
    assert format_usd(Decimal("1250")) == "USD 1,250.00"
    assert mask_account("CLBE99887766") == "••••7766"


def test_explicit_currency_markers():
    assert names_currency_explicitly("Total: 1.500 dólares", "USD")
    assert names_currency_explicitly("120 euros", "EUR")
    assert names_currency_explicitly("Total: CLP 1.400.000", "CLP")
    assert not names_currency_explicitly("Total: $119.000", "CLP")
