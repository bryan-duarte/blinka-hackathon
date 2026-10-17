# API, Container & Migration Implementation

## Overview

This step wires the new modules into the composition root, exposes the HTTP routes, maps the errors and generates the single product migration.

## Files to Modify/Create

- `api/routers/payment_policy.py` (new): `payment_policy_router = APIRouter(tags=["payment-policy"])`, covering the policy, payee and blacklist routes from `03-design.md` § API.
- `api/routers/bills.py` (new): `bills_router = APIRouter(prefix="/bills", tags=["bills"])` with `GET ""`, `GET "/{bill_id}"`, `POST "/{bill_id}/approve"` and `POST "/{bill_id}/reject"`. In the same file, add `budgets_router = APIRouter(prefix="/budgets", tags=["bills"])` with `GET ""` and a `period: str | None = None` query parameter (defaults to the current UTC month). It calls `clients.payments.budget_usage`.
- `api/routers/payments.py`: `trigger_run` changes to the upload body (see 08). `GET /payments/runs/{id}` is unchanged in shape apart from `decision`.
- `api/routers/__init__.py`: include both new routers with `dependencies=[Depends(get_current_user)]`.
- `api/app.py`
  - Register handlers:
    - `PolicyMissingError` → 404
    - `PayeeMissingError` → 404
    - `PayeeVersionConflictError` → 409 "payee was modified, reload and retry"
    - `IdentifierTakenError` → 409
    - `PayeeNameTakenError` → 409
    - `BlacklistEntryMissingError` → 404
    - `BillMissingError` → 404
    - `BillStateConflictError` → 409
    - `BillNotReviewableError` → 409
    - `BillSourceMissingError` → 404
  - Lifespan: call `await clients.payments.recover_unfinished_payments()` right after `payments.fail_unfinished`.
- `container.py`
  - `Clients` gains `payment_policy: PaymentPolicyClient` and `bills: BillsClient`.
  - Build order: auth, files, llm, prompts, guardrails, then `payment_policy` (repository plus service), then `bills`, then `invoice_ingestor` (no repository now), then sessions, then payments (with `LedgerRepository(product)` and the new dependency fields), then orchestrator (gains `bills`), then mail_gateway, then inbox (`InboxDependencies` gains `bills`).
  - Import `PaymentRunDependencies` from the `modules.payments` facade, which fixes the existing inconsistency.
- `alembic/env.py`: in the product branch, import `modules.payment_policy.models` and `modules.bills.models`. Remove the `modules.invoice_ingestor.models` import, since that file is deleted.

## Implementation Guidelines

### Router example (mirror `api/routers/payments.py`)

```python
@bills_router.post("/{bill_id}/approve", response_model=BillDecisionView)
async def approve_bill(bill_id: UUID, request: ReviewActionRequest, user: CurrentUserDep, clients: ClientsDep) -> BillDecisionView:
    return await clients.payments.approve(user, bill_id, request)
```

Policy and payee routes call `clients.payment_policy.*`. `PUT /payment-policy` returns 200 with the new version, and the payee POST returns 201.

### Migration

1. `cd backend && uv run alembic -n product revision --autogenerate -m "add payment policy bills and ledger"`
2. Review the generated file. It must:
   - create `payment_policies`, `payees`, `payee_identifiers`, `blacklist_entries`, `bill_sources`, `bills`, `payment_decisions`, `payments` and `budget_counters`, with FKs, in a valid order;
   - include the partial unique indexes `uq_payment_policies_owner_active`, `uq_bills_owner_fingerprint`, `uq_bills_owner_document` and `uq_agent_runs_active_source`, each with `postgresql_where`;
   - include the named unique constraints `uq_payees_owner_name`, `uq_payee_identifiers_owner_kind_value`, `uq_blacklist_entries_owner_kind_value`, `uq_bill_sources_owner_type_ref`, `uq_payments_bill_id`, `uq_payments_idempotency_key` and `pk_budget_counters`;
   - add `agent_runs.bill_source_id` and `bill_id` with their FKs;
   - drop `invoices`.
3. FK cycle: `bill_sources.bill_id` → `bills` and `bills` has no FK back to sources, so there is no cycle. If autogenerate orders `bill_sources` before `bills`, move the `create_table` calls; reordering is allowed, but hand-writing new content is not.
4. Run `uv run alembic -n product upgrade head`, then `uv run python scripts/seed_payment_policy.py --email <demo user>`.

## Dependencies

Modules 02 through 08.

## Integration Notes

- The frontend (10) consumes exactly these routes. Response models are the contracts from 01.
- `ruff check` and `ruff format --check` must pass (`pnpm lint` in `backend/`).
