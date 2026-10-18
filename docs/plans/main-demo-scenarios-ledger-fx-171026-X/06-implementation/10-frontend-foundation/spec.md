# Frontend Foundation Implementation

## Overview

This step does the groundwork the other UI specs depend on:

- Translate the whole console to English and switch formatting to `en-US`.
- Mirror the new backend contracts in `types.ts` and add the API calls.
- Add a shared `MoneyWithUsd` component.
- Update the nav and add the "Enter the demo" login button.
- Remove the old simulate code.

**Before starting, re-read `frontend/DESIGN.md` in full and follow its latest version strictly. Also read `frontend/node_modules/next/dist/docs/` for the Next 16 specifics.**

## Files to Modify/Create

- `frontend/src/app/layout.tsx`: change `<html lang="es">` to `lang="en"`, and translate the metadata title and description.
- `frontend/src/lib/format.ts`: replace every `es-CL` with `en-US`. `formatMoney(amount, currency)` renders `CLP 1,150,000` / `USD 1,198.08`.
  - Add `formatRate(usdPerUnit: Decimal): string`, which uses significant digits (`1 CLP = 0.001052 USD`; `maximumSignificantDigits: 4`).
  - Add `formatPeriod("2026-10")`, which returns "October 2026".
- `frontend/src/lib/labels.ts`: translate every label map to English and add these:
  - `LEDGER_OUTCOME_LABELS`: Paid · Escalated to a person · Held · Approved by a person · Rejected by a person · Duplicate · Blocked · Not an invoice · Missing information · Error
  - `FX_SOURCE_LABELS`: see 02
  - `DEMO_SECTION_LABELS`
  - `RUN_STATUS_LABELS`
  - `TRACE_ROLE_LABELS`
- Every page and component with Spanish copy: `inbox/*`, `bills/*`, `files/*`, `settings/*`, `console/ConsoleShell.tsx`, `app/login`, `app/bills`, `app/settings/*`, `app/inbox/*`, `app/page.tsx` (landing). Translate all of it. Find what's left with `rg -n "[áéíóúñ¿¡]|Bandeja|Cola de|Beneficiario|Política|Pagar|Factura" frontend/src`.
- `frontend/src/components/console/ConsoleShell.tsx` `NAV_GROUPS`:
  ```ts
  [
    { label: "Payments", items: [
      { href: "/inbox", label: "Inbox" },
      { href: "/bills", label: "Review queue" },
      { href: "/ledger", label: "Agent ledger" },
      { href: "/runs", label: "Executions" },
    ]},
    { label: "Payment rules", items: [
      { href: "/settings/policy", label: "Policy" },
      { href: "/settings/payees", label: "Payees" },
      { href: "/settings/blacklist", label: "Blacklist" },
    ]},
  ]
  ```
  Check the active-link logic: `/runs/[id]` should highlight "Executions" (use a prefix match if it is currently exact).
- `frontend/src/lib/types.ts`:
  - Remove `SimulatedEmailKind`.
  - Add FX fields to `BillDecisionView` and `PaymentView`.
  - Add every type from 03-design: Demo*, Kit*, TrustedForwarder*, Ledger*, `RunListItemView`, `RunTraceView`, `TraceMessage`, `TraceToolCall`, `FxSource`.
- `frontend/src/lib/api.ts`:
  - Remove `api.simulate`.
  - Add the demo, kit and trusted-forwarder calls (listed in 08), the ledger calls (`ledgerEntries(filters)`, `ledgerSummary(period, months)`, `exportLedgerCsv(filters)`), `runs(status?)` and `runTrace(runId)`.
  - Add a shared helper `downloadBlob(path: string, filename: string)` that fetches with the token and clicks a temporary `<a download>`.
- `frontend/src/components/money/MoneyWithUsd.tsx` (new):
  ```tsx
  type MoneyWithUsdProps = {
    amount: Decimal | null; currency: string | null; amountUsd: Decimal | null;
    usdPerUnit?: Decimal | null; rateDate?: string | null; fxSource?: FxSource | null;
    layout?: "inline" | "stacked";
  };
  ```
  - The original amount is the primary line (tabular numerals).
  - For a non-USD currency, add a muted second line: `≈ USD 1,198.08 · 1 MXN = 0.05547 USD · Oct 17 · Live rate`.
  - For USD, show only the primary line.
  - If `amountUsd` is null, show "No USD rate" in the warning tone.
  - Use it in `DecisionCard.tsx` `VerdictHeader` (replacing the current "≈ USD" rendering), `EmailDetail.tsx`, the ledger table (12) and the run summary (13).
- `frontend/src/app/login/page.tsx`:
  - On mount, call `api.demoStatus()`. When `is_enabled` is true, render a secondary button "Enter the demo" plus a hint "Andescape Labs, Inc. · demo data, resettable".
  - On click: call `api.demoLogin()`, then `tokenStore.set(token)`, then `router.replace("/inbox")`.
- `frontend/package.json`: add `recharts` with `pnpm --filter @blinka/web add recharts@<exact 3.x>`.

## Implementation Guidelines

- Translation is copy-only. Don't restructure components.
- Keep the existing tone constants (`NEEDS_ACTION`, `SETTLED`, `STOPPED`).
- Use the "warning" alias (cobalt) for escalated, "danger" (night) for held, blocked and rejected, and "success" (gray) for paid. These match the semantic aliases in `globals.css`.
- Check that `useReportError()` and the error strings in `components/settings/errors.ts` are translated.

## Dependencies

- Backend contracts from 02, 05, 07, 08 and 09.
- `recharts` (new).

## Integration Notes

- 11, 12 and 13 import `MoneyWithUsd`, the new types, the API calls and the labels from here.
- Merge order: land the backend first so the types match real responses.
