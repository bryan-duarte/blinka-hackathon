"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckerMeters } from "@/components/runs/CheckerMeters";
import { ExtractedFields } from "@/components/runs/ExtractedFields";
import { LlmStats } from "@/components/runs/LlmStats";
import { RuleGrid } from "@/components/runs/RuleGrid";
import { StageRail } from "@/components/runs/StageRail";
import { api } from "@/lib/api";
import { formatToolDuration } from "@/lib/format";
import { POLICY_RULE_IDS, TODO_STATUS_LABELS } from "@/lib/labels";
import {
  type ActivityEvent,
  collectLlmCalls,
  collectRules,
  collectToolRuns,
  latestChecker,
  latestExtraction,
  latestFx,
  latestSummary,
  latestTodos,
  mergeEvents,
  type ToolRun,
} from "@/lib/runEvents";
import type { AgentTodo, AgentTodoStatus, PaymentRunEvent, PipelineStageRecord, RealtimeEvent } from "@/lib/types";

const THINKING_VISIBLE_CHARS = 220;
const CLOCK_TICK_MS = 1000;

const TODO_ROW_CLASSES: Record<AgentTodoStatus, string> = {
  pending: "text-quiet",
  in_progress: "bg-sunken text-ink",
  completed: "text-muted",
};

type AgentActivityProps = {
  runId: string;
  liveEvents: RealtimeEvent[];
  stages: PipelineStageRecord[];
  thinking: string;
  isRunning: boolean;
  refreshKey: number;
};

export function AgentActivity({
  runId,
  liveEvents,
  stages,
  thinking,
  isRunning,
  refreshKey,
}: AgentActivityProps) {
  const [persistedEvents, setPersistedEvents] = useState<PaymentRunEvent[]>([]);

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
  const rules = collectRules(activityEvents);
  const extraction = latestExtraction(activityEvents);
  const fx = latestFx(activityEvents);
  const checker = latestChecker(activityEvents);
  const llmTotals = collectLlmCalls(activityEvents);
  const hasAgentActivity = todos.length > 0 || toolRuns.length > 0;
  const currentToolRun = isRunning ? toolRuns.findLast((toolRun) => toolRun.status === "running") : undefined;
  const passedRuleCount = rules.filter((rule) => rule.outcome === "pass").length;

  return (
    <section aria-label="Agent activity" className="flex flex-col gap-6">
      <RunStats
        runId={runId}
        isRunning={isRunning}
        startedAt={runStartedAt(stages, activityEvents)}
        finishedAt={isRunning ? null : (activityEvents.at(-1)?.createdAt ?? null)}
        stepCount={toolRuns.length}
        ruleSummary={rules.length > 0 ? `${passedRuleCount} / ${POLICY_RULE_IDS.length}` : null}
        modelCallCount={llmTotals.calls.length}
      />
      <StageRail stages={stages} toolRuns={toolRuns} />
      {isRunning && <LiveTicker currentToolRun={currentToolRun} thinking={thinking} />}
      {!hasAgentActivity && isRunning && <StepsSkeleton />}
      {todos.length > 0 && <PlanChecklist todos={todos} />}
      {toolRuns.length > 0 && (
        <ol aria-label="Agent steps" className="flex flex-col">
          {toolRuns.map((toolRun, position) => (
            <ToolRunRow key={toolRun.callId} toolRun={toolRun} position={position + 1} />
          ))}
        </ol>
      )}
      {extraction && <ExtractedFields extraction={extraction} fx={fx} />}
      {rules.length > 0 && <RuleGrid rules={rules} />}
      {checker && checker.answers.length > 0 && (
        <section aria-label="Second review" className="flex flex-col gap-1">
          <p className="text-sm font-medium">Second review</p>
          <CheckerMeters
            answers={checker.answers.map((answer) => ({
              questionId: answer.question,
              probability: answer.probability,
            }))}
          />
        </section>
      )}
      {!isRunning && summary && (
        <p className="rounded-lg bg-sunken px-4 py-3.5 text-sm leading-[1.5] text-ink">
          <span className="text-muted">Agent summary: </span>
          {summary}
        </p>
      )}
      <LlmStats totals={llmTotals} />
    </section>
  );
}

function runStartedAt(stages: PipelineStageRecord[], events: ActivityEvent[]): string | null {
  const timestamps = [...stages.map((stage) => stage.at), events[0]?.createdAt].filter(
    (timestamp): timestamp is string => typeof timestamp === "string",
  );
  if (timestamps.length === 0) return null;
  return timestamps.reduce((earliest, timestamp) => (timestamp < earliest ? timestamp : earliest));
}

function useNow(isTicking: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!isTicking) return;
    const clock = setInterval(() => setNow(Date.now()), CLOCK_TICK_MS);
    return () => clearInterval(clock);
  }, [isTicking]);
  return now;
}

type RunStatsProps = {
  runId: string;
  isRunning: boolean;
  startedAt: string | null;
  finishedAt: string | null;
  stepCount: number;
  ruleSummary: string | null;
  modelCallCount: number;
};

