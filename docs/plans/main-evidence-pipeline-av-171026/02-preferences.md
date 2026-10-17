# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral (orientative snippets; implementer decides final code)

## 💬 Q&A and Rationale

### 🗄️ Storage & antivirus

**Q:** GuardDuty Malware Protection only scans real AWS S3 (not MinIO, the current storage). Where should evidence files live?
**A:** AWS S3 only — all environments, including local dev, upload to real S3.
**Decision:** Terraform provisions the evidence bucket + GuardDuty plan. `StorageSettings` drops MinIO defaults (endpoint/access keys); backend authenticates via the `panoptico` AWS profile, same as the Bedrock guardrail client. MinIO service removed from docker-compose.
**Rejected:** Hybrid S3+MinIO (split behavior, simulated scans locally) and MinIO-only with fake scan status (does not satisfy the antivirus requirement).

**Q:** GuardDuty scan results arrive asynchronously. How should the pipeline wait?
**A:** Poll S3 object tags.
**Decision:** Enable GuardDuty scan-result tagging at plan creation. After upload, poll `get_object_tagging` (every 2s, ≤60s configurable) for tag `GuardDutyMalwareScanStatus`. No new infrastructure.
**Rejected:** EventBridge→webhook (public endpoint, more moving parts); non-blocking badge-only (infected file would already be parsed).

**Q:** If the scan finds malware (or times out), what happens to the bill?
**A:** Block, fail-closed.
**Decision:** Source is marked `blocked` with a malware violation (same UX as guardrail violations). No agent run, no decision. Status mapping: `THREATS_FOUND`/`FAILED`/`ACCESS_DENIED`/timeout → blocked. `UNSUPPORTED` (no AV engine for the type) → proceed, evidence shows "Sin escaneo" instead of the AWS badge.
**Rejected:** Force human review (still parses/executes a malicious file's content through the LLM chain).

### 🔍 Extraction

**Q:** Engine for last-resort visual extraction on image-only PDFs?
**A:** Textract `AnalyzeExpense`.
**Decision:** Native AWS, purpose-built for invoices/receipts, ~$0.01/page, active service in us-east-1. New `textract_gateway` module (aioboto3, `panoptico` profile). Chain position: after PDF text/LLM fails or PDF has no text; before `no_info`.
**Rejected:** Claude-vision via existing OpenRouter layer (not the "native AWS" ask); chained Claude+Textract (more code than needed).

**Q:** How to extract data from XML inside a ZIP (preferred over PDF)?
**A:** Deterministic parser + LLM fallback.
**Decision:** `parse_invoice_xml()` deterministically parses recognized e-invoice formats (CFDI 3.3/4.0) with confidence 1.0; unrecognized XML falls back to the existing LLM extraction on XML text. XML is always preferred over PDF from the same ZIP.
**Rejected:** LLM-only on XML text (non-deterministic for the most structured input).

### 🏷️ Sources, badges, UI

**Q:** How to model source values (icons wanted: email, Consola, WhatsApp)?
**A:** Reuse `upload` → display as "Consola"; add `whatsapp` enum value now (reserved, no intake yet).
**Decision:** No migration needed (source_type is a plain str column). `BillSourceType.WHATSAPP` added; UI label/icon map covers all values. Assumption: console uploads keep appearing in `/bills` review queue (their DecisionCard shows the Consola icon); the Inbox list stays email-only.
**Rejected:** Adding a separate `console` DB value (churn, `upload` already means exactly this).

**Q:** Badge copy for AWS-scanned evidence (UI is Spanish)?
**A:** "Escaneado por AWS".
**Rejected:** "Analizado por AWS" (broader claim than an antivirus scan), "Protegido por AWS" (marketing-y).

**Q:** How to show process status + agent history for in-analysis bills in the Inbox?
**A:** Detail pane live timeline.
**Decision:** While an email is in a pending status and has `run_id`, the detail pane polls `GET /payments/runs/{run_id}` and renders the step timeline from `agent_run_events` (Postgres) with per-step state. List rows keep their `StatusBadge`; no new list mechanics.
**Rejected:** Expandable rows (new list pattern); both (double surface, double code).

**Q:** How should the UI open evidence files from S3?
**A:** Backend proxy endpoint.
**Decision:** `GET /files/{file_id}/content` streams the object with existing JWT auth (ownership-checked). Frontend fetches it as a blob with the auth header and opens via `URL.createObjectURL` (an `<a href>` cannot send Authorization headers). `nosniff` + CSP sandbox headers on the response.
**Rejected:** Presigned URLs (bypass JWT auth, expire, leak URLs).
