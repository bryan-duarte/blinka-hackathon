# Frontend Executions Pages Implementation

## Overview

This module adds three pages. `/runs` lists every agent execution. `/runs/[id]` is the business summary: a timeline from the persisted events, the decision card, evidence and FX. `/runs/[id]/trace` is a separate technical page that shows the full LLM trace from the LangGraph checkpoint. The summary and the trace pages link to each other.

**Re-read `frontend/DESIGN.md` fully first. Read `frontend/node_modules/next/dist/docs/` before writing the dynamic routes.** In Next 16, `params` may be a Promise and need `use(params)`; check the docs before using it.

## Files to Modify/Create

- `frontend/src/app/runs/page.tsx` (new): the runs list.
- `frontend/src/app/runs/[id]/page.tsx` (new): the business summary.
- `frontend/src/app/runs/[id]/trace/page.tsx` (new): the technical trace.
- `frontend/src/components/runs/RunsTable.tsx` (new)
- `frontend/src/components/runs/RunTimeline.tsx` (new)
- `frontend/src/components/runs/RunHeader.tsx` (new)
- `frontend/src/components/runs/TraceMessageCard.tsx` (new)
- `frontend/src/components/runs/JsonBlock.tsx` (new)
- `frontend/src/components/inbox/EmailDetail.tsx`: when the item has a `run_id`, add a "View execution ›" link to `/runs/{run_id}`.
- `frontend/src/components/inbox/AgentActivity.tsx`: in the expanded "View details" state, add an "Open full execution ›" link to `/runs/{runId}`.

## Implementation Guidelines

### `/runs`

- Data: `api.runs(status)`. Status filter toggles: All · Running · Completed · Failed. The page polls every 5 s while any run is `pending` or `running`.
- Columns: Started (relative time, with the absolute time as a `title`) · Status badge · Source (channel badge, sender and subject truncated) · Verdict (outcome tone) · Tools (`tool_count`) · Duration (`formatDuration(ms)` → "42 s") · "›". The whole row links to `/runs/{run_id}`.
- Empty state: "No executions yet. Send a demo scenario from the inbox."

### `/runs/[id]` (business summary)

The page has 3 fetches: `api.runStatus(id)`, which already exists and returns events, decision, evidence and `is_bill`; `api.bill(decision.bill_id)` when there is a bill, for the history, sources and payment; and the inbox email, when the run links to one, for the subject and body preview. Fetch the email only if that link is cheap to resolve; otherwise rely on the `RunListItemView` fields, re-fetched with `api.runs()` and filtered by id, or add `GET /runs/{id}` to the 09 backend if that's cleaner. Pick one option and document it in the code.

Layout:

1. `RunHeader`: shows the status, the started time and duration, the channel and subject, and the actions "View full LLM trace ›" (goes to `./trace`) and "Back to ledger".
2. `RunTimeline`: a vertical `border-l` timeline built from `events`:
   - It reuses `collectToolRuns` and the `latestTodos` logic from `AgentActivity.tsx`. Extract them into `frontend/src/lib/runEvents.ts` so both use the same code instead of copying it.
   - Each tool row shows the step name (e.g. "Extract invoice"), the English `message` from `phrases.py` (03), the duration and ok/✕, plus an expandable summary from `tool_finished.payload.summary`, which is capped at 280 characters and points to the trace page for the full output.
   - The plan checklist (todos) sits at the top, followed by the agent summary.
3. Decision: reuse `DecisionCard` as is. It already renders the verdict, rules, checker, evidence and history, and it now uses `MoneyWithUsd` (10).
4. FX panel: original amount, USD amount, rate, rate date and source label. Shown only for non-USD bills.
5. Evidence: reuse `EvidenceSection`.

### `/runs/[id]/trace` (technical)

- Data: `api.runTrace(id)`. When `is_available` is false, show "The full trace is no longer available for this execution (the checkpoint was cleared)." along with a link back to the summary.
- Messages render in order as `TraceMessageCard` items:
  - Role eyebrow (System prompt · Task · Agent · Tool result), the index, and for tools the tool name.
  - SYSTEM and HUMAN messages: `<pre className="whitespace-pre-wrap">`, collapsed after 12 lines, with a "Show all" toggle.
  - AI messages: the text, then each tool call as `name(args)` with args in a `JsonBlock`.
  - TOOL messages: `JsonBlock` of `output_json` when present, otherwise `<pre>`. Highlight `"final": true` and `"error"` keys.
- `JsonBlock` uses `JSON.stringify(value, null, 2)` in a `<pre>` with a `bg-sunken` background, the monospace stack from DESIGN.md (or `ui-monospace`) and a "Copy" button that calls `navigator.clipboard.writeText`. No syntax-highlighting dependency.
- A sticky mini-index on the left on `lg` screens: a list of tool calls with anchor links.
- Header actions: "Back to summary ›" and "Copy full trace (JSON)".

### Copy

Everything is in English, for example: "Execution", "Full LLM trace", "Plan", "Steps", "Agent summary", "Decision", "Exchange rate".

## Dependencies

- 10 (types, API, labels, `MoneyWithUsd`), 09 (`/runs`, `/payments/runs/{id}/trace`) and the existing `/payments/runs/{id}` and `/bills/{id}` endpoints.

## Integration Notes

- The ledger rows from 12 link here.
- `frontend/src/lib/runEvents.ts` becomes the single source of the event-pairing logic for `AgentActivity` and `RunTimeline`.
