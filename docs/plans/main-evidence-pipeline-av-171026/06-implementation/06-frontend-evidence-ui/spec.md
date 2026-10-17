# Frontend — source icons, evidence badges, live run timeline

## Overview

Surface the new backend data in the console: source badge per process, openable evidence with the "Escaneado por AWS" badge, the `no_info` status, and a live agent-step timeline in the Inbox detail pane while a bill is in analysis.

**Read `frontend/DESIGN.md` fully before touching anything and follow it strictly** (it is replaced often). Read `frontend/AGENTS.md` for Next.js 16 caveats. Load the `us-frontend-design` skill before starting UI work.

## Files to Modify/Create

- `frontend/src/lib/types.ts` — `EvidenceFileView`, `EvidenceRole`, `FileScanStatus`, `BillSourceType += "whatsapp"`, `InboxEmailStatus += "no_info"`, `InboxEmailView.source_type`, `InboxEmailDetail.evidence`, `BillDetail.evidence`, `PaymentRunStatus.evidence` (mirror of module 05 contracts)
- `frontend/src/lib/api.ts` — `runStatus(runId): Promise<PaymentRunStatus>` (GET `/payments/runs/{id}`); `openFile(fileId)`: fetch `/files/{id}/content` with auth header → blob → `URL.createObjectURL` → `window.open` (revoke after open)
- `frontend/src/lib/labels.ts` — `SOURCE_LABELS` (Correo/Consola/Chat/Telegram/WhatsApp), `ROLE_LABELS` (Fuente/Factura PDF/Archivo ZIP — pick final copy at implementation), `SCAN_LABELS`, `RUN_STEP_LABELS` (see below)
- `frontend/src/components/inbox/SourceBadge.tsx` (new) — icon + accessible label
- `frontend/src/components/files/EvidenceBadge.tsx` (new) — "Escaneado por AWS" pill
- `frontend/src/components/files/EvidenceSection.tsx` (new) — evidence list, openable
- `frontend/src/components/inbox/RunTimeline.tsx` (new) — live step timeline
- `frontend/src/components/inbox/EmailList.tsx` — row gains `SourceBadge` next to the sender line
- `frontend/src/components/inbox/EmailDetail.tsx` — `SourceBadge` in header; `<EvidenceSection>` after the body; pending branch renders `<RunTimeline>`; `no_info` notice in `ResultCard`
- `frontend/src/components/inbox/StatusBadge.tsx` — `BADGES` entry for `no_info` (label "Sin datos", glyph `!`, `NEUTRAL` styling)
- `frontend/src/components/bills/DecisionCard.tsx` — eyebrow shows the source of the first `source` (Consola icon for console uploads); `<EvidenceSection>` inside the card

## Implementation Guidelines

Icons: no icon library. Inline SVGs, 16px, 1.5px cobalt (`var(--color-accent)`) stroke line-art per DESIGN.md "Imagery": envelope (Correo), terminal prompt in a square (Consola), chat bubble (Chat), paper-plane (Telegram), phone-in-bubble (WhatsApp). `SourceBadge` renders icon + `sr-only` label; visible text label only in detail headers.

`EvidenceBadge` (`scan_status === "clean"`): pill matching `StatusBadge` NEUTRAL convention — `inline-flex items-center gap-1 rounded-full border border-line bg-panel px-2 py-0.5 text-xs text-muted`, tiny shield glyph, text "Escaneado por AWS". `unsupported` → quiet text "Sin escaneo" (`text-quiet`), no pill. Never cobalt fill; never green.

`EvidenceSection`: eyebrow "Evidencia"; one row per file — filename (text-link button with trailing `›` per the `DuplicateLink` pattern, opens `api.openFile`), size (`formatBytes`, add to `lib/format.ts`), `ROLE_LABELS[role]`, `EvidenceBadge`. Empty state (data-in-email case): "Sin archivos — los datos vienen del correo." — the section renders nothing when `evidence` is empty/undefined.

`RunTimeline`: props `{ runId: string }`. Poll `api.runStatus(runId)` every 3s **only while** `status` is `pending|running` (stop on `completed|failed`; also stop when the parent email leaves `PENDING_STATUSES`). Ordered steps map (`RUN_STEP_LABELS`): `started→Recibido`, `classified→Clasificado`, `not_a_bill→No es factura`, `extracted→Datos extraídos`, `extraction_failed→Sin datos legibles`, `claimed→Registrada`, `decided→Decidido`, `completed→Listo`, `failed→Error`. Render as the existing timeline pattern in `DecisionHistory`: `<ol className="border-l border-line pl-4">`, each seen step `✓` + label + `formatRelativeTime(created_at)`; latest seen step pulses (`animate-pulse`) while the run is unfinished; unseen upcoming steps render as muted placeholders below. Include `event.payload` hints minimally (e.g. `decided` shows the verdict label).

`ResultCard` pending branch: keep the existing pulse bar + copy, then `<RunTimeline runId={email.run_id} />` when `run_id` exists. `no_info` branch: neutral notice "No se pudo leer la información de la factura. Ningún método de extracción produjo datos." (copy adjustable at implementation, Spanish, no em-dashes).

`EmailList` row: `<SourceBadge type={email.source_type} />` inline before the sender text; no layout changes otherwise.

Self-check (`pnpm dev` + simulate): ZIP email → row shows Correo badge; while analyzing, detail shows live steps appearing over ~seconds and stops polling on completion; decided email shows evidence rows; clicking the XML filename opens its content in a new tab; badge reads "Escaneado por AWS"; a `no_info` email shows the notice + badge. Verify against DESIGN.md checklist: 4px radii, pills only for badges, cobalt only as accent, tabular numerals for sizes.

## Dependencies

- Backend modules 04 + 05 contracts must be merged first (types mirror them).
- No new npm packages.

## Integration Notes

- `PENDING_STATUSES` (`lib/types.ts:283`) already drives inbox polling — reuse for both the page poll and `RunTimeline` lifecycle.
- Blob-download approach is required because `<a href>` cannot send the `Authorization` header; keep the object URL revocation to avoid leaks.
- All user-visible copy Spanish, es-CL formatting via `lib/format.ts`.
