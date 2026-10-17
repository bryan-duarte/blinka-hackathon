# Technical Design

All paths are relative to `backend/` unless prefixed with `frontend/`.

## Architecture Decisions

1. **Money decisions are code.** `modules/payments/rules.py::decide()` is a pure function. It does no I/O, uses no clock (`today` is a parameter) and calls no LLM. It evaluates every rule with no short-circuit. Verdict precedence: any HOLD gives `hold`; otherwise any REVIEW gives `review`; otherwise `pay`.
2. **LLMs are typed workers.** There are three LLM calls, all through `LlmGatewayClient.extract(...)`:
   - classify: `BillClassification`
   - extract: the candidate schema for the classified kind
   - check: `CheckerAssessment`

   No agent loop and no tools run in the payments path. `create_deep_agent` stays only in `orchestrator`.
3. **The checker can only tighten.** `apply_checker(evaluation, assessment, policy)` may append REVIEW rule results. It never removes a result or lowers the verdict.
4. **Exactly-once payment comes from database constraints, not from application checks:**
   - `payments.bill_id` is UNIQUE.
   - `payments.idempotency_key` is UNIQUE (`"bill:<bill_id>"`).
   - State changes are compare-and-set (`UPDATE ... WHERE status = :expected RETURNING`).
   - Reserving budget and inserting the payment happen in one transaction.
5. **Dedup is layered:**
   - **Source.** `bill_sources` UNIQUE(owner_id, source_type, source_ref). A repeat stops at intake.
   - **Document.** `bills` partial UNIQUE(owner_id, document_sha256) WHERE canonical.
   - **Bill.** `bills` partial UNIQUE(owner_id, fingerprint) WHERE canonical.
   - **Fuzzy.** Rule R11 gives REVIEW.
6. **Concurrency model:**
   - Postgres READ COMMITTED (the current default) is kept.
   - Correctness comes from unique constraints, `INSERT ... ON CONFLICT DO NOTHING RETURNING`, and conditional `UPDATE ... WHERE <invariant> RETURNING`. Postgres re-checks the WHERE clause against the latest row version after waiting on a row lock (EvalPlanQual).
   - Budget scopes are locked in sorted order to avoid deadlocks.
   - Payee edits use optimistic concurrency (`payees.version`).
7. **Each transaction that spans statements is one repository method.** Such methods use `async with self._sessionmaker() as session, session.begin():`. Today every method commits individually; the ledger and dedup methods are the exception, by design.
8. **Fail-closed.** Once a bill row exists, every exception in the run except `CancelledError` records a REVIEW decision (`reason_code="error_tecnico"`). On restart, the sweep moves bills stuck in `deciding` to review, and re-executes payments stuck in `reserved`. Re-execution is idempotent.
9. **New modules follow the existing seam rule.** Modules reach each other only through `clients/<name>.py`. `container.py` is the only composition root. Contracts live in `contracts/`.

## Patterns & Conventions

Mirror these exact files:

- **Module layout.** `modules/payments/{__init__,errors,models,repository,service}.py`. The `__init__.py` facade has an alphabetized `__all__`; mirror `modules/payments/__init__.py`.
- **Client.** Mirror `clients/payments.py`: service imported under `TYPE_CHECKING`, a string annotation, one async pass-through method per operation.
- **Repository.** Mirror `modules/payments/repository.py`: an `async_sessionmaker` is injected, there is one session per method, and rows map to `StrictModel` records through module-level `_to_<x>_record()`.
  - ON CONFLICT: mirror `modules/inbox/repository.py::insert_email` (`from sqlalchemy.dialects.postgresql import insert`).
  - Upsert: mirror `modules/invoice_ingestor/repository.py::upsert`.
