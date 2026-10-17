from contracts.payment_candidates import (
    CANDIDATE_SCHEMAS,
    DocumentFields,
    PaymentCandidateBase,
)
from contracts.payment_policy import PayeeKind

UNKNOWN_CATEGORY_CONFIDENCE = 0.0
COMMON_DOCUMENT_FIELDS = (
    "payee_name",
    "amount",
    "currency",
    "payee_country",
    "issuer_tax_country",
    "invoice_number",
    "issue_date",
    "due_date",
)
EMPTY_KIND_FIELDS: dict[PayeeKind, dict[str, None]] = {
    PayeeKind.SERVICE: {
        "provider_domain": None,
        "service_account_id": None,
        "billing_period_start": None,
        "billing_period_end": None,
    },
    PayeeKind.PERSON: {"national_id": None, "concept": None},
    PayeeKind.COMPANY: {
        "legal_name": None,
        "tax_id": None,
        "purchase_order": None,
    },
}


def candidate_from_document(kind: PayeeKind, fields: DocumentFields) -> PaymentCandidateBase:
    empty_candidate = CANDIDATE_SCHEMAS[kind](
        payee_name=None,
        amount=None,
        currency=None,
        issue_date=None,
        due_date=None,
        invoice_number=None,
        description=None,
        bank_account=None,
        payee_email=None,
        category=None,
        category_confidence=UNKNOWN_CATEGORY_CONFIDENCE,
        **EMPTY_KIND_FIELDS[kind],
    )
    return overlay_document(empty_candidate, fields)


def overlay_document(
    candidate: PaymentCandidateBase, fields: DocumentFields
) -> PaymentCandidateBase:
    document_values = {
        **{name: getattr(fields, name) for name in COMMON_DOCUMENT_FIELDS},
        **_kind_document_values(candidate.kind, fields),
    }
    present_values = {name: value for name, value in document_values.items() if value is not None}
    overridden_fields = set(present_values)
    kept_evidence = [
        evidence for evidence in candidate.evidence if evidence.field not in overridden_fields
    ]
    return candidate.model_copy(
        update={**present_values, "evidence": [*fields.evidence, *kept_evidence]}
    )


def _kind_document_values(kind: PayeeKind, fields: DocumentFields) -> dict[str, object]:
    if kind is PayeeKind.COMPANY:
        return {"legal_name": fields.payee_name, "tax_id": fields.tax_id}
    if kind is PayeeKind.PERSON:
        return {"national_id": fields.tax_id}
    return {}


def has_payee_and_amount(candidate: PaymentCandidateBase) -> bool:
    return candidate.payee_name is not None and candidate.amount is not None


def payee_tax_id(candidate: PaymentCandidateBase) -> str | None:
    return getattr(candidate, "tax_id", None) or getattr(candidate, "national_id", None)
