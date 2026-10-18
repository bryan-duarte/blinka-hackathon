import type {
  AgentTodo,
  AgentTodoStatus,
  CheckerPayload,
  ExtractionPayload,
  FxPayload,
  LlmCallPayload,
  PaymentRunEvent,
  PipelineStage,
  PipelineStageRecord,
  PipelineStageStatus,
  RealtimeEvent,
  RuleEventPayload,
} from "./types";

export const TERMINAL_RUN_STEPS: ReadonlySet<string> = new Set([
  "completed",
  "failed",
  "cancelled",
  "decided",
  "not_a_bill",
  "extraction_failed",
]);

const TODOS_UPDATED_STEP = "todos_updated";
const TOOL_STARTED_STEP = "tool_started";
const TOOL_FINISHED_STEP = "tool_finished";
const AGENT_SUMMARY_STEP = "agent_summary";
const RULE_EVALUATED_STEP = "rule_evaluated";
const EXTRACTED_STEP = "extracted";
const FX_CONVERTED_STEP = "fx_converted";
const CHECKER_ANSWERED_STEP = "checker_answered";
const LLM_CALL_STEP = "llm_call";
const PIPELINE_STAGE_TYPE = "pipeline.stage";
const STARTED_STAGE_STATUS: PipelineStageStatus = "started";

export const PIPELINE_STAGE_ORDER: PipelineStage[] = [
  "queued",
  "fetch",
  "malware_scan",
  "guardrail",
  "dedup",
  "handoff",
];
const TODO_STATUSES: ReadonlySet<string> = new Set<AgentTodoStatus>([
  "pending",
  "in_progress",
  "completed",
]);

export type ActivityEvent = {
  sequence: number;
  step: string;
  payload: Record<string, unknown>;
  createdAt: string;
};

export type LlmCallTotals = {
  calls: LlmCallPayload[];
  inputTokens: number;
  outputTokens: number;
  totalMs: number;
};

export type ToolRunStatus = "running" | "ok" | "error";

export type ToolRun = {
  callId: string;
  tool: string | null;
  message: string;
  status: ToolRunStatus;
  durationMs: number | null;
  summary: string | null;
};

export function persistedActivity(events: PaymentRunEvent[]): ActivityEvent[] {
  return events.map((event) => ({
    sequence: event.id,
    step: event.step,
    payload: event.payload,
    createdAt: event.created_at,
  }));
}

export function withEvent(existingEvents: RealtimeEvent[] = [], event: RealtimeEvent): RealtimeEvent[] {
  const eventKey = realtimeEventKey(event);
  const isDuplicate = existingEvents.some((existing) => realtimeEventKey(existing) === eventKey);
  return isDuplicate ? existingEvents : [...existingEvents, event];
}

export function mergeEvents(persisted: PaymentRunEvent[], live: RealtimeEvent[]): ActivityEvent[] {
  const eventsBySequence = new Map<number, ActivityEvent>();
  for (const event of persistedActivity(persisted)) {
    eventsBySequence.set(event.sequence, event);
  }
  for (const event of live) {
    const isPersisted = event.sequence !== null && eventsBySequence.has(event.sequence);
    if (event.sequence === null || isPersisted) continue;
    eventsBySequence.set(event.sequence, {
      sequence: event.sequence,
      step: event.step,
      payload: event.payload,
      createdAt: event.created_at,
    });
  }
  return [...eventsBySequence.values()].sort((first, second) => first.sequence - second.sequence);
}

export function latestTodos(events: ActivityEvent[]): AgentTodo[] {
  const latestTodoEvent = events.findLast((event) => event.step === TODOS_UPDATED_STEP);
  const rawTodos = latestTodoEvent?.payload.todos;
  if (!Array.isArray(rawTodos)) return [];
  return rawTodos.filter(isAgentTodo);
}

export function collectToolRuns(events: ActivityEvent[], isRunning: boolean): ToolRun[] {
  const toolRunsByCallId = new Map<string, ToolRun>();
  for (const event of events) {
    const { call_id: callId, message, tool } = event.payload;
    if (typeof callId !== "string" || typeof message !== "string") continue;
    const toolName = typeof tool === "string" ? tool : null;
    if (event.step === TOOL_STARTED_STEP && !toolRunsByCallId.has(callId)) {
      toolRunsByCallId.set(callId, {
        callId,
        tool: toolName,
        message,
        status: "running",
        durationMs: null,
        summary: null,
      });
    }
    if (event.step === TOOL_FINISHED_STEP) {
      const { duration_ms: durationMs, summary } = event.payload;
      toolRunsByCallId.set(callId, {
        callId,
        tool: toolName,
        message,
        status: event.payload.ok === false ? "error" : "ok",
        durationMs: typeof durationMs === "number" ? durationMs : null,
        summary: typeof summary === "string" && summary ? summary : null,
      });
    }
  }
  const toolRuns = [...toolRunsByCallId.values()];
  if (isRunning) return toolRuns;
  return toolRuns.map((toolRun) =>
    toolRun.status === "running" ? { ...toolRun, status: "error" } : toolRun,
  );
}

