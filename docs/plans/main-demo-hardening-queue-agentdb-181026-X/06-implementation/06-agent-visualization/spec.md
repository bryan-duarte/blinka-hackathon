# Agent Visualization (Frontend) Implementation

## Overview

Render the new events so the evaluator can watch the agent work:
- a stage rail running from intake through settlement;
- a rule grid that fills in live;
- extracted fields with confidence;
- the FX line;
- checker meters;
- tool output and LLM token/latency stats.

This goes in the inbox `AgentActivity` panel and on the `/runs/[id]` page, which now updates in realtime.

**Before editing:** load the `frontend-design` skill and re-read `frontend/DESIGN.md` in full (it changes often). Use ink-on-marble tokens only, iris only for chart strokes and link hover, 1px hairlines, no shadows, and restrained motion.

## Files to Modify/Create

- `frontend/src/lib/types.ts`:
  - extend `RealtimeEventType` (lines 334-339) with `"pipeline.stage" | "agent.rule" | "agent.llm"`;
  - add `RuleOutcome`, `PipelineStageStatus`, `PipelineStagePayload`, `RuleEventPayload`, `LlmCallPayload`, `ExtractedFieldPayload`, `FxPayload` and `CheckerAnswerPayload` (shapes in `03-design.md`);
  - add `pipeline_stages` to `InboxEmailDetail` and `PaymentRunStatus`.
- `frontend/src/lib/runEvents.ts`:
  - add the selectors `collectStages(events, persisted)`, `collectRules(events)`, `latestExtraction(events)`, `latestFx(events)`, `latestChecker(events)`, `collectLlmCalls(events)` (with totals: calls, input/output tokens, total ms) and `agentPhase(events)` (current phase: `intake | classify | extract | rules | checker | settle | done`);
  - make `collectToolRuns` keep `summary`.
- `frontend/src/lib/useRunChannel.ts` (new): wraps `useInboxChannel` and filters events by `run_id`. Returns `{events, thinking, state}`.
- `frontend/src/components/runs/StageRail.tsx` (new): a horizontal phase rail. Done phases are filled ink, the active phase gets an outline pulse, pending phases are muted. Show durations under each phase when known.
- `frontend/src/components/runs/RuleGrid.tsx` (new): a 16-cell grid (R1-R16 from `RULE_NAMES`). Cells fill as `agent.rule` events arrive. Outcome is shown by fill or outline plus copy (pass/flag/review/hold), never by color hue. Hover or focus shows `detail`.
- `frontend/src/components/runs/ExtractedFields.tsx` (new): a field and value list with a small confidence bar per field, plus the FX line (`1,250.00 EUR → $1,362.40 · rate 1.0899 · ECB 2026-10-17`).
- `frontend/src/components/runs/LlmStats.tsx` (new): a footer reading `N model calls · X in / Y out tokens · Z s`, with an expandable per-call list (node, parent tool, model, tokens, ms).
- `frontend/src/components/inbox/AgentActivity.tsx`: compose `StageRail`, then the todos, then `RuleGrid` (when rules exist), `ExtractedFields`, `CheckerMeters` (reuse from `RunTimeline`, or extract it), the tool rows with an expandable `summary`, the thinking text, then `LlmStats`.
- `frontend/src/app/inbox/page.tsx` (lines 100-140): route `pipeline.stage` events into a `stagesByItem: Record<itemId, RealtimeEvent[]>`, and `agent.rule` / `agent.llm` into `runEvents[runId]` (the same path as today). Pass the stages into `EmailDetail` → `AgentActivity`.
- `frontend/src/app/runs/[id]/page.tsx`:
  - replace the 3s `setInterval` (`ACTIVE_POLL_MS`, lines 13, 103-107) with `useRunChannel(runId)`;
  - merge live and persisted events with `mergeEvents`;
  - refetch `api.runStatus` on terminal steps;
  - fall back to polling only when the channel `state !== "live"`.
- `frontend/src/components/runs/RunTimeline.tsx`:
  - build the rules node from `collectRules(events)` while the decision is still `null`, and keep `decision.rule_results` once it exists;
  - add pipeline-stage nodes (malware scan, guardrail) from `pipeline_stages` instead of the current synthesized "malware scan" node;
  - add an FX node from `fx_converted`.
- `frontend/src/lib/labels.ts`: add `STAGE_LABELS`, `PHASE_LABELS` and `RULE_OUTCOME_LABELS`.

## Implementation Guidelines

```ts
// lib/runEvents.ts (orientative)
export function collectRules(events: RealtimeEvent[]): RuleEventPayload[] {
  const byCode = new Map<string, RuleEventPayload>();
  for (const event of events) {
    if (event.type === "agent.rule") byCode.set(String(event.payload.code), event.payload as RuleEventPayload);
  }
  return [...byCode.values()];
}

export function collectLlmCalls(events: RealtimeEvent[]) {
  const calls = events.filter((e) => e.type === "agent.llm").map((e) => e.payload as LlmCallPayload);
  return {
    calls,
    inputTokens: sum(calls, (c) => c.input_tokens),
    outputTokens: sum(calls, (c) => c.output_tokens),
    totalMs: sum(calls, (c) => c.duration_ms),
  };
}
```

```ts
// lib/useRunChannel.ts (orientative)
export function useRunChannel(runId: string) {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const state = useInboxChannel((event) => {
    if (event.run_id !== runId) return;
    setEvents((current) => withEvent(current, event));   // reuse the dedup used by inbox/page.tsx:60-63
  });
  return { events, state };
}
```

- Check `useInboxChannel`'s actual signature (`lib/useInboxChannel.ts`) and adapt; it may take an `onEvent` callback.
- Move `withEvent` from `inbox/page.tsx` into `lib/runEvents.ts` so both pages share it.
- **Dedup of events with `sequence === null`** (`pipeline.stage`): key on `${type}:${step}:${payload.status}:${created_at}`.
- **Motion:** at most a 150-200ms opacity/translate on new rule cells and tool rows. Honor `prefers-reduced-motion`.
- **Copy:** English, no em-dashes in UI copy, no invented numbers. Show only values that came from events.

## Dependencies

- Module 05: event types and payloads.
- Existing `useInboxChannel`, `mergeEvents` and `api.runStatus`.

## Integration Notes

- Field names must match the backend payloads in `03-design.md` exactly.
- `/runs/[id]` must still render a completed run with **no** live events, from persisted `runStatus.events` and `pipeline_stages`.
