from decimal import Decimal
from uuid import UUID

VISIBLE_ACCOUNT_DIGITS = 4
ACCOUNT_MASK = "••••"
SHORT_BILL_ID_CHARS = 8
RATE_SIGNIFICANT_DIGITS = 4


def format_usd(amount: Decimal) -> str:
    return f"USD {format_amount(amount)}"


def format_amount(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def format_rate(usd_per_unit: Decimal) -> str:
    rate_step = Decimal(1).scaleb(usd_per_unit.adjusted() - RATE_SIGNIFICANT_DIGITS + 1)
    return f"{usd_per_unit.quantize(rate_step).normalize():f}"


def mask_account(account: str) -> str:
    return f"{ACCOUNT_MASK}{account[-VISIBLE_ACCOUNT_DIGITS:]}"


def bill_label(invoice_number: str | None, bill_id: UUID) -> str:
    return invoice_number or str(bill_id)[:SHORT_BILL_ID_CHARS]