- **Errors.** A bare `<Module>Error(Exception)` base with `pass` subclasses, raised bare or with an UPPER constant message. Map HTTP errors in `api/app.py` with `app.add_exception_handler(...)` and `_reject_<snake>` handlers that return `{"detail": "..."}`. Use 404 for missing, 409 for conflict and invalid state, 422 for validation.
- **Background run.** Mirror `modules/payments/runner.py::run_execution`: catch `CancelledError` and re-raise, `logger.exception(...)` on `Exception`, and step constants in UPPER_CASE.
- **Contracts.** Records use `StrictModel`. HTTP bodies and every LLM-produced schema use `ApiModel`, because strict mode rejects string enums coming through structured output. Enums are `StrEnum` with UPPER members and lowercase values.
- **Comments.** No `#` comments except `# TEMPORAL: <what>; <how to replace>.` Docstrings appear only on LLM schema classes and as tool descriptions.
- **Logging.** Event names are `<domain>_<subject>_<past>`, e.g. `bill_duplicate_detected`, `payment_reserved`, `payment_executed`, `budget_exhausted`, `bill_review_approved`.
- **Migrations.** Always `alembic -n product revision --autogenerate -m "<lowercase imperative>"`. Never hand-write them. Every new `models.py` must be imported in `alembic/env.py` (product section). Partial unique indexes must be declared on the model as `Index(name, *cols, unique=True, postgresql_where=...)` so autogenerate emits them. Give every composite constraint or index an explicit `name=`, because the naming convention only uses the first column.

## Dependencies

No new Python packages:
- Normalization uses `unicodedata` and `re`.
- Hashing uses `hashlib`.
- UUIDv5 comes from `uuid`.

Existing pins: `sqlalchemy 2.1.5`, `psycopg 3.3.6`, `pydantic 2.14.1`, `fastapi 0.143.3`, `alembic 1.20.0`, `langchain-anthropic 1.7.6`.

Frontend: no new packages. Use the existing Next 16, React 19 and Tailwind 4 stack and `frontend/src/lib/api.ts`.

## Integration Points

| Touchpoint | Change |
|---|---|
| `modules/inbox/pipeline.py::_analyze` | Store the attachment PDF (if any) as a file. Call `bills.register_source(BillSourceIntake(type=EMAIL, source_ref=f"{provider}:{external_message_id}", ...))` with `body_text=f"{subject}\n\n{body}"`. If `is_new=False`, mark the email `DUPLICATE` and stop. Otherwise call `payments.start_run(PaymentRunTrigger(bill_source_id=...))`. |
| `modules/inbox/service.py::simulate` | Keep `source_ref=f"simulated:sim-{uuid4()}"`. Identical simulated content is still caught by the document hash and fingerprint layers. |
| `modules/inbox/service.py::_resolve_status` | Map the run's `decision.verdict` to `PAID`, `HELD` or `REVIEW`. A non-bill run maps to `NO_INVOICE`. |
| `modules/orchestrator/tools.py::initiate_payments` | Register a source with `type=CHAT`, `source_ref=f"{session_id}:{file_id}"`, then `start_run`. Return `{run_id, status, duplicate: bool}`. |
| `api/routers/payments.py::trigger_run` | Register a source with `type=UPLOAD`, `source_ref=f"upload:{file_id}"`, then `start_run`. |
| `modules/payments/runner.py` | Rewritten: classify → extract → match → claim → decide → check → reserve → execute → record. |
| `modules/invoice_ingestor/service.py` | `parse()` is replaced by `classify(owner, document)` and `extract_candidate(owner, document, kind)`. The `invoices` table and `InvoiceData` are removed. |
| `modules/llm_gateway/service.py::extract` | Unchanged. Used with `model_kind="main"` for extraction and `"payments"` for the checker. |
| `modules/prompts/registry.py::PROMPTS` | Add `BILL_CLASSIFICATION`, `SERVICE_EXTRACTION`, `PERSON_EXTRACTION`, `COMPANY_EXTRACTION` and `PAYMENT_CHECKER`. Remove `INVOICE_EXTRACTION` and `PAYMENT_AGENT`. `PromptsService` refuses to start if any `PromptId` has no prompt registered. |
| `api/app.py` lifespan | After `payments.fail_unfinished`, call `payments.recover_unfinished_payments()`. Register the new error handlers. |
| `container.py::build_clients` | Build `PaymentPolicyService` and `BillsService` before `PaymentsService`. Inject their clients. |
| `frontend/src/components/inbox/EmailDetail.tsx::ResultCard` | Add branches for `paid`, `held`, `review` and `duplicate` that render `DecisionCard`. |

