# Payment Policy Module Implementation

## Overview

New module `modules/payment_policy`. It owns the versioned rules for each owner, the payee registry (services, people, companies), payee identifiers, the blacklist, and deterministic payee matching. It knows nothing about bills or payments.

## Files to Modify/Create

- `modules/payment_policy/__init__.py` (new). Facade exporting `PaymentPolicyService`, `PaymentPolicyRepository`, the errors, `normalize_name`, `normalize_identifier` and `strong_identifiers`.
- `modules/payment_policy/models.py` (new). `PaymentPolicyRow`, `PayeeRow`, `PayeeIdentifierRow`, `BlacklistEntryRow` on `ProductBase`, with the columns and named constraints from `03-design.md`.
- `modules/payment_policy/normalize.py` (new). Pure helpers.
- `modules/payment_policy/repository.py` (new). `PaymentPolicyRepository`.
- `modules/payment_policy/matching.py` (new). `match_payee(...)`, a pure function over repository lookups.
- `modules/payment_policy/service.py` (new). `PaymentPolicyService`.
- `modules/payment_policy/errors.py` (new).
  - Base: `PaymentPolicyError`.
  - `PolicyMissingError` (404 "payment policy not configured")
  - `PayeeMissingError` (404)
  - `PayeeVersionConflictError` (409)
  - `IdentifierTakenError` (409 "identifier belongs to another payee")
  - `PayeeNameTakenError` (409)
  - `BlacklistEntryMissingError` (404)
- `clients/payment_policy.py` (new). `PaymentPolicyClient`, one method per service operation below.
- `scripts/seed_payment_policy.py` (new). A CLI that takes `--email` and seeds the demo company for that user.

## Implementation Guidelines

### normalize.py

```python
LEGAL_SUFFIX_WORDS = frozenset({"spa", "sa", "ltda", "llc", "inc", "corp", "sas", "eirl", "gmbh", "s", "a"})

def normalize_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    words = re.sub(r"[^a-z0-9]+", " ", folded).split()
    while len(words) > 1 and words[-1] in LEGAL_SUFFIX_WORDS:
        words.pop()
    return " ".join(words)

def normalize_identifier(kind: IdentifierKind, value: str) -> str:
    # EMAIL: strip + lower; DOMAIN: lower, drop "www.", and for a full email keep what follows "@";
    # ALIAS: normalize_name; TAX_ID/BANK_ACCOUNT/SERVICE_ACCOUNT_ID: re.sub(r"[^0-9A-Za-z]", "", value).upper()
    ...

def strong_identifiers(candidate: PaymentCandidateBase, sender: str) -> list[tuple[IdentifierKind, str]]:
    # per 03-design § strong_identifiers; skip None/empty; normalized; deduplicated, order preserved
    ...
```

### Repository

Write methods use one transaction. Use `session.begin()` where two or more statements must be atomic.

- `get_active_policy(owner_id) -> PaymentPolicy | None`
- `activate_policy(owner_id, update: PaymentPolicyUpdate, created_by) -> PaymentPolicy`. One transaction:
  1. `SELECT max(version) ... FOR UPDATE`. Lock the owner's active row with `select(PaymentPolicyRow).where(owner_id, is_active).with_for_update()`.
  2. Set `is_active=False` on that row.
  3. Insert a new row with `version + 1` and `is_active=True`.

  The partial unique `uq_payment_policies_owner_active` is the backstop. On `IntegrityError`, retry once.
- `list_payees(owner_id)`, `get_payee(owner_id, payee_id) -> PayeeRecord | None`
- `create_payee(owner_id, PayeeCreate) -> PayeeRecord`. Inserts the payee and its identifiers in one transaction.
  - An `IntegrityError` on `uq_payees_owner_name` maps to `PayeeNameTakenError`.
  - An `IntegrityError` on `uq_payee_identifiers_owner_kind_value` maps to `IdentifierTakenError`.
  - Inspect `error.orig.diag.constraint_name` (psycopg 3).
- `update_payee(owner_id, payee_id, PayeeUpdate) -> PayeeRecord | None`:
  ```python
  statement = (update(PayeeRow)
      .where(PayeeRow.id == payee_id, PayeeRow.owner_id == owner_id, PayeeRow.version == changes.version)
      .values(**changed_columns, version=PayeeRow.version + 1, updated_at=func.now())
      .returning(PayeeRow))
  ```
  Zero rows means either missing or a version conflict. The service distinguishes the two with a `get_payee` call.
