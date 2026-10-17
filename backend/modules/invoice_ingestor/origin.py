import re

from contracts.payment_candidates import (
    DocumentIssuer,
    DocumentOrigin,
    FieldEvidence,
    PaymentCandidateBase,
)
from core.tax_jurisdictions import bank_account_country, infer_tax_id_country, tax_id_fits_country
from modules.invoice_ingestor.candidates import payee_tax_id

ISSUER_TAX_COUNTRY_FIELD = "issuer_tax_country"
BANK_ACCOUNT_COUNTRY_FIELD = "bank_account_country"
ISO_COUNTRY_CODE = re.compile(r"[A-Z]{2}")
TAX_ID_SHAPE_CONFIDENCE = 0.9
TAX_ID_MISMATCH_CONFIDENCE = 0.5
BANK_ACCOUNT_CHECKSUM_CONFIDENCE = 1.0


def resolve_countries(
    candidate: PaymentCandidateBase, origin: DocumentOrigin | None
) -> PaymentCandidateBase:
    added_evidence: list[FieldEvidence] = []
    tax_id = payee_tax_id(candidate)
    issuer_tax_country = _issuer_tax_country(candidate, origin, tax_id, added_evidence)
    bank_country = bank_account_country(candidate.bank_account)
    if bank_country is not None and candidate.bank_account:
        added_evidence.append(
            FieldEvidence(
                field=BANK_ACCOUNT_COUNTRY_FIELD,
                quote=candidate.bank_account,
                confidence=BANK_ACCOUNT_CHECKSUM_CONFIDENCE,
            )
        )
    kept_evidence = _evidence_with_tax_id_agreement(candidate, issuer_tax_country, tax_id)
    return candidate.model_copy(
        update={
            "payee_country": _iso_country(candidate.payee_country),
            "issuer_tax_country": issuer_tax_country,
            "bank_account_country": bank_country,
            "evidence": [*kept_evidence, *added_evidence],
        }
    )


def _issuer_tax_country(
    candidate: PaymentCandidateBase,
    origin: DocumentOrigin | None,
    tax_id: str | None,
    added_evidence: list[FieldEvidence],
) -> str | None:
    is_buyer_issued = origin is not None and origin.issued_by is DocumentIssuer.BUYER
    if is_buyer_issued:
        return None
    stated_country = _iso_country(candidate.issuer_tax_country)
    if stated_country is not None:
        return stated_country
    inferred_country = infer_tax_id_country(tax_id)
    if inferred_country is not None and tax_id:
        added_evidence.append(
            FieldEvidence(
                field=ISSUER_TAX_COUNTRY_FIELD, quote=tax_id, confidence=TAX_ID_SHAPE_CONFIDENCE
            )
        )
    return inferred_country


def _evidence_with_tax_id_agreement(
    candidate: PaymentCandidateBase, issuer_tax_country: str | None, tax_id: str | None
) -> list[FieldEvidence]:
    contradicts_tax_id = tax_id_fits_country(tax_id, issuer_tax_country) is False
    if not contradicts_tax_id:
        return list(candidate.evidence)
    return [
        evidence.model_copy(update={"confidence": TAX_ID_MISMATCH_CONFIDENCE})
        if evidence.field == ISSUER_TAX_COUNTRY_FIELD
        else evidence
        for evidence in candidate.evidence
    ]


def _iso_country(raw_country: str | None) -> str | None:
    normalized_country = (raw_country or "").strip().upper()
    return normalized_country if ISO_COUNTRY_CODE.fullmatch(normalized_country) else None
