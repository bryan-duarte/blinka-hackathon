from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from contracts._base import ApiModel, StrictModel

MAX_PROBABILITY = Decimal("1")
NAME_MAX_LENGTH = 200
IDENTIFIER_MAX_LENGTH = 200
REASON_MIN_LENGTH = 3
REASON_MAX_LENGTH = 300
CURRENCY_CODE_LENGTH = 3
DEFAULT_DUPLICATE_WINDOW_DAYS = 45
DEFAULT_MIN_FIELD_CONFIDENCE = Decimal("0.80")
DEFAULT_MIN_CATEGORY_CONFIDENCE = Decimal("0.70")
DEFAULT_CHECKER_REVIEW_LOW = Decimal("0.20")
DEFAULT_CHECKER_REVIEW_HIGH = Decimal("0.80")


class PayeeKind(StrEnum):
    SERVICE = "service"
    PERSON = "person"
    COMPANY = "company"


class PayeeStatus(StrEnum):
    ALLOWED = "allowed"
    BLACKLISTED = "blacklisted"


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "bank_transfer"
    CARD_ON_FILE = "card_on_file"
    PLATFORM_DEBIT = "platform_debit"


class PaymentCategory(StrEnum):
    CLOUD = "cloud"
    SAAS = "saas"
    CONTRACTOR = "contractor"
    PROFESSIONAL_SERVICES = "professional_services"
    UTILITIES = "utilities"
    RENT = "rent"
    MARKETING = "marketing"
    OTHER = "other"


class IdentifierKind(StrEnum):
    TAX_ID = "tax_id"
    BANK_ACCOUNT = "bank_account"
    SERVICE_ACCOUNT_ID = "service_account_id"
    EMAIL = "email"
    DOMAIN = "domain"
    ALIAS = "alias"


class PaymentPolicy(StrictModel):
    policy_id: UUID
    owner_id: UUID
    version: int
    hard_cap_per_payment_usd: Decimal
    auto_pay_max_usd: Decimal
    monthly_budget_usd: Decimal
    category_monthly_budgets_usd: dict[PaymentCategory, Decimal]
    allowed_categories: list[PaymentCategory]
    allowed_currencies: list[str]
    duplicate_window_days: int
    min_field_confidence: Decimal
    min_category_confidence: Decimal
    checker_review_low: Decimal
    checker_review_high: Decimal
    created_at: datetime


class PayeeIdentifierRecord(StrictModel):
    identifier_id: UUID
    payee_id: UUID
    kind: IdentifierKind
    normalized_value: str
    raw_value: str


class PayeeRecord(StrictModel):
    payee_id: UUID
    owner_id: UUID
    kind: PayeeKind
    display_name: str
    normalized_name: str
    status: PayeeStatus
    payment_method: PaymentMethod
    default_category: PaymentCategory | None
    currency: str
    per_payment_max_usd: Decimal | None
    monthly_budget_usd: Decimal | None
    agreed_amount_usd: Decimal | None
    agreed_tolerance_pct: Decimal | None
    attributes: dict[str, str]
    version: int


class BlacklistEntryRecord(StrictModel):
    entry_id: UUID
    owner_id: UUID
    kind: IdentifierKind
    normalized_value: str
    reason: str
    created_at: datetime


class PayeeMatch(StrictModel):
    payee: PayeeRecord | None
    matched_by: IdentifierKind | None
    identifier_owners: dict[str, UUID]
    unknown_identifiers: list[str]
    name_candidates: list[PayeeRecord]
    registered_bank_accounts: list[str]
    registered_senders: list[str]
    normalized_payee_name: str | None
    bill_bank_account: str | None
    sender_email: str | None
    sender_domain: str | None


class BlacklistHit(StrictModel):
    kind: IdentifierKind
    normalized_value: str
    reason: str


