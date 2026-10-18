"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { QUIET_BUTTON_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatToolDuration } from "@/lib/format";
import { TODO_STATUS_LABELS } from "@/lib/labels";
import { collectToolRuns, latestSummary, latestTodos, mergeEvents, type ToolRun } from "@/lib/runEvents";
import type { AgentTodo, AgentTodoStatus, PaymentRunEvent, RealtimeEvent } from "@/lib/types";

const THINKING_VISIBLE_CHARS = 160;

const TODO_ROW_CLASSES: Record<AgentTodoStatus, string> = {
  pending: "text-quiet",
  in_progress: "bg-accent-wash text-ink",
  completed: "text-muted",
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
        <p className="text-muted">Plan completed in {toolRuns.length} steps</p>
        <button type="button" onClick={() => setIsExpanded(true)} className={QUIET_BUTTON_CLASS}>
          View details
        </button>
      </section>
    );
  }
  return (
    <section aria-label="Agent activity" className="flex flex-col gap-4 border-t border-line pt-4">
      {todos.length > 0 && <PlanChecklist todos={todos} />}
      <ol aria-live="polite" aria-label="Agent steps" className="flex flex-col gap-1">
        {toolRuns.map((toolRun) => (
          <ToolRunRow key={toolRun.callId} toolRun={toolRun} />
        ))}
      </ol>
      {isRunning && visibleThinking && (
        <p className="text-sm text-muted">Thinking: {visibleThinking}</p>
      )}
      {!isRunning && (
        <div className="flex flex-col gap-2">
          {summary && (
            <p className="text-sm text-nav-ink">
              <span className="text-muted">Agent summary: </span>
              {summary}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className={QUIET_BUTTON_CLASS}
            >
              Hide details
            </button>
            <Link
              href={`/runs/${runId}`}
              className="rounded text-sm font-normal text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
            >
              Open full execution ›
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function PlanChecklist({ todos }: { todos: AgentTodo[] }) {
  return (
    <ul aria-label="Agent plan" className="flex flex-col gap-1">
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
          <span className="shrink-0 text-xs text-muted">{formatToolDuration(toolRun.durationMs)}</span>
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