## Data Structures

### Enums (`contracts/payment_policy.py`, `contracts/bills.py`, `contracts/payments.py`)

```python
class PayeeKind(StrEnum): SERVICE = "service"; PERSON = "person"; COMPANY = "company"
class PayeeStatus(StrEnum): ALLOWED = "allowed"; BLACKLISTED = "blacklisted"
class PaymentMethod(StrEnum): BANK_TRANSFER = "bank_transfer"; CARD_ON_FILE = "card_on_file"; PLATFORM_DEBIT = "platform_debit"
class PaymentCategory(StrEnum):
    CLOUD = "cloud"; SAAS = "saas"; CONTRACTOR = "contractor"; PROFESSIONAL_SERVICES = "professional_services"
    UTILITIES = "utilities"; RENT = "rent"; MARKETING = "marketing"; OTHER = "other"
class IdentifierKind(StrEnum):
    TAX_ID = "tax_id"; BANK_ACCOUNT = "bank_account"; SERVICE_ACCOUNT_ID = "service_account_id"
    EMAIL = "email"; DOMAIN = "domain"; ALIAS = "alias"
class BillSourceType(StrEnum): EMAIL = "email"; CHAT = "chat"; UPLOAD = "upload"; TELEGRAM = "telegram"
class BillStatus(StrEnum):
    DECIDING = "deciding"; PAID = "paid"; HELD = "held"; REVIEW = "review"
    APPROVING = "approving"; REJECTED = "rejected"; DUPLICATE = "duplicate"
class Verdict(StrEnum): PAY = "pay"; HOLD = "hold"; REVIEW = "review"
class RuleEffect(StrEnum): PASS = "pass"; HOLD = "hold"; REVIEW = "review"
class DecisionActor(StrEnum): AGENT = "agent"; HUMAN = "human"
class LedgerStatus(StrEnum): RESERVED = "reserved"; EXECUTED = "executed"
```

### Tables (all on `ProductBase`, product DB)

**`payment_policies`** (`modules/payment_policy/models.py::PaymentPolicyRecord`)
| column | type | notes |
|---|---|---|
| id | Uuid PK | uuid4 |
| owner_id | Uuid FK users.id | indexed |
| version | Integer | `UniqueConstraint("owner_id","version", name="uq_payment_policies_owner_version")` |
| is_active | Boolean | `Index("uq_payment_policies_owner_active", "owner_id", unique=True, postgresql_where=is_active)` |
| hard_cap_per_payment_usd | Numeric(18,2) | |
| auto_pay_max_usd | Numeric(18,2) | must be ≤ hard cap (validated in service) |
| monthly_budget_usd | Numeric(18,2) | |
| category_monthly_budgets_usd | JSONB | `{category: "1500.00"}`; a missing category has no category cap |
| allowed_categories | JSONB | list[str] ("Services allowed") |
| allowed_currencies | JSONB | list[str] ISO 4217 |
| duplicate_window_days | Integer | default 45 |
| min_field_confidence | Numeric(3,2) | default 0.80 |
| min_category_confidence | Numeric(3,2) | default 0.70 |
| checker_review_low / checker_review_high | Numeric(3,2) | default 0.20 / 0.80 |
| created_by | Uuid FK users.id | |
| created_at | DateTime | server_default now() |

**`payees`** (`PayeeRecord`)
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK users.id | indexed |
| kind | String | PayeeKind |
| display_name | String | |
| normalized_name | String | `UniqueConstraint("owner_id","normalized_name", name="uq_payees_owner_name")` |
| status | String | PayeeStatus |
| payment_method | String | PaymentMethod |
| default_category | String NULL | PaymentCategory |
| currency | String | registered billing currency (informational; never used to infer) |
| per_payment_max_usd | Numeric(18,2) NULL | overrides the hard cap downward only |
| monthly_budget_usd | Numeric(18,2) NULL | counter scope `payee:<id>` |
| agreed_amount_usd | Numeric(18,2) NULL | R17 |
| agreed_tolerance_pct | Numeric(5,2) NULL | default 0 when agreed_amount set |
| attributes | JSONB | per-kind extras (see contracts) |
| version | Integer | optimistic lock, starts at 1 |
| created_at / updated_at | DateTime | |

