import re
from datetime import date
from decimal import Decimal, InvalidOperation

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from contracts.payment_candidates import DocumentFields, ExpenseReading, FieldEvidence
from modules.document_vision.errors import DocumentVisionError

PERCENT_SCALE = 100
ISO_DATE_LENGTH = 10
MAX_DECIMAL_DIGITS = 2
LINE_BLOCK_TYPE = "LINE"
AMOUNT_FIELD_PRIORITY = ("TOTAL", "AMOUNT_DUE")
ISO_CURRENCY_CODE = re.compile(r"\b[A-Z]{3}\b")
NON_NUMERIC_AMOUNT_CHARACTERS = re.compile(r"[^\d.,]")
AMOUNT_SEPARATORS = re.compile(r"[.,]")

SummaryField = dict


class TextractExpenseReader:
    def __init__(self, aws_profile: str | None, region: str) -> None:
        self._session = aioboto3.Session(profile_name=aws_profile, region_name=region)
        self._client_context = self._session.client("textract")
        self._client = None

    async def _expense_client(self):
        if self._client is None:
            self._client = await self._client_context.__aenter__()
        return self._client

    async def read_expense(self, document: bytes) -> ExpenseReading:
        try:
            client = await self._expense_client()
            response = await client.analyze_expense(Document={"Bytes": document})
        except (ClientError, BotoCoreError) as error:
            raise DocumentVisionError(type(error).__name__) from error
        expense_documents = response.get("ExpenseDocuments") or []
        if not expense_documents:
            return ExpenseReading(fields=DocumentFields())
        first_document = expense_documents[0]
        return ExpenseReading(
            fields=_document_fields(_best_fields_by_type(first_document)),
            text=_line_text(first_document),
        )


def _best_fields_by_type(expense_document: dict) -> dict[str, SummaryField]:
    best_fields: dict[str, SummaryField] = {}
    for summary_field in expense_document.get("SummaryFields") or []:
        field_type = (summary_field.get("Type") or {}).get("Text")
        has_value = bool(_value_text(summary_field))
        if not field_type or not has_value:
            continue
        current_best = best_fields.get(field_type)
        if current_best is None or _confidence(summary_field) > _confidence(current_best):
            best_fields[field_type] = summary_field
    return best_fields


def _document_fields(fields_by_type: dict[str, SummaryField]) -> DocumentFields:
    evidence: list[FieldEvidence] = []
    amount_field = next(
        (fields_by_type[label] for label in AMOUNT_FIELD_PRIORITY if label in fields_by_type),
        None,
    )
    payee_name = _recorded_text(evidence, "payee_name", fields_by_type.get("VENDOR_NAME"))
    tax_id = _recorded_text(evidence, "tax_id", fields_by_type.get("TAX_PAYER_ID"))
    invoice_number = _recorded_text(
        evidence, "invoice_number", fields_by_type.get("INVOICE_RECEIPT_ID")
    )
    amount = _parse_amount(_value_text(amount_field)) if amount_field else None
    if amount is not None:
        _record(evidence, "amount", amount_field)
    currency = _currency(amount_field) if amount_field else None
    if currency is not None:
        _record(evidence, "currency", amount_field, _currency_confidence(amount_field))
    return DocumentFields(
        payee_name=payee_name,
        tax_id=tax_id,
        amount=amount,
        currency=currency,
        invoice_number=invoice_number,
        issue_date=_parse_iso_date(fields_by_type.get("INVOICE_RECEIPT_DATE")),
        due_date=_parse_iso_date(fields_by_type.get("DUE_DATE")),
        evidence=evidence,
    )


def _recorded_text(
    evidence: list[FieldEvidence], field: str, summary_field: SummaryField | None
) -> str | None:
    if summary_field is None:
        return None
    _record(evidence, field, summary_field)
    return _value_text(summary_field)


def _record(
    evidence: list[FieldEvidence],
    field: str,
    summary_field: SummaryField,
    confidence: float | None = None,
) -> None:
    evidence.append(
        FieldEvidence(
            field=field,
            quote=_value_text(summary_field),
            confidence=_confidence(summary_field) if confidence is None else confidence,
        )
    )


def _value_text(summary_field: SummaryField) -> str:
    return ((summary_field.get("ValueDetection") or {}).get("Text") or "").strip()


def _confidence(summary_field: SummaryField) -> float:
    raw_confidence = (summary_field.get("ValueDetection") or {}).get("Confidence") or 0
    return min(raw_confidence / PERCENT_SCALE, 1.0)


def _currency_confidence(amount_field: SummaryField) -> float:
    detected_confidence = (amount_field.get("Currency") or {}).get("Confidence")
    if detected_confidence is None:
        return _confidence(amount_field)
    return min(detected_confidence / PERCENT_SCALE, 1.0)


def _line_text(expense_document: dict) -> str | None:
    lines = [
        block.get("Text", "")
        for block in expense_document.get("Blocks") or []
        if block.get("BlockType") == LINE_BLOCK_TYPE and block.get("Text")
    ]
    return "\n".join(lines) or None


def _currency(amount_field: SummaryField) -> str | None:
    detected_code = ((amount_field.get("Currency") or {}).get("Code") or "").upper()
    if ISO_CURRENCY_CODE.fullmatch(detected_code):
        return detected_code
    code_in_text = ISO_CURRENCY_CODE.search(_value_text(amount_field).upper())
    return code_in_text.group() if code_in_text else None


def _parse_amount(amount_text: str) -> Decimal | None:
    numeric_text = NON_NUMERIC_AMOUNT_CHARACTERS.sub("", amount_text)
    if not numeric_text:
        return None
    last_separator = max(numeric_text.rfind("."), numeric_text.rfind(","))
    decimal_digits = len(numeric_text) - last_separator - 1
    has_decimal_part = last_separator != -1 and 0 < decimal_digits <= MAX_DECIMAL_DIGITS
    if has_decimal_part:
        integer_part = AMOUNT_SEPARATORS.sub("", numeric_text[:last_separator])
        normalized_amount = f"{integer_part or '0'}.{numeric_text[last_separator + 1 :]}"
    else:
        normalized_amount = AMOUNT_SEPARATORS.sub("", numeric_text)
    try:
        return Decimal(normalized_amount)
    except InvalidOperation:
        return None


def _parse_iso_date(summary_field: SummaryField | None) -> date | None:
    if summary_field is None:
        return None
    try:
        return date.fromisoformat(_value_text(summary_field)[:ISO_DATE_LENGTH])
    except ValueError:
        return None
