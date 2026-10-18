"use client";

import { useEffect, useState } from "react";
import { QUIET_BUTTON_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { TODO_STATUS_LABELS } from "@/lib/labels";
import type { AgentTodo, AgentTodoStatus, PaymentRunEvent, RealtimeEvent } from "@/lib/types";

const TODOS_UPDATED_STEP = "todos_updated";
const TOOL_STARTED_STEP = "tool_started";
const TOOL_FINISHED_STEP = "tool_finished";
const AGENT_SUMMARY_STEP = "agent_summary";
const THINKING_VISIBLE_CHARS = 160;
const MS_PER_SECOND = 1000;
const TODO_STATUSES: ReadonlySet<string> = new Set<AgentTodoStatus>([
  "pending",
  "in_progress",
  "completed",
]);

const TODO_ROW_CLASSES: Record<AgentTodoStatus, string> = {
  pending: "text-quiet",
  in_progress: "bg-accent-wash text-ink",
  completed: "text-muted",
};

const durationFormatter = new Intl.NumberFormat("es-CL", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

type ActivityEvent = {
  sequence: number;
  step: string;
  payload: Record<string, unknown>;
};

type ToolRunStatus = "running" | "ok" | "error";

type ToolRun = {
  callId: string;
  message: string;
  status: ToolRunStatus;
  durationMs: number | null;
};

type AgentActivityProps = {
  runId: string;
  liveEvents: RealtimeEvent[];
  thinking: string;
  isRunning: boolean;
  refreshKey: number;
};

export function AgentActivity({
  runId,
  liveEvents,
  thinking,
  isRunning,
  refreshKey,
}: AgentActivityProps) {
  const [persistedEvents, setPersistedEvents] = useState<PaymentRunEvent[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    let isCancelled = false;
    api
      .runStatus(runId)
      .then((run) => {
        if (!isCancelled) setPersistedEvents(run.events);
      })
      .catch(() => undefined);
    return () => {
      isCancelled = true;
    };
  }, [runId, refreshKey]);

  const activityEvents = mergeEvents(persistedEvents, liveEvents);
  const todos = latestTodos(activityEvents);
  const toolRuns = collectToolRuns(activityEvents, isRunning);
  const summary = latestSummary(activityEvents);
  const hasAgentActivity = todos.length > 0 || toolRuns.length > 0;
  const visibleThinking = thinking.slice(-THINKING_VISIBLE_CHARS);

  if (!hasAgentActivity) {
    return isRunning ? <ActivitySkeleton /> : null;
  }
  if (!isRunning && !isExpanded) {
    return (
      <section className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-4 text-sm">
        <p className="text-muted">Plan completado en {toolRuns.length} pasos</p>
        <button type="button" onClick={() => setIsExpanded(true)} className={QUIET_BUTTON_CLASS}>
          Ver detalle
        </button>
      </section>
    );
  }
  return (
    <section aria-label="Actividad del agente" className="flex flex-col gap-4 border-t border-line pt-4">
      {todos.length > 0 && <PlanChecklist todos={todos} />}
      <ol aria-live="polite" aria-label="Pasos del agente" className="flex flex-col gap-1">
        {toolRuns.map((toolRun) => (
          <ToolRunRow key={toolRun.callId} toolRun={toolRun} />
        ))}
      </ol>
      {isRunning && visibleThinking && (
        <p className="text-sm text-muted">Pensando: {visibleThinking}</p>
      )}
      {!isRunning && (
        <div className="flex flex-col gap-2">
          {summary && (
            <p className="text-sm text-nav-ink">
              <span className="text-muted">Resumen del agente: </span>
              {summary}
            </p>
          )}
          <button
            type="button"
            onClick={() => setIsExpanded(false)}
            className={`${QUIET_BUTTON_CLASS} self-start`}
          >
            Ocultar detalle
          </button>
        </div>
      )}
    </section>
  );
}

function PlanChecklist({ todos }: { todos: AgentTodo[] }) {
  return (
    <ul aria-label="Plan del agente" className="flex flex-col gap-1">
      {todos.map((todo, index) => (
        <li
          key={`${index}-${todo.content}`}
          className={`flex items-center gap-2 rounded px-2 py-1 text-sm ${TODO_ROW_CLASSES[todo.status]}`}
        >
          <TodoGlyph status={todo.status} />
          <span className="sr-only">{TODO_STATUS_LABELS[todo.status]}: </span>
          {todo.content}
        </li>
      ))}
    </ul>
  );
}

function TodoGlyph({ status }: { status: AgentTodoStatus }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className="size-4 shrink-0 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <circle cx="8" cy="8" r="6.25" />
      {status === "in_progress" && <path d="M8 1.75a6.25 6.25 0 0 1 0 12.5Z" fill="currentColor" />}
      {status === "completed" && <path d="m5.25 8.25 1.9 1.9 3.6-3.9" strokeLinecap="round" />}
    </svg>
  );
}