**`payee_identifiers`**
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK users.id | |
| payee_id | Uuid FK payees.id ON DELETE CASCADE | indexed |
| kind | String | IdentifierKind |
| normalized_value | String | `UniqueConstraint("owner_id","kind","normalized_value", name="uq_payee_identifiers_owner_kind_value")`. One identifier belongs to one payee. |
| raw_value | String | as typed |

**`blacklist_entries`**
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK | |
| kind | String | IdentifierKind (ALIAS means a normalized name) |
| normalized_value | String | `UniqueConstraint("owner_id","kind","normalized_value", name="uq_blacklist_entries_owner_kind_value")` |
| reason | String | |
| created_at | DateTime | |

**`bill_sources`** (`modules/bills/models.py`)
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK | indexed |
| source_type | String | BillSourceType |
| source_ref | String | `UniqueConstraint("owner_id","source_type","source_ref", name="uq_bill_sources_owner_type_ref")` |
| sender | String | email address / chat user email / telegram handle |
| body_text | Text | subject plus body for email; empty for chat/upload |
| file_id | Uuid FK files.id NULL | the PDF or image attachment |
| content_sha256 | String(64) | sha256 of `body_text` bytes + attachment bytes |
| attachment_sha256 | String(64) NULL | sha256 of the attachment bytes only |
| inbox_email_id | Uuid FK inbox_emails.id NULL | |
| bill_id | Uuid FK bills.id NULL | set by `claim_bill` |
| received_at | DateTime(timezone=True) NULL | |
| created_at | DateTime | |

**`bills`**
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK | indexed |
| kind | String | PayeeKind |
| payee_id | Uuid FK payees.id NULL | |
| payee_name | String | extracted |
| invoice_number | String NULL | normalized |
| amount | Numeric(18,4) NULL | original |
| currency | String(3) NULL | never inferred |
| amount_usd | Numeric(18,2) NULL | |
| category | String NULL | LLM-inferred |
| due_date | Date NULL | |
| candidate | JSONB | full `PaymentCandidate` dump |
| document_sha256 | String(64) NULL | attachment hash, else content hash |
| fingerprint | String(64) NULL | see below |
| duplicate_of_bill_id | Uuid FK bills.id NULL | |
| status | String | BillStatus, indexed |
| version | Integer | default 1 |
| created_at / updated_at | DateTime | |

Indexes:
- `Index("uq_bills_owner_fingerprint", "owner_id", "fingerprint", unique=True, postgresql_where=and_(duplicate_of_bill_id.is_(None), fingerprint.is_not(None)))`
- `Index("uq_bills_owner_document", "owner_id", "document_sha256", unique=True, postgresql_where=and_(duplicate_of_bill_id.is_(None), document_sha256.is_not(None)))`
- `Index("ix_bills_owner_payee_created", "owner_id", "payee_id", "created_at")` for the R11 fuzzy lookup.

**`payment_decisions`** (append-only, `modules/payments/models.py`)
| column | type |
|---|---|
| id | Uuid PK |
| bill_id | Uuid FK bills.id, indexed |
| run_id | Uuid FK agent_runs.id NULL |
| actor | String (DecisionActor) |
| actor_user_id | Uuid FK users.id NULL |
| verdict | String (Verdict) |
| rule_results | JSONB (list[RuleResult]) |
| checker | JSONB NULL (CheckerAssessment) |
| explanation | Text (Spanish, template) |
| policy_id | Uuid FK payment_policies.id NULL |
| policy_version | Integer NULL |
| note | Text NULL (human note) |
| created_at | DateTime |

