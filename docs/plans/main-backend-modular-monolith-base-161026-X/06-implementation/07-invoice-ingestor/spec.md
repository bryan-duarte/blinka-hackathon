# Invoice Ingestor

## Overview

Parses invoice files (any uploaded format) into a validated `InvoiceData` via LLM extraction; caches the result in the `invoices` table. Future entry point for the email-triggered flow.

## Files to Create

- `backend/modules/invoice_ingestor/__init__.py` — facade: `InvoiceIngestorService`, `InvoiceParseError`
- `backend/modules/invoice_ingestor/errors.py` — `InvoiceParseError(InvoiceParseError detail message)` (parse failure with reason)
- `backend/modules/invoice_ingestor/service.py`:

```python
class InvoiceIngestorService:
    def __init__(self, files: FilesClient, llm: LlmGatewayClient, repo: InvoicesRepository) -> None: ...

    async def parse(self, owner: CurrentUser, file_id: UUID) -> InvoiceParseResult:
        # 1. cached? -> return stored InvoiceData
        # 2. files.read_bytes(owner, file_id) -> row + bytes
        # 3. build multimodal/text message: PDF bytes if mime is pdf (multimodal input),
        #    else extracted preview text
        # 4. llm.extract(model_kind="main", system=INVOICE_EXTRACTION_PROMPT, payload=...)
        #    -> structured output validated as InvoiceData (pydantic; retry once on ValidationError)
        # 5. upsert invoices(file_id, data) ; files.set_parse_status(parsed)
        # failure -> InvoiceParseError (caller decides severity)
```

- `backend/modules/invoice_ingestor/models.py` — `InvoiceRecord(ProductBase)` per 03-design.md.
- `backend/modules/invoice_ingestor/repository.py` — `InvoicesRepository(sessionmaker: async_sessionmaker[AsyncSession])`: `upsert(file_id, data: dict) -> None` (SQLAlchemy `insert().on_conflict_do_update` from `sqlalchemy.dialects.postgresql`), `get(file_id) -> InvoiceData | None`.
- `backend/modules/invoice_ingestor/prompts.py` — `INVOICE_EXTRACTION_PROMPT` (instructs strict JSON matching the InvoiceData schema; no invented fields; `due_date` ISO or null).
- `backend/clients/invoice_ingestor.py` — `InvoiceIngestorClient.parse(...)`.
- `contracts/invoices.py` — per 03-design.md (`InvoiceData`, `InvoiceLineItem`, `InvoiceParseResult`).

## Implementation Guidelines

- No routes in this module in the base (parse happens on demand when a payment run starts). A `POST /invoices/parse` route is fine to add later — not part of base.
- Structured extraction: use `ChatOpenAI.with_structured_output(InvoiceData)` when supported by the OpenRouter model; fallback: JSON-mode prompt + `model_validate_json` + one retry.
- `invoices.data` is jsonb — store `InvoiceData.model_dump(mode="json")`.

## Dependencies

06-files-storage (`FilesClient.read_bytes`), 08-llm-gateway-prompts.

## Integration Notes

Contract consumed by `payments/agent.py`: given a run's `file_id`, seed the payment agent input with `InvoiceParseResult.invoice`. On `InvoiceParseError`, the payments run fails with event `invoice_parse_failed` (see 11-payments).
