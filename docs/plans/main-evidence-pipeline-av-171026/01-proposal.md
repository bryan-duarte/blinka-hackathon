# Evidence Pipeline: S3 + Antivirus, ZIP/XML ingestion, visual extraction & UI evidence

> "Trust me, the invoice is in the ZIP inside the email. What could possibly go wrong?"
> - El Barto

## Overview

**Request**: Improve platform behavior: handle bills inside ZIPs (preferring the XML e-invoice inside), store all process evidence files in S3 linked to each agent run, add AWS antivirus scanning, add visual extraction as last resort before "no info", use specific active native AWS services, show a source icon (Correo/Consola/WhatsApp) per process, show openable "Escaneado por AWS" evidence badges, and show live process status + agent history in the Inbox.

**Created**: 2026-10-17

## What

1. **AWS S3-only evidence storage** (replaces MinIO) with **GuardDuty Malware Protection for S3** scanning every uploaded object. Pipeline polls the scan-result tag and **blocks (fail-closed)** any file that is infected, errors, or times out.
2. **ZIP/XML ingestion**: mail gateway and console uploads accept `.zip` and `.xml`; ZIPs are safely expanded and the **XML e-invoice is preferred** over the PDF in the same ZIP.
3. **Extraction chain**: deterministic multi-country XML parse (format detected by root namespace: CFDI MX, DTE CL, UBL CO/PE/EU, CII EU — with ISO country + currency per document) → LLM on XML text → PDF text via LLM → **Textract `AnalyzeExpense`** (native AWS) for image-only PDFs → explicit `no_info` terminal state.
4. **Evidence model**: new `agent_run_files` table linking each agent run (and bill source) to its files with roles (archive / primary / secondary), surfaced through the API with scan status.
5. **UI**: source badge (Correo / Consola / WhatsApp reserved / Chat / Telegram), openable evidence list with "Escaneado por AWS" badge (backend-proxy download), `no_info` status, and a live agent step timeline in the Inbox detail pane while a bill is in analysis.

## Why

- ZIPs and XML e-invoices are dropped silently today (only the first PDF is ever fetched, mime hardcoded).
- Image-only PDFs are blocked before the LLM ever runs — real bills get stuck with no recourse.
- Evidence is write-only: files land in MinIO with no download endpoint, no antivirus, no per-run multi-file linkage.
- The Inbox shows nothing about in-flight analysis even though `agent_run_events` already records every step in Postgres.

## Impact

- **Infra**: Terraform gains S3 bucket + GuardDuty malware protection plan + IAM policies (backend user gets S3 + Textract). MinIO removed from docker-compose.
- **Backend**: `files` (S3-only client, scan polling, download proxy), `mail_gateway` (multi-attachment), `inbox/pipeline` (multi-file + scan gating), new `textract_gateway` module, `invoice_ingestor` (extraction chain), `payments` (evidence linkage, `extraction_failed` → `no_info`), contracts + 1 Alembic migration (product branch).
- **Frontend**: `types.ts`/`api.ts`/`labels.ts` extensions, new `SourceBadge`, `EvidenceSection`/`EvidenceBadge`, `RunTimeline` components, `StatusBadge`/`ResultCard` updates.
- **New dependency**: `defusedxml` (XXE-safe XML parsing).

## Flow

```
Email webhook / Console upload / (Chat)
        │
        ▼
 Attachment selection (.zip, .xml, .pdf)          ← mail_gateway (was: first-PDF-only)
        │
        ▼
 Upload every file to S3  ──► GuardDuty Malware Protection scan (on PUT)
        │                        │ tag: GuardDutyMalwareScanStatus
        ▼                        ▼
 Poll tag ≤60s ── THREATS_FOUND / FAILED / timeout ──► BLOCKED (fail-closed, no run)
        │ NO_THREATS_FOUND
        ▼
 ZIP? expand safely → members (.xml/.pdf)
        │
        ▼
 Pick primary source: XML > PDF        ← evidence rows: archive / primary / secondary
        │
        ▼
 Extraction chain:
   XML ──► deterministic CFDI parse ── fail ──► LLM on XML text
   PDF ──► pypdf text + LLM ── empty/fail ──► Textract AnalyzeExpense ── fail ──► no_info
        │
        ▼
 Agent run steps (agent_run_events) ──► Inbox detail live timeline
 Decisions + evidence (S3 files, scan status) ──► UI badges, openable via GET /files/{id}/content
```