class PaymentPolicyUpdate(ApiModel):
    hard_cap_per_payment_usd: Decimal = Field(ge=0)
    auto_pay_max_usd: Decimal = Field(ge=0)
    monthly_budget_usd: Decimal = Field(ge=0)
    category_monthly_budgets_usd: dict[PaymentCategory, Decimal] = {}
    allowed_categories: list[PaymentCategory]
    allowed_currencies: list[str]
    duplicate_window_days: int = Field(default=DEFAULT_DUPLICATE_WINDOW_DAYS, ge=0)
    min_field_confidence: Decimal = Field(
        default=DEFAULT_MIN_FIELD_CONFIDENCE, ge=0, le=MAX_PROBABILITY
    )
    min_category_confidence: Decimal = Field(
        default=DEFAULT_MIN_CATEGORY_CONFIDENCE, ge=0, le=MAX_PROBABILITY
    )
    checker_review_low: Decimal = Field(
        default=DEFAULT_CHECKER_REVIEW_LOW, ge=0, le=MAX_PROBABILITY
    )
    checker_review_high: Decimal = Field(
        default=DEFAULT_CHECKER_REVIEW_HIGH, ge=0, le=MAX_PROBABILITY
    )

    @model_validator(mode="after")
    def _limits_are_consistent(self) -> Self:
        if self.auto_pay_max_usd > self.hard_cap_per_payment_usd:
            raise ValueError("auto_pay_max_usd must not exceed hard_cap_per_payment_usd")
        if self.checker_review_low > self.checker_review_high:
            raise ValueError("checker_review_low must not exceed checker_review_high")
        has_negative_category_budget = any(
            budget < 0 for budget in self.category_monthly_budgets_usd.values()
        )
        if has_negative_category_budget:
            raise ValueError("category budgets must not be negative")
        return self


class PaymentPolicyView(PaymentPolicyUpdate):
    policy_id: UUID
    version: int
    created_at: datetime


class PayeeIdentifierCreate(ApiModel):
    kind: IdentifierKind
    value: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)


class PayeeIdentifierView(ApiModel):
    identifier_id: UUID
    kind: IdentifierKind
    normalized_value: str
    raw_value: str


class PayeeCreate(ApiModel):
    kind: PayeeKind
    display_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    status: PayeeStatus = PayeeStatus.ALLOWED
    payment_method: PaymentMethod
    default_category: PaymentCategory | None = None
    currency: str = Field(min_length=CURRENCY_CODE_LENGTH, max_length=CURRENCY_CODE_LENGTH)
    per_payment_max_usd: Decimal | None = Field(default=None, ge=0)
    monthly_budget_usd: Decimal | None = Field(default=None, ge=0)
    agreed_amount_usd: Decimal | None = Field(default=None, ge=0)
    agreed_tolerance_pct: Decimal | None = Field(default=None, ge=0)
    attributes: dict[str, str] = {}
    identifiers: list[PayeeIdentifierCreate] = []


class PayeeUpdate(ApiModel):
    version: int
    display_name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    status: PayeeStatus | None = None
    payment_method: PaymentMethod | None = None
    default_category: PaymentCategory | None = None
    currency: str | None = Field(
        default=None, min_length=CURRENCY_CODE_LENGTH, max_length=CURRENCY_CODE_LENGTH
    )
    per_payment_max_usd: Decimal | None = Field(default=None, ge=0)
    monthly_budget_usd: Decimal | None = Field(default=None, ge=0)
    agreed_amount_usd: Decimal | None = Field(default=None, ge=0)
    agreed_tolerance_pct: Decimal | None = Field(default=None, ge=0)
    attributes: dict[str, str] | None = None


class PayeeView(ApiModel):
    payee_id: UUID
    kind: PayeeKind
    display_name: str
    status: PayeeStatus
    payment_method: PaymentMethod
    default_category: PaymentCategory | None
    currency: str
    per_payment_max_usd: Decimal | None
    monthly_budget_usd: Decimal | None
    agreed_amount_usd: Decimal | None
    agreed_tolerance_pct: Decimal | None
    attributes: dict[str, str]
    version: int
    identifiers: list[PayeeIdentifierView]


class BlacklistEntryCreate(ApiModel):
    kind: IdentifierKind
    value: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    reason: str = Field(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH)


class BlacklistEntryView(ApiModel):
    entry_id: UUID
    kind: IdentifierKind
    normalized_value: str
    reason: str
    created_at: datetime