export function latestSummary(events: ActivityEvent[]): string | null {
  const summaryText = events.findLast((event) => event.step === AGENT_SUMMARY_STEP)?.payload.text;
  return typeof summaryText === "string" && summaryText ? summaryText : null;
}

export function collectRules(events: ActivityEvent[]): RuleEventPayload[] {
  const rulesByCode = new Map<string, RuleEventPayload>();
  for (const event of events) {
    if (event.step === RULE_EVALUATED_STEP && isRuleEventPayload(event.payload)) {
      rulesByCode.set(event.payload.code, event.payload);
    }
  }
  return [...rulesByCode.values()];
}

export function latestExtraction(events: ActivityEvent[]): ExtractionPayload | null {
  const payload = latestPayload(events, EXTRACTED_STEP);
  return payload && Array.isArray(payload.fields) && typeof payload.method === "string"
    ? (payload as ExtractionPayload)
    : null;
}

export function latestFx(events: ActivityEvent[]): FxPayload | null {
  const payload = latestPayload(events, FX_CONVERTED_STEP);
  return payload && typeof payload.amount_usd === "string" ? (payload as FxPayload) : null;
}

export function latestChecker(events: ActivityEvent[]): CheckerPayload | null {
  const payload = latestPayload(events, CHECKER_ANSWERED_STEP);
  return payload && Array.isArray(payload.answers) ? (payload as CheckerPayload) : null;
}

export function collectLlmCalls(events: ActivityEvent[]): LlmCallTotals {
  const calls = events
    .filter((event) => event.step === LLM_CALL_STEP && isLlmCallPayload(event.payload))
    .map((event) => event.payload as LlmCallPayload);
  return {
    calls,
    inputTokens: calls.reduce((total, call) => total + call.input_tokens, 0),
    outputTokens: calls.reduce((total, call) => total + call.output_tokens, 0),
    totalMs: calls.reduce((total, call) => total + call.duration_ms, 0),
  };
}

export function collectStages(
  persistedStages: PipelineStageRecord[],
  liveStageEvents: RealtimeEvent[],
): PipelineStageRecord[] {
  const stagesByName = new Map<PipelineStage, PipelineStageRecord>();
  const liveStages = liveStageEvents
    .filter((event) => event.type === PIPELINE_STAGE_TYPE)
    .map((event) => event.payload)
    .filter(isPipelineStageRecord);
  for (const stage of [...persistedStages, ...liveStages]) {
    const known = stagesByName.get(stage.stage);
    const isRegression = known !== undefined && known.status !== STARTED_STAGE_STATUS && stage.status === STARTED_STAGE_STATUS;
    if (!isRegression) stagesByName.set(stage.stage, stage);
  }
  return PIPELINE_STAGE_ORDER.flatMap((stageName) => stagesByName.get(stageName) ?? []);
}

function latestPayload(events: ActivityEvent[], step: string): Record<string, unknown> | null {
  return events.findLast((event) => event.step === step)?.payload ?? null;
}

function realtimeEventKey(event: RealtimeEvent): string {
  if (event.sequence !== null) return `sequence:${event.sequence}`;
  return `${event.type}:${event.step}:${String(event.payload.status)}:${event.created_at}`;
}

function isRuleEventPayload(payload: Record<string, unknown>): payload is RuleEventPayload {
  return typeof payload.code === "string" && typeof payload.outcome === "string" && typeof payload.detail === "string";
}

function isLlmCallPayload(payload: Record<string, unknown>): boolean {
  return (
    typeof payload.input_tokens === "number" &&
    typeof payload.output_tokens === "number" &&
    typeof payload.duration_ms === "number"
  );
}

function isPipelineStageRecord(payload: Record<string, unknown>): payload is PipelineStageRecord {
  return (
    PIPELINE_STAGE_ORDER.includes(payload.stage as PipelineStage) && typeof payload.status === "string"
  );
}

function isAgentTodo(candidate: unknown): candidate is AgentTodo {
  if (!candidate || typeof candidate !== "object") return false;
  const { content, status } = candidate as Record<string, unknown>;
  return typeof content === "string" && typeof status === "string" && TODO_STATUSES.has(status);
}
