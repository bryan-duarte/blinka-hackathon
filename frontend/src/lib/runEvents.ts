import type { AgentTodo, AgentTodoStatus, PaymentRunEvent, RealtimeEvent } from "./types";

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
const TODO_STATUSES: ReadonlySet<string> = new Set<AgentTodoStatus>([
  "pending",
  "in_progress",
  "completed",
]);

export type ActivityEvent = {
  sequence: number;
  step: string;
  payload: Record<string, unknown>;
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
  return events.map((event) => ({ sequence: event.id, step: event.step, payload: event.payload }));
}

export function mergeEvents(persisted: PaymentRunEvent[], live: RealtimeEvent[]): ActivityEvent[] {
  const eventsBySequence = new Map<number, ActivityEvent>();
  for (const event of persistedActivity(persisted)) {
    eventsBySequence.set(event.sequence, event);
  }
  for (const event of live) {
    if (event.sequence === null) continue;
    eventsBySequence.set(event.sequence, {
      sequence: event.sequence,
      step: event.step,
      payload: event.payload,
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

function isAgentTodo(candidate: unknown): candidate is AgentTodo {
  if (!candidate || typeof candidate !== "object") return false;
  const { content, status } = candidate as Record<string, unknown>;
  return typeof content === "string" && typeof status === "string" && TODO_STATUSES.has(status);
}
