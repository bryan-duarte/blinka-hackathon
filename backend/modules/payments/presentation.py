from decimal import Decimal
from uuid import UUID

VISIBLE_ACCOUNT_DIGITS = 4
ACCOUNT_MASK = "••••"
THOUSANDS_PLACEHOLDER = "_"
SHORT_BILL_ID_CHARS = 8


def format_usd(amount: Decimal) -> str:
    return f"USD {format_amount(amount)}"


def format_amount(amount: Decimal) -> str:
    us_style = f"{amount:,.2f}"
    chilean_style = (
        us_style.replace(",", THOUSANDS_PLACEHOLDER)
        .replace(".", ",")
        .replace(THOUSANDS_PLACEHOLDER, ".")
    )
    return chilean_style


def mask_account(account: str) -> str:
    return f"{ACCOUNT_MASK}{account[-VISIBLE_ACCOUNT_DIGITS:]}"


def bill_label(invoice_number: str | None, bill_id: UUID) -> str:
    return invoice_number or str(bill_id)[:SHORT_BILL_ID_CHARS]