function ToolRunRow({ toolRun }: { toolRun: ToolRun }) {
  const isRunning = toolRun.status === "running";
  return (
    <li className="flex flex-col gap-1">
      <p className="flex items-baseline justify-between gap-4 text-sm">
        <span className={toolRun.status === "error" ? "text-danger" : "text-ink"}>
          {toolRun.message}
        </span>
        {toolRun.durationMs !== null && (
          <span className="shrink-0 text-xs text-muted">{formatDuration(toolRun.durationMs)}</span>
        )}
      </p>
      {isRunning && <div aria-hidden className="h-0.5 w-full animate-pulse rounded bg-accent-wash" />}
    </li>
  );
}

function ActivitySkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-2 border-t border-line pt-4">
      <div className="h-3.5 w-1/3 animate-pulse rounded bg-sunken" />
      <div className="h-3.5 w-1/4 animate-pulse rounded bg-sunken" />
    </div>
  );
}

function mergeEvents(persisted: PaymentRunEvent[], live: RealtimeEvent[]): ActivityEvent[] {
  const eventsBySequence = new Map<number, ActivityEvent>();
  for (const event of persisted) {
    eventsBySequence.set(event.id, { sequence: event.id, step: event.step, payload: event.payload });
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

function latestTodos(events: ActivityEvent[]): AgentTodo[] {
  const latestTodoEvent = events.findLast((event) => event.step === TODOS_UPDATED_STEP);
  const rawTodos = latestTodoEvent?.payload.todos;
  if (!Array.isArray(rawTodos)) return [];
  return rawTodos.filter(isAgentTodo);
}

function isAgentTodo(candidate: unknown): candidate is AgentTodo {
  if (!candidate || typeof candidate !== "object") return false;
  const { content, status } = candidate as Record<string, unknown>;
  return typeof content === "string" && typeof status === "string" && TODO_STATUSES.has(status);
}

function collectToolRuns(events: ActivityEvent[], isRunning: boolean): ToolRun[] {
  const toolRunsByCallId = new Map<string, ToolRun>();
  for (const event of events) {
    const callId = event.payload.call_id;
    const message = event.payload.message;
    if (typeof callId !== "string" || typeof message !== "string") continue;
    if (event.step === TOOL_STARTED_STEP && !toolRunsByCallId.has(callId)) {
      toolRunsByCallId.set(callId, { callId, message, status: "running", durationMs: null });
    }
    if (event.step === TOOL_FINISHED_STEP) {
      const durationMs = event.payload.duration_ms;
      toolRunsByCallId.set(callId, {
        callId,
        message,
        status: event.payload.ok === false ? "error" : "ok",
        durationMs: typeof durationMs === "number" ? durationMs : null,
      });
    }
  }
  const toolRuns = [...toolRunsByCallId.values()];
  if (isRunning) return toolRuns;
  return toolRuns.map((toolRun) =>
    toolRun.status === "running" ? { ...toolRun, status: "error" } : toolRun,
  );
}

function latestSummary(events: ActivityEvent[]): string | null {
  const summaryText = events.findLast((event) => event.step === AGENT_SUMMARY_STEP)?.payload.text;
  return typeof summaryText === "string" && summaryText ? summaryText : null;
}

function formatDuration(durationMs: number): string {
  return `${durationFormatter.format(durationMs / MS_PER_SECOND)} s`;
}