**`payments`** (the ledger)
| column | type | notes |
|---|---|---|
| id | Uuid PK | |
| owner_id | Uuid FK | |
| bill_id | Uuid FK bills.id | `UniqueConstraint("bill_id", name="uq_payments_bill_id")` |
| idempotency_key | String | `UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key")`, value `f"bill:{bill_id}"` |
| payee_id | Uuid FK payees.id | |
| amount | Numeric(18,4) | |
| currency | String(3) | |
| amount_usd | Numeric(18,2) | |
| category | String | |
| period | String(7) | `"YYYY-MM"` UTC |
| scopes | JSONB | list of counter scopes charged (for release) |
| status | String | LedgerStatus |
| rail_reference | String NULL | `str(uuid5(PAYMENTS_NAMESPACE, idempotency_key))` |
| executed_at | DateTime NULL | |
| created_at / updated_at | DateTime | |

**`budget_counters`**
| column | type | notes |
|---|---|---|
| owner_id | Uuid FK | composite PK part |
| scope | String | `"global"`, `"category:<cat>"`, `"payee:<uuid>"` |
| period | String(7) | |
| reserved_usd | Numeric(18,2) | default 0 |
| updated_at | DateTime | |

PK is `PrimaryKeyConstraint("owner_id","scope","period", name="pk_budget_counters")`. Limits are not stored here. The caller computes `BudgetCharge(scope, limit_usd)` from the policy and payee it loaded just before reserving, and `reserve()` enforces them atomically. The decision records `policy_version`.

**`agent_runs`** (existing) gains:
- `bill_source_id Uuid FK bill_sources.id NULL`
- `bill_id Uuid FK bills.id NULL`
- `Index("uq_agent_runs_active_source", "bill_source_id", unique=True, postgresql_where=status.in_(["pending","running"]))`

**`invoices`**: dropped, together with `InvoiceRecord` and `InvoicesRepository`.

**`inbox_emails`**: no schema change. New status values are plain strings.

### Fingerprint

```
payee_key   = str(payee_id) if payee_id else normalize_name(payee_name)
number_part = normalize_identifier(invoice_number) if invoice_number else f"due:{due_date or ''}"
fingerprint = sha256(f"{owner_id}|{payee_key}|{number_part}|{amount:.2f}|{currency or ''}")
```

When there's no invoice number (common for a person's "cuenta de cobro"), the due date stands in. A resend with a new amount gets a new fingerprint, and R11 catches it.

### Contracts: payment candidates (`contracts/payment_candidates.py`, all `ApiModel`)

```python
class FieldEvidence(ApiModel):
    field: str
    quote: str          # exact text from body or PDF
    confidence: float   # 0..1

class PaymentCandidateBase(ApiModel):
    kind: PayeeKind
    payee_name: str | None
    amount: Decimal | None
    currency: str | None          # ISO 4217 only when explicit; "$" alone -> None
    issue_date: date | None
    due_date: date | None
    invoice_number: str | None
    description: str | None
    bank_account: str | None
    payee_email: str | None
    category: PaymentCategory | None
    category_confidence: float
    embedded_instructions: list[str] = []   # text addressed to an AI/agent
    evidence: list[FieldEvidence] = []

class ServiceCandidate(PaymentCandidateBase):
    kind: Literal[PayeeKind.SERVICE] = PayeeKind.SERVICE
    provider_domain: str | None
    service_account_id: str | None     # e.g. AWS account id
    billing_period_start: date | None
    billing_period_end: date | None

class PersonCandidate(PaymentCandidateBase):
    kind: Literal[PayeeKind.PERSON] = PayeeKind.PERSON
    national_id: str | None            # RUT / cédula / SSN-last4
    concept: str | None                # honorarios, reembolso...

class CompanyCandidate(PaymentCandidateBase):
    kind: Literal[PayeeKind.COMPANY] = PayeeKind.COMPANY
    legal_name: str | None
    tax_id: str | None                 # RUT / EIN / NIT
    country: str | None                # ISO 3166-1 alpha-2
    purchase_order: str | None

PaymentCandidate = Annotated[ServiceCandidate | PersonCandidate | CompanyCandidate, Field(discriminator="kind")]

class BillClassification(ApiModel):
    """Step 1: call once. Decide if the document is a bill to pay and who gets paid."""
    is_bill: bool
    kind: PayeeKind | None
    reason: str
    confidence: float
```