- `add_identifier`, `delete_identifier`, `delete_payee` (identifiers cascade).
- `find_identifier_owners(owner_id, pairs: list[tuple[IdentifierKind, str]]) -> dict[tuple[IdentifierKind, str], UUID]`. One `SELECT ... WHERE (kind, normalized_value) IN (...)`, using `tuple_(...).in_(...)`.
- `find_payees_by_name(owner_id, normalized_name) -> list[PayeeRecord]`. Matches `payees.normalized_name` exactly, or an ALIAS identifier equal to it.
- `list_payee_identifiers(payee_id) -> list[PayeeIdentifierRecord]`
- `find_blacklist_hits(owner_id, pairs) -> list[BlacklistHit]`. Blacklist CRUD: `list_blacklist`, `add_blacklist_entry` (ON CONFLICT DO NOTHING RETURNING, then re-select), `delete_blacklist_entry`.

### matching.py

This is the anti-impersonation core. It stays deterministic.

```python
async def match_payee(repository, owner_id, candidate, sender) -> PayeeMatch:
    strong = strong_identifiers(candidate, sender)
    owners = await repository.find_identifier_owners(owner_id, strong)
    name_candidates = await repository.find_payees_by_name(owner_id, normalize_name(candidate.payee_name or ""))
    owning_payee_ids = list(dict.fromkeys(owners.values()))
    matched_id = owning_payee_ids[0] if len(owning_payee_ids) == 1 else None
    matched_by = next(kind for (kind, _), pid in owners.items() if pid == matched_id) if matched_id else None
    if matched_id is None and not owners and len(name_candidates) == 1:
        matched_id, matched_by = name_candidates[0].payee_id, IdentifierKind.ALIAS
    ...
```

Order of precedence:
1. A strong identifier match wins over a name match.
2. A name-only match is accepted as the matched payee only when no strong identifier on the bill is registered to anyone. Rule R05 then checks whether any unknown strong identifiers are present.
3. If strong identifiers point to two or more payees, `payee=None`, and R05 holds the bill because `identifier_owners` holds several ids.

Sender identifiers are part of `strong` for ownership lookup. A sender that is unknown on its own is not an impersonation signal; R05b treats it as REVIEW. Return the payee's `registered_bank_accounts` and `registered_senders` so `decide()` stays pure.

### Service

- `get_policy(owner) -> PaymentPolicy` raises `PolicyMissingError` when none is active.
- `update_policy(owner, PaymentPolicyUpdate) -> PaymentPolicyView`
- Payee CRUD, identifier CRUD and blacklist CRUD.
- `match_payee(owner_id, candidate, sender) -> PayeeMatch`
- `find_blacklist_hits(owner_id, candidate, sender) -> list[BlacklistHit]`. Checks strong identifiers plus `(ALIAS, normalize_name(payee_name))`.
- `get_payee_record(owner_id, payee_id) -> PayeeRecord | None`. Used by the ledger to read the payee's limits.

### Seed script

Mirror the CLI style of `scripts/create_guardrail.py` (argparse plus `asyncio.run`). The script builds `Settings()`, a product pool and the repository directly. It does not go through `container.py`, because `build_clients` needs every dependency. Demo data, fictitious only:

- **Policy v1:**
  - hard cap 5,000 USD; auto-pay max 1,000 USD; monthly budget 12,000 USD
  - categories: `{cloud: 3000, saas: 1500, contractor: 6000, professional_services: 2500}`
  - allowed categories: cloud, saas, contractor, professional_services, utilities
  - currencies: USD, CLP, CLF, MXN, COP
- **Payees:**
  - `Amazon Web Services`: SERVICE, `card_on_file`, cloud. Identifiers: DOMAIN `aws.amazon.com`, DOMAIN `amazon.com`, SERVICE_ACCOUNT_ID `123456789012`, ALIAS `aws`.
  - `ACME Cloud`: SERVICE, `bank_transfer`, saas. Agreed amount 120 USD, tolerance 5%. DOMAIN `acmecloud.io`, BANK_ACCOUNT `000123456789`.
  - `Servicios Integrales del Sur SpA`: COMPANY, `bank_transfer`, professional_services. TAX_ID `76543210K`, BANK_ACCOUNT `CL-001-2233445566`, EMAIL `facturacion@sisur.cl`.
  - `María José Pérez`: PERSON, `bank_transfer`, contractor. TAX_ID `15234567-8` normalizes to `152345678`. BANK_ACCOUNT `CL-BE-99887766`. Monthly budget 2,500 USD. Agreed 2,000 USD, tolerance 0%.
- **Blacklist:** BANK_ACCOUNT `US-CHASE-55554444` ("cuenta reportada"), DOMAIN `amaz0n-billing.com`, ALIAS `proveedor fantasma`.

The values must line up with the simulated trap emails in `08-sources-wiring`.

## Dependencies

`contracts/payment_policy.py`, `contracts/payment_candidates.py`, `core/db/base.py::ProductBase`, `core/logging_config.get_logger`.

## Integration Notes

- The `payments` runner calls `PaymentPolicyClient.get_policy`, `.match_payee`, `.find_blacklist_hits` and `.get_payee_record`.
- The ledger repository needs limits inside its own transaction. It receives `PaymentPolicy` and `PayeeRecord` values from the runner. It does not import this module.
