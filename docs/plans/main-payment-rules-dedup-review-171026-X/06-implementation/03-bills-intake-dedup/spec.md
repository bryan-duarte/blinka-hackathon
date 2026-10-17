# Bills Intake & Dedup Implementation

## Overview

New module `modules/bills`. It records every delivery as a bill source and stores each canonical bill exactly once. It enforces the three exact-duplicate layers (source, document, fingerprint) with database constraints, and owns compare-and-set transitions of `bills.status`.

## Files to Modify/Create

- `modules/bills/__init__.py` (new). Facade: `BillsService`, `BillsRepository`, errors, `bill_fingerprint`, `sha256_hex`.
- `modules/bills/models.py` (new). `BillSourceRow` and `BillRow`, with the constraints and partial indexes from `03-design.md`.
- `modules/bills/hashing.py` (new). `sha256_hex(*parts: bytes) -> str` and `bill_fingerprint(owner_id, payee_id, payee_name, invoice_number, due_date, amount, currency) -> str | None`. It returns `None` when `amount` or `payee_name` is missing, so no fingerprint uniqueness applies and the bill can't collide on empty data.
- `modules/bills/repository.py` (new). `BillsRepository`.
- `modules/bills/service.py` (new). `BillsService`.
- `modules/bills/errors.py` (new).
  - Base: `BillsError`.
  - `BillMissingError` (404 "bill not found")
  - `BillStateConflictError` (409 "bill is not in the expected state")
  - `BillSourceMissingError` (404)
- `clients/bills.py` (new). `BillsClient`.

## Implementation Guidelines

### register_source (layer 1: same delivery)

```python
async def register_source(self, intake: BillSourceIntake, content_sha256: str) -> SourceRegistration:
    statement = (insert(BillSourceRow)
        .values(owner_id=intake.owner_id, source_type=intake.source_type, source_ref=intake.source_ref, ...,
                content_sha256=content_sha256)
        .on_conflict_do_nothing(constraint="uq_bill_sources_owner_type_ref")
        .returning(BillSourceRow))
    async with self._sessionmaker() as session:
        inserted = (await session.execute(statement)).scalar_one_or_none()
        if inserted is None:
            existing = (await session.execute(select(BillSourceRow).where(
                BillSourceRow.owner_id == intake.owner_id,
                BillSourceRow.source_type == intake.source_type,
                BillSourceRow.source_ref == intake.source_ref))).scalar_one()
        await session.commit()
    ...
```

`BillsService.register_source(intake)` computes `content_sha256 = sha256_hex(intake.body_text.encode(), attachment_bytes_hash)`. It uses `intake.attachment_sha256` when there's an attachment; the caller hashes the attachment bytes it already holds. The service logs `bill_source_duplicate` when `is_new=False`.

### claim_bill (layers 2 and 3: same document, same bill)

This is a single transaction that creates the bill as canonical when it can, and as a duplicate when uniqueness forbids it. It is concurrency-safe because both partial unique indexes decide the race.

```python
async def claim_bill(self, source_id, owner_id, fields: BillFields) -> BillClaim:
    async with self._sessionmaker() as session, session.begin():
        canonical_insert = (insert(BillRow).values(**fields.columns(), status=BillStatus.DECIDING)
            .on_conflict_do_nothing()          # any unique violation, incl. both partial indexes
            .returning(BillRow))
        bill = (await session.execute(canonical_insert)).scalar_one_or_none()
        original = None
        if bill is None:
            original = await self._find_canonical(session, owner_id, fields.document_sha256, fields.fingerprint)
            bill = (await session.execute(insert(BillRow).values(
                **fields.columns(), status=BillStatus.DUPLICATE, duplicate_of_bill_id=original.id
            ).returning(BillRow))).scalar_one()
        await session.execute(update(BillSourceRow).where(BillSourceRow.id == source_id).values(bill_id=bill.id))
    return BillClaim(bill=_to_bill_record(bill), duplicate_of=_to_bill_record(original) if original else None)
```

- `on_conflict_do_nothing()` without a target covers both partial unique indexes. Postgres can't name a partial index as an ON CONFLICT target without its predicate, so the untargeted form is the simplest correct option. Then `_find_canonical` selects `WHERE owner_id=:o AND duplicate_of_bill_id IS NULL AND (document_sha256=:d OR fingerprint=:f) ORDER BY created_at LIMIT 1`.
- **Race:** if the winner's transaction hasn't committed yet, our INSERT waits on the index entry, then conflicts. When we SELECT afterwards, the winner is visible under READ COMMITTED.
- If `_find_canonical` returns nothing after a conflict, the competing transaction rolled back. Retry the whole `claim_bill` once (`CLAIM_ATTEMPTS = 2`). If it still finds nothing, raise `BillStateConflictError`; the runner's fail-closed handler then records REVIEW.
- A duplicate row never has a fingerprint or document_sha256 under a uniqueness constraint, because the predicate excludes `duplicate_of_bill_id IS NOT NULL`. So any number of duplicates can point at one original.
- `BillFields` (a frozen dataclass in `service.py`) carries kind, payee_id, payee_name, invoice_number (normalized), amount, currency, amount_usd, category, due_date, candidate (a dict dump), document_sha256 and fingerprint.

`document_sha256` is `source.attachment_sha256` when there's an attachment. Otherwise it's `source.content_sha256`, but only for UPLOAD and CHAT sources. For email it is `None` when there's no attachment, so two different short emails with near-identical text don't collide. The fingerprint covers those emails instead.

### Compare-and-set status

```python
async def transition(self, owner_id, bill_id, expected: BillStatus | tuple[BillStatus, ...], target: BillStatus) -> BillRecord | None:
    expected_statuses = expected if isinstance(expected, tuple) else (expected,)
    statement = (update(BillRow)
        .where(BillRow.id == bill_id, BillRow.owner_id == owner_id, BillRow.status.in_(expected_statuses))
        .values(status=target, version=BillRow.version + 1, updated_at=func.now())
        .returning(BillRow))
```

When this returns `None`, the service raises `BillStateConflictError`.

These transitions are the only allowed ones:

| from | to | by |
|---|---|---|
| deciding | paid / held / review | runner |
| review | approving | approve |
| review | rejected | reject |
| approving | paid / held | approve |
| deciding | review | restart sweep |
| approving | review | restart sweep |

Encode them as `ALLOWED_TRANSITIONS: dict[BillStatus, frozenset[BillStatus]]` in `service.py` and validate the requested transition before calling the repository.

### Other repository methods

- `get_bill(owner_id, bill_id)`
- `list_bills(owner_id, status: BillStatus | None, limit=BILL_LIST_LIMIT)`
- `get_source(source_id)`
- `list_sources_for_bill(bill_id)`
- `recent_canonical_bills(owner_id, payee_id, since: datetime, exclude_bill_id) -> list[BillSummary]`. Uses `ix_bills_owner_payee_created`. Used by R11 and the CHK3 history.
- `stuck_bills(statuses) -> list[BillRecord]`. Used by the restart sweep.

## Dependencies

`contracts/bills.py`, `contracts/payment_candidates.py`, `contracts/payment_policy.py` (PayeeKind), `core/db/base.py`.

## Integration Notes

- Callers: inbox pipeline, orchestrator tool and payments router call `register_source`. The payments runner calls `get_source`, `claim_bill`, `transition` and `recent_canonical_bills`.
- `bill_sources.inbox_email_id` points to `inbox_emails`. This module must not import inbox; the FK lives only in `models.py` via `ForeignKey("inbox_emails.id")`. That is fine, since both tables are on `ProductBase`.
