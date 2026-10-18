# Frontend Demo Scenarios Panel Implementation

## Overview

This adds a right-side slide-over in the inbox, shown only to the demo account. It lists the scenarios by section, each with its expected outcome and a fixed channel badge, plus a Send button and live step progress. It also offers file downloads for self-sending, the send destinations, a trusted-forwarders editor, and "Reset demo" behind a confirm dialog.

**Re-read `frontend/DESIGN.md` fully before building and follow it strictly.** That means no shadows, so depth comes from tint steps; 4px radius; weight 300; and cobalt for actions only.

## Files to Modify/Create

- `frontend/src/components/demo/DemoScenariosPanel.tsx` (new): exports `DemoScenariosPanel({ isOpen, onClose, onLaunched, onReset })`.
- `frontend/src/components/demo/ScenarioRow.tsx` (new): exports `ScenarioRow({ scenario, launch, onSend, onDownload })`.
- `frontend/src/components/demo/LaunchProgress.tsx` (new): renders step chips (`Step 1 · Paid ✓`, `Step 2 · Waiting…`, `Step 2 · Duplicate ✓`, or `✕ expected Duplicate, got Paid`).
- `frontend/src/components/demo/ResetDemoDialog.tsx` (new): a confirm dialog built on the native `<dialog>` element.
- `frontend/src/components/demo/SelfSendCard.tsx` (new): destinations, "Download full kit (.zip)", and the trusted forwarders list with add and remove.
- `frontend/src/lib/useDemoLaunches.ts` (new): a hook that holds `Record<scenarioId, DemoLaunchView>` and polls `api.demoLaunch(id)` every `LAUNCH_POLL_MS = 2000` while any launch is `running`.
- `frontend/src/app/inbox/page.tsx`:
  - Delete `SimulationOption`, `WHATSAPP_SIMULATION_OPTIONS`, `EMAIL_SIMULATION_OPTIONS`, `SIMULATION_GROUPS`, `simulate()` and the old menu markup.
  - Compute `isDemoAccount`: decode the email from the JWT if `currentUserId()` has a sibling helper; otherwise compare against `api.demoStatus().email`.
  - When `isDemoAccount` is true, add a `SECONDARY_BUTTON_CLASS` button "Demo scenarios" to the `ConsoleTopBar` `actions`.
  - Render `<DemoScenariosPanel>`.
  - `onLaunched` and `onReset` bump the existing `refreshCount`. After a reset, also clear the selected email.
  - Handle the realtime `inbox.item` event with `payload.status === "reset"` by triggering a refresh.

## Implementation Guidelines

### Layout (orientative ASCII)

```text
┌──────────────────────────── Inbox ─────────────────────────────┬──── Demo scenarios ─────── ✕ ┐
│ list …                                     detail …            │ Andescape Labs, Inc.          │
│                                                                │ Guardrail on · Malware scan on│
│                                                                │ ▾ Happy path (3)              │
│                                                                │   ACME Cloud invoice in email │
│                                                                │   Expected: Paid       [Email]│
│                                                                │   Files ↓            [ Send ] │
│                                                                │ ▾ Duplicates (4)              │
│                                                                │   Same invoice sent twice     │
│                                                                │   ① Paid ✓  ② Duplicate …     │
│                                                                │ ▸ Formats · Rules · Limits ·  │
│                                                                │   Security                    │
│                                                                │ ── Send it yourself ───────── │
│                                                                │ Email: demo-inbox@…  WA: +1…  │
│                                                                │ Trusted forwarders  [+ add]   │
│                                                                │ [ Download full kit (.zip) ]  │
│                                                                │ ── ────────────────────────── │
│                                                                │ [ Reset demo ]  (danger text) │
└────────────────────────────────────────────────────────────────┴───────────────────────────────┘
```

- Panel width is `w-full sm:w-[420px]`. It is fixed to the right, `bg-panel`, with a `border-l border-line` and its own scroll. Close it on Esc and on the ✕ button. The focus trap uses the `<dialog>` element with `showModal()`, or a manual trap, following any modal pattern already in the codebase.
- Sections are `<details>` disclosures using the same chevron pattern as `DecisionCard`'s passing rules. Happy path is open by default.
- Each row shows:
  - title (14px)
  - description (muted, 13px)
  - "Expected:" followed by the outcome label from `LEDGER_OUTCOME_LABELS`, or a status label, plus the key rule IDs as small sunken pills. Sequences show one chip per step.
  - channel badge (reuse `SourceBadge`)
  - "Send" (`PRIMARY_BUTTON_CLASS`, small). It is disabled while that scenario's launch is running and shows "Sending…".
  - "Files" (`QUIET_BUTTON_CLASS`), shown when `is_self_sendable`. It calls `api.downloadScenarioKit(id)`. Its `title` is the `self_send_hint`.
- When `is_guardrail_enforced` is false, show a muted notice on the security section: "Guardrail is off: injection cases will be held by rule R02 instead of blocked."
- When `is_malware_scan_enabled` is false, disable `security_malware` and give it the hint "Enable the malware scan to run this case".
- Reset:
  - The confirm dialog reads: title "Reset the demo?", body "This deletes every message, decision, payment and file for the demo account and restores the initial data. Connected mailboxes are kept."
  - Buttons: "Cancel" and "Reset demo" (danger).
  - While it runs, show "Resetting…" and disable every Send button.
  - On success, show a toast-like inline line: "Demo restored: {seeded_bills} historical bills loaded."
  - On 409, show "Demo is busy, try again in a moment."
- Live progress: after `launchScenario`, store the returned launch and let `useDemoLaunches` poll it. On every poll that changes a step's `email_id`, call `onLaunched()` so the inbox refreshes and can select the newest item. Auto-selecting the first email of the launch is a nice touch; do it only if the existing inbox page makes it easy.

### Copy

All copy is in English. Section titles: Happy path · Formats · Duplicates · Rules & agreements · Limits & budget · Security.

## Dependencies

- 10 (types, API calls, labels), plus 05, 07 and 08 on the backend.

## Integration Notes

- The panel holds no ledger logic. Outcomes appear in the inbox and the ledger through the existing flows.
- `isDemoAccount` gating is cosmetic; the backend enforces it with `DemoUserDep`.