function RunStats({ runId, isRunning, startedAt, finishedAt, stepCount, ruleSummary, modelCallCount }: RunStatsProps) {
  const now = useNow(isRunning);
  const endMs = isRunning ? now : finishedAt ? Date.parse(finishedAt) : null;
  const elapsedMs = startedAt && endMs !== null ? Math.max(0, endMs - Date.parse(startedAt)) : null;
  return (
    <dl className="flex flex-wrap items-end gap-x-8 gap-y-3 border-y border-line py-3.5">
      <RunStat label={isRunning ? "Elapsed" : "Duration"}>
        {elapsedMs !== null ? formatToolDuration(elapsedMs) : "…"}
      </RunStat>
      <RunStat label="Steps">{stepCount}</RunStat>
      {ruleSummary && <RunStat label="Rules passed">{ruleSummary}</RunStat>}
      {modelCallCount > 0 && <RunStat label="Model calls">{modelCallCount}</RunStat>}
      <Link
        href={`/runs/${runId}`}
        className="ml-auto self-center rounded text-[13px] text-ink hover:text-accent-hover hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        View execution ›
      </Link>
    </dl>
  );
}

function RunStat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-base tabular-nums">{children}</dd>
    </div>
  );
}

function LiveTicker({ currentToolRun, thinking }: { currentToolRun: ToolRun | undefined; thinking: string }) {
  const visibleThinking = thinking.slice(-THINKING_VISIBLE_CHARS);
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-ink p-4">
      <p className="flex items-center gap-2 text-sm" aria-live="polite">
        <span aria-hidden className="size-2 shrink-0 animate-pulse rounded-full bg-ink" />
        <span className="font-medium">Live</span>
        <span className="min-w-0 truncate text-muted">
          {currentToolRun ? currentToolRun.message : "Waiting for the next step"}
        </span>
      </p>
      {visibleThinking && (
        <p className="font-mono text-xs leading-[1.6] tracking-normal break-words text-muted">
          {visibleThinking}
          <span aria-hidden className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-ink align-middle" />
        </p>
      )}
    </div>
  );
}

function PlanChecklist({ todos }: { todos: AgentTodo[] }) {
  return (
    <ul aria-label="Agent plan" className="flex flex-col gap-1">
      {todos.map((todo, index) => (
        <li
          key={`${index}-${todo.content}`}
          className={`flex animate-enter items-center gap-2 rounded px-2 py-1 text-sm ${TODO_ROW_CLASSES[todo.status]}`}
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
      className={`size-4 shrink-0 text-ink ${status === "in_progress" ? "animate-pulse" : ""}`}
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

function ToolRunRow({ toolRun, position }: { toolRun: ToolRun; position: number }) {
  const isRunning = toolRun.status === "running";
  const isError = toolRun.status === "error";
  const summaryPreview = toolRun.summary?.split("\n", 1)[0] ?? null;
  const heading = (
    <span className="grid grid-cols-[1.75rem_minmax(0,1fr)_auto] items-baseline gap-3">
      <span className={`font-mono text-xs tracking-normal tabular-nums ${isRunning ? "text-ink" : "text-muted"}`}>
        {String(position).padStart(2, "0")}
      </span>
      <span className="flex min-w-0 flex-col gap-1">
        <span className={`text-sm ${isError ? "text-danger" : "text-ink"} ${isRunning ? "font-medium" : ""}`}>
          {isError && <span aria-hidden>✕ </span>}
          {toolRun.message}
        </span>
        {summaryPreview && (
          <span className="self-start truncate rounded bg-sunken px-2 py-1 font-mono text-xs tracking-normal text-ink max-w-full">
            {summaryPreview}
          </span>
        )}
      </span>
      <span className="font-mono text-xs tracking-normal text-muted tabular-nums">
        {isRunning ? "working" : toolRun.durationMs !== null ? formatToolDuration(toolRun.durationMs) : ""}
      </span>
    </span>
  );
  return (
    <li
      className={`flex animate-enter flex-col gap-2 border-t border-line py-3 first:border-t-0 ${isRunning ? "-mx-3 rounded-lg border-t-transparent bg-sunken px-3" : ""}`}
    >
      {toolRun.summary && toolRun.summary !== summaryPreview ? (
        <details>
          <summary className="cursor-pointer list-none rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink [&::-webkit-details-marker]:hidden">
            {heading}
          </summary>
          <pre className="mt-2 ml-10 max-h-48 overflow-auto rounded border border-line bg-panel p-2 font-mono text-xs tracking-normal whitespace-pre-wrap text-ink">
            {toolRun.summary}
          </pre>
        </details>
      ) : (
        heading
      )}
      {isRunning && <div aria-hidden className="ml-10 h-0.5 animate-pulse rounded bg-ink/30" />}
    </li>
  );
}

function StepsSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-3">
      {[0, 1, 2].map((row) => (
        <div key={row} className="grid grid-cols-[1.75rem_minmax(0,1fr)_3rem] gap-3">
          <div className="h-3 animate-pulse rounded bg-sunken" />
          <div className="h-3.5 animate-pulse rounded bg-sunken" style={{ width: `${70 - row * 15}%` }} />
          <div className="h-3 animate-pulse rounded bg-sunken" />
        </div>
      ))}
    </div>
  );
}
