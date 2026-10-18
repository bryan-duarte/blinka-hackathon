# Frontend Agent Ledger Implementation

## Overview

`/ledger` is the agent's accountability book. It has a KPI strip, four Recharts charts, verdict tabs, filters, a table of every outcome with its reasons and original and USD amounts, a CSV export, and an FX attribution footer.

**Re-read `frontend/DESIGN.md` fully first.** Before writing any chart code, also load the `dataviz` skill for the chart color, mark and axis rules, then map its palette onto DESIGN.md tokens.

## Files to Modify/Create

- `frontend/src/app/ledger/page.tsx` (new): a `"use client"` page with the auth guard, `<ConsoleShell><ConsoleTopBar title="Agent ledger" caption="Every decision the agent made, and why" actions={<ExportButton/>}/>…`.
- `frontend/src/components/ledger/LedgerKpis.tsx` (new)
- `frontend/src/components/ledger/DecisionsOverTimeChart.tsx` (new)
- `frontend/src/components/ledger/LimitsChart.tsx` (new)
- `frontend/src/components/ledger/TopReasonsChart.tsx` (new)
- `frontend/src/components/ledger/CurrencyBreakdown.tsx` (new)
- `frontend/src/components/ledger/LedgerTable.tsx` (new)
- `frontend/src/components/ledger/LedgerFilters.tsx` (new)
- `frontend/src/components/ledger/chartTheme.ts` (new): reads CSS variables at runtime (`getComputedStyle(document.documentElement).getPropertyValue("--color-accent")`) so the charts follow the `globals.css` tokens. It exports `CHART_COLORS = { paid, escalated, stopped, grid, axis, label }` and `AXIS_TICK_STYLE` (12px, weight 300, `--color-muted`, tabular numerals).

## Implementation Guidelines

### Page state

- `filters: LedgerFilters` defaults to `{ period: currentPeriod(), tab: "all" }` and is kept in the URL search params so the view can be shared and survives a reload. Use `useSearchParams` and `router.replace`, and check the Next 16 docs on wrapping in `Suspense`.
- Two fetches run in parallel inside `useEffect`, using the `isCancelled` pattern from `bills/page.tsx`: `api.ledgerSummary(period, 4)` and `api.ledgerEntries(filters)`.
- Refresh when realtime sends a terminal `run.step` event: reuse `useInboxChannel` and the `TERMINAL_RUN_STEPS` set from `inbox/page.tsx` (move it to `lib/` so both pages share it).

### Layout (top to bottom)

1. **KPI strip** (`LedgerKpis`). Follow the `InboxMetrics` pattern: `divide-x divide-line` with no cards, big weight-300 numbers and muted labels.
   - Paid: count and USD total
   - Escalated to a person: count and USD
   - Stopped by the agent: count and USD, labeled "money protected"
   - Auto-pay rate, as a percentage
2. **Charts grid**: `grid gap-6 lg:grid-cols-2`, with each chart in a `CARD_CLASS` panel that has an `EYEBROW_CLASS` title.
   - `DecisionsOverTimeChart`: a Recharts `BarChart` stacked by `paid`, `escalated` and `stopped` per week bucket over the last 4 months. Paid uses `--color-success`, escalated `--color-accent`, and stopped `--color-night`. It needs a legend and a tooltip showing counts. Turn off animation when `prefers-reduced-motion` is set (`isAnimationActive={!reducedMotion}`).
   - `LimitsChart`: a horizontal `BarChart` (`layout="vertical"`) with one row per `LimitUsage` and the bar value `spent_usd`. A `ReferenceLine` or background bar shows `limit_usd`. Rows at or above 90% get the `--color-night` fill and a "Limit reached" label at 100%. The Y-axis label shows the name and the payee's local currency in muted text (e.g. "Andrés Felipe Gómez · COP").
   - `TopReasonsChart`: a horizontal `BarChart` of `count` by rule, labeled `R14 · Budget available`. Get the human label by mapping `rule_id` through a `RULE_LABELS` map in `labels.ts`, adding it if missing.
   - `CurrencyBreakdown`: a compact table rather than a pie: currency, original total (`formatMoney`), USD total and count, plus a thin inline bar for the USD share. The `dataviz` skill discourages pies for this.
3. **Tabs and filters** (`LedgerFilters`):
   - Tabs: All · Paid · Escalated · Stopped. Use `aria-pressed` toggle buttons, the same as `FilterTab` in `inbox/page.tsx`, and show counts from the entries.
   - A period select listing the last 6 months plus "All time".
   - Payee and currency selects, populated from the summary limits or from `api.payees()`, and from the distinct entry currencies.
4. **Table** (`LedgerTable`): `divide-y divide-line` rows, or a semantic `<table>` with sticky headers.
   - Columns: Date · Outcome badge (labels from `LEDGER_OUTCOME_LABELS`, tone from 10) · Payee and kind · Amount (`<MoneyWithUsd layout="stacked">`) · Reasons (first two non-pass reasons as `R14 · reason text`, with "+N more") · Channel (`SourceBadge`) · "View execution ›".
   - The execution link goes to `/runs/{run_id}`. When there is no `run_id` (seeded history or inbox-only rows), show muted text instead: "Imported history" when `is_seeded`, or "Stopped before the agent" for blocked entries.
   - Clicking a row expands it inline, showing the full explanation, every non-pass reason, the human note, the FX detail and the subject.
   - Empty state: "No decisions in this period yet. Send a demo scenario from the inbox."
5. **Footer**: muted 12px text reading "Exchange rates: live rates by Exchange Rate API (open.er-api.com), cached daily; fallback table when offline." The first part links to `https://www.exchangerate-api.com`, which their terms of use require.

### Export

The `ExportButton` (`SECONDARY_BUTTON_CLASS`, "Export CSV") calls `api.exportLedgerCsv(filters)` through `downloadBlob`, with the filename `agent-ledger-{period}.csv`.

### Recharts notes

- Import only the components you use (`BarChart`, `Bar`, `XAxis`, `YAxis`, `Tooltip`, `Legend`, `ResponsiveContainer`, `ReferenceLine`, `CartesianGrid`).
- Recharts needs the client. These are client components already. If SSR warnings show up, wrap the charts with a `dynamic(() => import(...), { ssr: false })`, following the Next 16 docs.
- Style the tooltip with no shadow, a `border-line` 1px border, `bg-panel` and the 4px radius, using `contentStyle` / `wrapperStyle`.

## Dependencies

- 10 (`recharts`, types, API, `MoneyWithUsd`, labels) and 09 (endpoints).

## Integration Notes

- The row link targets `/runs/[id]` from 13.
- `RULE_LABELS` added here is shared with the 13 run summary.
