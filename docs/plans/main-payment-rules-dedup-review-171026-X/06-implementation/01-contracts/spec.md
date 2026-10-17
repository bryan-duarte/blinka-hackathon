# Contracts Implementation

## Overview

These are the Pydantic types every other module of this plan imports. Field lists are fixed in `03-design.md` § Data Structures. This spec covers how to lay them out.

## Files to Modify/Create

- `contracts/payment_policy.py` (new). Enums: `PayeeKind`, `PayeeStatus`, `PaymentMethod`, `PaymentCategory`, `IdentifierKind`.
  - Records (`StrictModel`): `PaymentPolicy`, `PayeeRecord`, `PayeeIdentifierRecord`, `BlacklistEntryRecord`, `PayeeMatch`, `BlacklistHit`.
  - API models (`ApiModel`): `PaymentPolicyView`, `PaymentPolicyUpdate`, `PayeeView`, `PayeeCreate`, `PayeeUpdate`, `PayeeIdentifierCreate`, `BlacklistEntryView`, `BlacklistEntryCreate`.
- `contracts/payment_candidates.py` (new). `FieldEvidence`, `PaymentCandidateBase`, `ServiceCandidate`, `PersonCandidate`, `CompanyCandidate`, the `PaymentCandidate` annotated union, `BillClassification`, and `CANDIDATE_SCHEMAS: dict[PayeeKind, type[PaymentCandidateBase]]`. All are `ApiModel`, because the LLM produces them.
- `contracts/bills.py` (new). `BillSourceType`, `BillStatus`, `BillSourceIntake` (Strict), `SourceRegistration` (Strict), `BillSourceRecord` (Strict), `BillRecord` (Strict), `BillClaim` (Strict), `BillSummary` (Strict), `BillSourceView` (Api).
- `contracts/payments.py` (rewrite).
  - Keep `RunStatus`, `PaymentRunRecord`, `PaymentRunEvent`.
  - `PaymentRunTrigger` becomes `{bill_source_id, session_id}`.
  - `PaymentRunAccepted` gains `duplicate: bool = False`.
  - Add `Verdict`, `RuleEffect`, `DecisionActor`, `LedgerStatus`, `RuleResult`, `CheckerAnswer`, `CheckerAssessment`, `DecisionRecord` (Strict), `BillDecisionView`, `BillDetail`, `PaymentView`, `BudgetUsageView`, `ReviewActionRequest`, `UploadRunRequest{file_id}`.
  - `PaymentRunStatus` replaces `analysis` with `decision` and `is_bill`.
  - Delete `ClpConversion` and `InvoiceClpAnalysis`.
- `contracts/inbox.py`. In `InboxEmailStatus`, remove `ANALYZED` and add `PAID`, `HELD`, `REVIEW`, `DUPLICATE`. In `InboxEmailView`, `analysis: InvoiceClpAnalysis | None` becomes `decision: BillDecisionView | None = None`.
- `contracts/prompts.py`. `PromptId` gains `BILL_CLASSIFICATION`, `SERVICE_EXTRACTION`, `PERSON_EXTRACTION`, `COMPANY_EXTRACTION`, `PAYMENT_CHECKER`, and loses `INVOICE_EXTRACTION` and `PAYMENT_AGENT`.
- `contracts/invoices.py`: delete.

## Implementation Guidelines

Orientative snippets follow.

```python
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


class PayeeMatch(StrictModel):
    payee: PayeeRecord | None
    matched_by: IdentifierKind | None
    identifier_owners: dict[str, UUID]   # f"{kind}:{normalized}" -> payee_id, for every strong identifier on the bill
    unknown_identifiers: list[str]       # strong identifiers present on the bill and not registered
    name_candidates: list[PayeeRecord]   # name/alias matches, used for R04/R05 messages
    registered_bank_accounts: list[str]  # of the matched payee
    registered_senders: list[str]        # EMAIL/DOMAIN identifiers of the matched payee
    bill_bank_account: str | None        # candidate.bank_account normalized, so rules stay pure
    sender_email: str | None             # normalized sender address
    sender_domain: str | None            # normalized sender domain


class BillSourceIntake(StrictModel):
    owner_id: UUID
    source_type: BillSourceType
    source_ref: str
    sender: str
    body_text: str
    file_id: UUID | None
    attachment_sha256: str | None
    inbox_email_id: UUID | None = None
    received_at: datetime | None = None


class SourceRegistration(StrictModel):
    source: BillSourceRecord
    is_new: bool


class BillClaim(StrictModel):
    bill: BillRecord
    duplicate_of: BillRecord | None   # set when a uniqueness conflict made this a duplicate
```

- In `PaymentPolicyUpdate`, add a `model_validator(mode="after")` that raises when `auto_pay_max_usd > hard_cap_per_payment_usd` or any amount is negative. The router turns the resulting `ValidationError` into a 422 automatically.
- `PayeeCreate` takes `kind`, `display_name`, `status`, `payment_method`, `default_category`, `currency`, the optional limits and agreement, `attributes: dict[str, str] = {}`, and `identifiers: list[PayeeIdentifierCreate] = []`.
- `PayeeUpdate` has the same optional fields plus a required `version: int`.
- `BillDecisionView.can_approve` is computed by the service (`status == BillStatus.REVIEW`), not by a validator.
- Put docstrings only on LLM schema classes: `BillClassification`, the three candidates and `CheckerAssessment`. They act as tool descriptions, as in the existing `InvoiceClpAnalysis` docstring.

## Dependencies

None. Pydantic 2.14 only.

## Integration Notes

- Field names and types must match the tables in `03-design.md` exactly. Repositories map `id` to `<entity>_id`, as existing records do (`run_id`, `email_id`).
- The frontend mirrors these names by hand in `frontend/src/lib/types.ts`. Keep them snake_case.
