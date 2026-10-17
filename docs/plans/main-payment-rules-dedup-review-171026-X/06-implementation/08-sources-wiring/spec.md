# Sources Wiring Implementation

## Overview

Every entry point registers a bill source before it starts a run, so duplicate deliveries stop at intake. Email sends its body and its PDF together. Chat and upload use the same path. The simulated emails gain the trap cases from `CLAUDE.md`, plus the impersonation case the user asked for.

## Files to Modify/Create

- `modules/inbox/pipeline.py`. `InboxDependencies` gains `bills: "BillsClient"`. Rewrite `_analyze` and `_store_invoice_file` (see below).
- `modules/inbox/repository.py`. Add `mark_duplicate(email_id, file_id)`, which sets `DUPLICATE`, and keep `mark_analyzing`. `UNFINISHED_STATUSES` stays `(RECEIVED, PROCESSING)`.
- `modules/inbox/service.py`
  - `_resolve_status`: map the run's `decision` to an inbox status.
  - `_to_view`: use `decision` instead of `analysis`.
  - `simulate`: unchanged except that the new kinds are added.
- `modules/inbox/samples.py`. Add the trap emails, the attachment builder and `SimulatedEmailKind` members.
- `modules/orchestrator/tools.py`. `build_initiate_payments_tool(payments, bills, owner, session_id)` registers a CHAT source.
- `modules/orchestrator/service.py`. Pass `bills` into the tool builder. `OrchestratorService.__init__` gains `bills: "BillsClient"`.
- `modules/prompts/main_agent.py`. Update the `initiate_payments` description in the prompt: the tool returns `duplicate`, and the agent must tell the user when a bill was already received.
- `api/routers/payments.py`. `trigger_run` takes `UploadRunRequest{file_id}`, registers an UPLOAD source, then calls `start_run`.

## Implementation Guidelines

### Email: body and PDF, one source

```python
async def _analyze(email_id, owner, source, deps) -> None:
    email = await _resolve_email(source, deps)
    await deps.repository.store_content(email_id, email)
    attachment = email.attachments[0] if email.attachments else None
    stored = await deps.files.upload(owner, attachment.filename, attachment.mime, attachment.content) if attachment else None
    if attachment and stored.parse_status != FileParseStatus.PARSED:
        await deps.repository.mark_blocked(email_id, stored.file_id, [UNREADABLE_ATTACHMENT_VIOLATION])
        return
    verdict = await deps.guardrails.check(GuardrailCheckRequest(context=await _guard_text(...)))
    if not verdict.allowed:
        await deps.repository.mark_blocked(email_id, stored.file_id if stored else None, verdict.violations)
        return
    record = await deps.repository.get_email_ref(email_id)        # provider + external_message_id
    registration = await deps.bills.register_source(BillSourceIntake(
        owner_id=owner.user_id, source_type=BillSourceType.EMAIL,
        source_ref=f"{record.provider}:{record.external_message_id}",
        sender=email.sender, body_text=f"{email.subject}\n\n{email.body}",
        file_id=stored.file_id if stored else None,
        attachment_sha256=sha256(attachment.content).hexdigest() if attachment else None,
        inbox_email_id=email_id, received_at=email.received_at))
    if not registration.is_new:
        await deps.repository.mark_duplicate(email_id, stored.file_id if stored else None)
        return
    accepted = await deps.payments.start_run(PaymentRunTrigger(bill_source_id=registration.source.source_id), owner)
    await deps.repository.mark_analyzing(email_id, stored.file_id if stored else None, accepted.run_id)
```

- The body no longer becomes a `text/plain` file. It travels as `body_text`. `mark_blocked` and `mark_analyzing` must accept `file_id=None`; the column is already nullable.
- Add `get_email_ref(email_id) -> tuple[MailProvider, str]` to `InboxRepository`. `InboxEmailRecord` doesn't carry `external_message_id`.

### Inbox status from the decision

```python
VERDICT_INBOX_STATUS = {Verdict.PAY: InboxEmailStatus.PAID, Verdict.HOLD: InboxEmailStatus.HELD,
                        Verdict.REVIEW: InboxEmailStatus.REVIEW}
```

| run | inbox status |
|---|---|
| `COMPLETED` with a `decision` whose bill status is `duplicate` | `DUPLICATE` |
| `COMPLETED` with any other `decision` | `VERDICT_INBOX_STATUS[decision.verdict]` |
| `COMPLETED` with `is_bill=False` | `NO_INVOICE` |
| `FAILED` | `ERROR` with `run.error` |

The `invoice_parse_failed` event no longer exists. A bill that is still in review but was later approved shows its latest decision, because `get_run` reads the latest decision for the bill.

