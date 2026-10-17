import hashlib
from datetime import date
from decimal import Decimal
from uuid import UUID

from core.identifiers import canonical_identifier

FINGERPRINT_SEPARATOR = "|"
DUE_DATE_PREFIX = "due:"


def sha256_hex(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


def bill_fingerprint(
    owner_id: UUID,
    payee_key: str | None,
    invoice_number: str | None,
    due_date: date | None,
    amount: Decimal | None,
    currency: str | None,
) -> str | None:
    is_identifiable = bool(payee_key) and amount is not None
    if not is_identifiable:
        return None
    number_part = invoice_number or f"{DUE_DATE_PREFIX}{due_date or ''}"
    fingerprint_parts = (str(owner_id), payee_key, number_part, f"{amount:.2f}", currency or "")
    return sha256_hex(FINGERPRINT_SEPARATOR.join(fingerprint_parts).encode())


def normalize_invoice_number(invoice_number: str | None) -> str | None:
    if not invoice_number:
        return None
    return canonical_identifier(invoice_number) or None
