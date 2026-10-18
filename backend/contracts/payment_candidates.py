from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from contracts._base import ApiModel, StrictModel
from contracts.payment_policy import PayeeKind, PaymentCategory

MIN_CONFIDENCE = 0
MAX_CONFIDENCE = 1
LEGACY_COUNTRY_FIELD = "country"


class FieldEvidence(ApiModel):
    field: str
    quote: str = Field(description="Exact text copied from the email body or the PDF.")
    confidence: float = Field(ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)


class PaymentCandidateBase(ApiModel):
    kind: PayeeKind
    payee_name: str | None
    amount: Decimal | None = Field(description="Total to pay, plain number with '.' decimals.")
    currency: str | None = Field(
        description="ISO 4217 code only when explicit in the document; a bare '$' is null."
    )
    issue_date: date | None
    due_date: date | None
    invoice_number: str | None
    description: str | None
    payee_country: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 code of the payee's country, from its address.",
    )
    issuer_tax_country: SkipJsonSchema[str | None] = None
    bank_account_country: SkipJsonSchema[str | None] = None
    bank_account: str | None = Field(description="Destination account written on the bill.")
    payee_email: str | None
    category: PaymentCategory | None
    category_confidence: float = Field(ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)
    embedded_instructions: list[str] = Field(
        default=[], description="Verbatim sentences addressed to an AI, agent or payment system."
    )
    evidence: list[FieldEvidence] = []

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_country(cls, raw_candidate: object) -> object:
        is_legacy_payload = isinstance(raw_candidate, dict) and LEGACY_COUNTRY_FIELD in (
            raw_candidate
        )
        if not is_legacy_payload:
            return raw_candidate
        migrated_candidate = dict(raw_candidate)
        legacy_country = migrated_candidate.pop(LEGACY_COUNTRY_FIELD)
        migrated_candidate.setdefault("payee_country", legacy_country)
        return migrated_candidate


class ServiceCandidate(PaymentCandidateBase):
    """Call once with the bill of a platform or subscription (cloud, SaaS, utilities)."""

    kind: Literal[PayeeKind.SERVICE] = PayeeKind.SERVICE
    provider_domain: str | None
    service_account_id: str | None
    billing_period_start: date | None
    billing_period_end: date | None


class PersonCandidate(PaymentCandidateBase):
    """Call once with the bill (cuenta de cobro, honorarios) of an individual person."""

    kind: Literal[PayeeKind.PERSON] = PayeeKind.PERSON
    national_id: str | None
    concept: str | None


class CompanyCandidate(PaymentCandidateBase):
    """Call once with the invoice of a legal entity selling goods or professional services."""

    kind: Literal[PayeeKind.COMPANY] = PayeeKind.COMPANY
    legal_name: str | None
    tax_id: str | None
    purchase_order: str | None


PaymentCandidate = Annotated[
    ServiceCandidate | PersonCandidate | CompanyCandidate, Field(discriminator="kind")
]

CANDIDATE_SCHEMAS: dict[PayeeKind, type[PaymentCandidateBase]] = {
    PayeeKind.SERVICE: ServiceCandidate,
    PayeeKind.PERSON: PersonCandidate,
    PayeeKind.COMPANY: CompanyCandidate,
}


class BillClassification(ApiModel):
    """Call once. Decide if the document is a bill to pay and who gets paid."""

    is_bill: bool
    kind: PayeeKind | None
    reason: str = Field(description="One sentence in English.")
    confidence: float = Field(ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)


class ExtractionMethod(StrEnum):
    XML = "xml"
    XML_LLM = "xml_llm"
    TEXTRACT = "textract"
    PDF_TEXT_LLM = "pdf_text"
    PDF_FILE_LLM = "pdf"
    EMAIL_LLM = "email"


class XmlInvoiceFormat(StrEnum):
    CFDI_MX = "cfdi_mx"
    DTE_CL = "dte_cl"
    UBL = "ubl"
    CII = "cii"
    SRI_EC = "sri_ec"
    UNKNOWN = "unknown"


class DocumentFields(StrictModel):
    payee_name: str | None = None
    tax_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    payee_country: str | None = None
    issuer_tax_country: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    evidence: list[FieldEvidence] = []

    @property
    def is_sufficient(self) -> bool:
        return self.payee_name is not None and self.amount is not None


class ExpenseReading(StrictModel):
    fields: DocumentFields
    text: str | None = None


class DocumentIssuer(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"


class DocumentOrigin(StrictModel):
    country: str
    standard: str
    authority: str
    signal: str
    issued_by: DocumentIssuer = DocumentIssuer.SELLER


class ParsedXmlInvoice(StrictModel):
    format: XmlInvoiceFormat
    fields: DocumentFields
    origin: DocumentOrigin | None = None


class CandidateExtraction(StrictModel):
    candidate: PaymentCandidate
    method: ExtractionMethod
    origin: DocumentOrigin | None = None