### Chat

```python
@tool(INITIATE_PAYMENTS_TOOL_NAME)
async def initiate_payments(file_id: UUID, reason: str = "") -> dict:
    """Send an uploaded bill to the payments agent. Returns the run id and whether this bill was already received."""
    stored = await files.get(owner, file_id)
    content = await files.read_bytes(owner, file_id)
    registration = await bills.register_source(BillSourceIntake(
        owner_id=owner.user_id, source_type=BillSourceType.CHAT, source_ref=f"{session_id}:{file_id}",
        sender=owner.email, body_text=reason, file_id=file_id,
        attachment_sha256=sha256(content).hexdigest()))
    accepted = await payments.start_run(PaymentRunTrigger(bill_source_id=registration.source.source_id, session_id=session_id), owner)
    return {"run_id": str(accepted.run_id), "status": str(accepted.status), "duplicate": not registration.is_new or accepted.duplicate}
```

- When the source is not new and no run is active, `start_run` would create a new run for the same source. To keep a replay from re-deciding, `start_run` returns the most recent run for the source when the source already has a `bill_id`. Implement this in `PaymentsService.start_run`: if `source.bill_id` is set, return the latest run for the source with `duplicate=True` and spawn nothing.
- `files.read_bytes` already exists on `FilesClient`. The orchestrator gains `files` access to it (it already holds `files`).

### Upload (`POST /payments/runs`)

Same as chat, with `source_type=UPLOAD` and `source_ref=f"upload:{file_id}"`. Keep the existing `guardrails.require_allowed` call.

### Simulated trap emails (`samples.py`)

Add `SimulatedEmailKind` members and `SIMULATED_EMAILS` entries. Each sender, account and amount lines up with the seed in `02-payment-policy`.

| kind | content | expected |
|---|---|---|
| `invoice_usd` (existing ACME 120 USD) | from `billing@acmecloud.io`, account `000123456789` | PAY |
| `aws_card` | AWS invoice, USD 840, account id 123456789012, from `no-reply@aws.amazon.com`, "charged to card on file" | PAY |
| `aws_impersonation` | "Amazon Web Services" invoice, USD 950, asks for a transfer to `CL-BE-99887766` (María's personal account), from `billing@aws-invoices.net` | HOLD R05 |
| `amaz0n_blacklisted` | from `@amaz0n-billing.com` | HOLD R03 |
| `over_auto_pay` | Servicios Integrales del Sur, CLP 1.400.000 (about 1,470 USD), RUT 76.543.210-K | REVIEW R13 |
| `over_hard_cap` | ACME, USD 6,200 | HOLD R12 (+R17) |
| `unknown_payee` | "Diseños Lumen Ltda", USD 300 | REVIEW R04 |
| `no_currency` | María, "$2.000", no ISO code | REVIEW R01 |
| `person_cuenta_cobro` | María, honorarios USD 2,000, no invoice number, due date set | PAY |
| `agreement_mismatch` | ACME, USD 180 against agreed 120 ±5% | REVIEW R17 |
| `invoice_usd_pdf` | ACME 120 USD with a PDF attachment generated in code | PAY, or HOLD DUP if `invoice_usd` was simulated first (same fingerprint) |
| `prompt_injection` (existing) | | guardrail BLOCKED, or HOLD R02 if guardrails are off |

- Simulating `invoice_usd` twice gives HOLD DUP. The fingerprint matches, even though each `source_ref` is a fresh `sim-<uuid>`.
- Budget exhausted: simulate `person_cuenta_cobro` twice with different due dates. That gives two canonical bills; the second goes to REVIEW (R11). Approving it hits María's 2,500 USD monthly budget, so it ends HOLD at reservation. Document this flow in the sample's subject line ("(2/2)").
- PDF builder: add `_minimal_pdf(lines: list[str]) -> bytes` in `samples.py`. It writes a single-page PDF with Helvetica text objects: header, one `BT ... ET` stream, xref and trailer, about 30 lines, with no new dependency. pypdf must be able to extract its text (`FilesService` parse status must be PARSED). If you can't make pypdf read it, fall back to `.txt` attachments and drop `invoice_usd_pdf`.

## Dependencies

`clients/bills.py` (03), `contracts/bills.py`, `contracts/payments.py` (new trigger), `hashlib.sha256`.

## Integration Notes

- The inbox never reads `bills` directly. It reads the decision through `payments.get_run(run_id)`.
- Telegram later: a `modules/telegram_gateway` adapter registers `BillSourceType.TELEGRAM` with `source_ref=f"{chat_id}:{message_id}"`. It needs no schema change.