`strong_identifiers(candidate) -> list[tuple[IdentifierKind, str]]` (in `modules/payment_policy/normalize.py`):
- base: `bank_account`, `payee_email` (EMAIL) and the sender (EMAIL, DOMAIN)
- service: `service_account_id`, `provider_domain`
- person: `national_id` (TAX_ID)
- company: `tax_id`

### Contracts: decisions (`contracts/payments.py`)

```python
class RuleResult(ApiModel):
    rule_id: str              # "R01".."R17", "CHK1".."CHK3", "DUP"
    name: str
    effect: RuleEffect
    reason: str               # Spanish, with figures
    evidence: dict[str, str] = {}

class CheckerAnswer(ApiModel):
    question_id: Literal["CHK1", "CHK2", "CHK3"]
    probability: float
    rationale: str

class CheckerAssessment(ApiModel):
    """Final step: answer each question once with a probability in [0,1]."""
    answers: list[CheckerAnswer]

class BillDecisionView(ApiModel):
    bill_id: UUID
    verdict: Verdict
    status: BillStatus
    explanation: str
    rule_results: list[RuleResult]
    checker: CheckerAssessment | None
    candidate: PaymentCandidate | None
    payee_id: UUID | None
    payee_name: str | None
    amount: Decimal | None
    currency: str | None
    amount_usd: Decimal | None
    category: PaymentCategory | None
    duplicate_of_bill_id: UUID | None
    actor: DecisionActor
    decided_at: datetime
    can_approve: bool         # status == REVIEW

class PaymentRunTrigger(ApiModel):
    bill_source_id: UUID
    session_id: UUID | None = None

class PaymentRunStatus(ApiModel):   # replaces analysis with decision
    run_id: UUID
    status: RunStatus
    error: str | None
    events: list[PaymentRunEvent] = []
    decision: BillDecisionView | None = None
    is_bill: bool | None = None

class ReviewActionRequest(ApiModel):
    note: str = Field(min_length=3, max_length=500)
```

`InvoiceClpAnalysis`, `ClpConversion`, `InvoiceData`, `InvoiceLineItem` and `InvoiceParseResult` are deleted.

### Rules catalog (`modules/payments/rules.py`)

| id | name | effect when failing | fails when |
|---|---|---|---|
| R01 | datos_completos | REVIEW | `payee_name`, `amount > 0`, `currency` or `due_date` missing, or any of their evidence confidences below `min_field_confidence` |
| R02 | sin_instrucciones | HOLD | `embedded_instructions` is non-empty |
| R03 | no_bloqueado | HOLD | any strong identifier or normalized name is in `blacklist_entries`, or the matched payee has `status=BLACKLISTED` |
| R04 | beneficiario_registrado | REVIEW | no payee matched; reason lists name-only candidates |
| R05 | identidad_consistente | HOLD | see impersonation conditions in 02-preferences |
| R05b | remitente_conocido | REVIEW | email source, the payee has EMAIL/DOMAIN identifiers, and the sender matches none of them |
| R06 | tipo_coincide | REVIEW | `candidate.kind != payee.kind` |
| R07 | categoria_permitida | REVIEW | `category not in policy.allowed_categories` |
| R08 | categoria_confiable | REVIEW | `category_confidence < min_category_confidence`, or the payee's `default_category` differs from it |
| R09 | moneda_permitida | REVIEW | currency not in `allowed_currencies`, or no FX rate |
| R11 | sin_duplicado_probable | REVIEW | a canonical bill from the same payee with `abs(amount_usd - x) <= 0.5%` inside `duplicate_window_days`, and an invoice number that is missing or different |
| R12 | tope_por_pago | HOLD | `amount_usd > min(hard_cap, payee.per_payment_max_usd)` |
| R13 | tope_autopago | REVIEW | `amount_usd > auto_pay_max_usd` |
| R14 | presupuesto_disponible | HOLD | the projected spend would exceed the global, category or payee limit, using a counter snapshot (reservation re-checks atomically) |
| R17 | coincide_con_acuerdo | REVIEW | `payee.agreed_amount_usd` is set and `abs(amount_usd - agreed) > agreed * tolerance_pct / 100` |
| DUP | duplicado_exacto | HOLD | set by `claim_bill` when there's a conflict; `decide()` is not called |
| CHK1 | servicio_coincide | REVIEW | p(description matches the payee's registered service or category) is inside the band or below `low` |
| CHK2 | suplantacion | REVIEW | p(document impersonates the payee) is inside the band or above `low` |
| CHK3 | monto_habitual | REVIEW | p(amount consistent with the payee's last 6 bills) is inside the band or below `low` |

R10 is intentionally unused, since exact dup is DUP. Rules R12–R17 are skipped (effect PASS, reason "no aplica: sin monto en USD") when `amount_usd is None`; R01 or R09 already force REVIEW in that case.

```python
@dataclass(frozen=True)
class DecisionContext:
    candidate: PaymentCandidate
    source: BillSourceRecord
    match: PayeeMatch
    policy: PaymentPolicy
    blacklist_hits: list[BlacklistHit]
    amount_usd: Decimal | None
    recent_bills: list[BillSummary]
    budget: BudgetSnapshot
    today: date
    waived_effects: frozenset[RuleEffect] = frozenset()   # {REVIEW} on human approval

@dataclass(frozen=True)
class RuleEvaluation:
    verdict: Verdict
    results: list[RuleResult]
```

### FX (`modules/payments/fx.py`)

```python
# TEMPORAL: dummy USD rates for the demo; replace with a dated FX source.
DUMMY_USD_PER_UNIT = {"USD": Decimal("1"), "CLP": Decimal("0.00105"), "CLF": Decimal("41.50"),
                      "EUR": Decimal("1.08"), "MXN": Decimal("0.055"), "COP": Decimal("0.00025"),
                      "BRL": Decimal("0.18")}
def to_usd(amount: Decimal, currency: str) -> Decimal | None  # quantize(Decimal("0.01"), ROUND_HALF_UP)
```

### API (new and changed)

| method | path | body / response |
|---|---|---|
| GET | `/payment-policy` | `PaymentPolicyView` |
| PUT | `/payment-policy` | `PaymentPolicyUpdate` → `PaymentPolicyView` (new version, atomic deactivate-and-insert) |
| GET | `/payees` | `list[PayeeView]` |
| POST | `/payees` | `PayeeCreate` → `PayeeView` (201) |
| GET | `/payees/{id}` | `PayeeView` |
| PATCH | `/payees/{id}` | `PayeeUpdate{version, ...}` → `PayeeView`; 409 on version mismatch |
| DELETE | `/payees/{id}` | 204 |
| POST | `/payees/{id}/identifiers` | `PayeeIdentifierCreate` → `PayeeView`; 409 if the identifier belongs to another payee |
| DELETE | `/payees/{id}/identifiers/{identifier_id}` | 204 |
| GET / POST | `/blacklist` | `list[BlacklistEntryView]` / `BlacklistEntryCreate` |
| DELETE | `/blacklist/{id}` | 204 |
| GET | `/bills?status=review` | `list[BillDecisionView]` (latest decision per bill) |
| GET | `/bills/{id}` | `BillDetail{decision: BillDecisionView, history: list[BillDecisionView], sources: list[BillSourceView], payment: PaymentView \| None}` |
| POST | `/bills/{id}/approve` | `ReviewActionRequest` → `BillDecisionView`; 409 if not in review |
| POST | `/bills/{id}/reject` | `ReviewActionRequest` → `BillDecisionView`; 409 if not in review |
| GET | `/budgets?period=2026-10` | `list[BudgetUsageView{scope, limit_usd, reserved_usd}]` |
| POST | `/payments/runs` | body becomes `{file_id}`, registers an UPLOAD source, returns `PaymentRunAccepted{run_id, status, duplicate}` |

The bill routes live in `api/routers/bills.py`, routed to `PaymentsClient`. The policy, payee and blacklist routes live in `api/routers/payment_policy.py`.

### Inbox status additions (`contracts/inbox.py`)

Add `PAID = "paid"`, `HELD = "held"`, `REVIEW = "review"` and `DUPLICATE = "duplicate"`. Remove `ANALYZED`. `InboxEmailView.analysis` is replaced by `decision: BillDecisionView | None`.
