"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConsoleShell } from "@/components/console/ConsoleShell";
import { RawTracePanel } from "@/components/runs/RawTracePanel";
import { RunTimeline, policyRules } from "@/components/runs/RunTimeline";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import { formatMoney, formatToolDuration } from "@/lib/format";
import { TERMINAL_RUN_STEPS, collectToolRuns, mergeEvents } from "@/lib/runEvents";
import type { BillStatus, PaymentRunStatus, RunListItemView, RunTraceView } from "@/lib/types";
import { useRunChannel } from "@/lib/useRunChannel";

const OFFLINE_POLL_MS = 3000;
const COPY_FEEDBACK_MS = 1500;
const SHORT_RUN_ID_LENGTH = 8;

const HEADER_BUTTON_CLASS =
  "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-full border border-ink bg-transparent px-4 text-[13px] leading-none font-medium whitespace-nowrap text-ink hover:bg-ink hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";
const STATUS_CLASS = "inline-flex h-6 items-center gap-1.5 justify-self-start rounded-full px-2.5 text-xs leading-none font-medium whitespace-nowrap";

type StatusTone = "filled" | "outline" | "muted";

const STATUS_TONES: Record<StatusTone, string> = {
  filled: "bg-ink text-white",
  outline: "border border-ink bg-white text-ink before:size-1.5 before:rounded-full before:bg-ink before:content-['']",
  muted: "bg-ash text-ink",
};

const BILL_STATUS_PILLS: Record<BillStatus, { label: string; tone: StatusTone }> = {
  paid: { label: "Paid", tone: "filled" },
  review: { label: "Escalated to a person", tone: "outline" },
  approving: { label: "Approved, paying", tone: "outline" },
  deciding: { label: "Deciding", tone: "outline" },
  held: { label: "Held", tone: "muted" },
  rejected: { label: "Rejected by a person", tone: "muted" },
  duplicate: { label: "Duplicate", tone: "muted" },
};

const BILL_STATUS_HEADLINES: Record<BillStatus, string> = {
  paid: "Read, checked, and paid.",
  review: "Read, checked, and sent to you.",
  approving: "Read, checked, and approved by a person.",
  deciding: "Read, and still being checked.",
  held: "Read, checked, and held.",
  rejected: "Read, checked, and rejected by a person.",
  duplicate: "Read, and held as a duplicate.",
};

function statusPill(runStatus: PaymentRunStatus | null, isRunning: boolean): { label: string; tone: StatusTone } | null {
  if (!runStatus) return null;
  if (isRunning) return { label: "Running", tone: "outline" };
  if (runStatus.decision) return BILL_STATUS_PILLS[runStatus.decision.status];
  if (runStatus.status === "failed") return { label: "Failed", tone: "muted" };
  if (runStatus.is_bill === false) return { label: "Not a bill", tone: "muted" };
  return { label: "No decision", tone: "muted" };
}

function headline(run: RunListItemView | null, runStatus: PaymentRunStatus | null): string {
  const decision = runStatus?.decision;
  if (decision?.payee_name && decision.amount) {
    return `${decision.payee_name}, ${formatMoney(decision.amount, decision.currency)}. ${BILL_STATUS_HEADLINES[decision.status]}`;
  }
  return run?.subject ?? "Agent run";
}

export default function RunSummaryPage() {
  const { id: runId } = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunListItemView | null>(null);
  const [runStatus, setRunStatus] = useState<PaymentRunStatus | null>(null);
  const [trace, setTrace] = useState<RunTraceView | null | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const [isCopied, setIsCopied] = useState(false);
  const runChannel = useRunChannel(runId);
  const isRunning = runStatus?.status === "pending" || runStatus?.status === "running";
  const hasStatus = runStatus !== null;
  const isChannelLive = runChannel.state === "live";
  const terminalEventCount = runChannel.events.filter(
    (event) => event.type === "run.step" && TERMINAL_RUN_STEPS.has(event.step),
  ).length;
  const activity = mergeEvents(runStatus?.events ?? [], runChannel.events);

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    let isCancelled = false;
    Promise.all([api.run(runId), api.runStatus(runId)])
      .then(([listItem, status]) => {
        if (isCancelled) return;
        setRun(listItem);
        setRunStatus(status);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        if (error instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setLoadError("This run could not be loaded.");
      });
    return () => {
      isCancelled = true;
    };
  }, [router, runId, refreshCount, terminalEventCount, isChannelLive]);

  useEffect(() => {
    if (!isRunning || isChannelLive) return;
    const pollTimer = setInterval(() => setRefreshCount((count) => count + 1), OFFLINE_POLL_MS);
    return () => clearInterval(pollTimer);
  }, [isRunning, isChannelLive]);

  useEffect(() => {
    if (!hasStatus || isRunning) return;
    let isCancelled = false;
    api
      .runTrace(runId)
      .then((loadedTrace) => {
        if (!isCancelled) setTrace(loadedTrace);
      })
      .catch(() => {
        if (!isCancelled) setTrace(null);
      });
    return () => {
      isCancelled = true;
    };
  }, [runId, hasStatus, isRunning]);

  async function copyRunId() {
    await navigator.clipboard.writeText(runId);
    setIsCopied(true);
    window.setTimeout(() => setIsCopied(false), COPY_FEEDBACK_MS);
  }

  const pill = statusPill(runStatus, isRunning);
  const decision = runStatus?.decision ?? null;
  const ruleCount = policyRules(decision).length;
  const stepCount = runStatus ? collectToolRuns(activity, isRunning).length : null;

  return (
    <ConsoleShell>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-4 md:px-8">
        <nav aria-label="Breadcrumb" className="text-muted">
          <Link
            href="/runs"
            className="rounded text-ink hover:text-iris hover:underline hover:underline-offset-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Agent runs
          </Link>{" "}
          / <span aria-current="page">Run {runId.slice(0, SHORT_RUN_ID_LENGTH)}</span>
        </nav>
        <div className="flex flex-wrap gap-2">
          {decision?.can_approve && (
            <Link href="/bills" className={HEADER_BUTTON_CLASS}>
              Review the bill
            </Link>
          )}
          <button type="button" onClick={copyRunId} className={HEADER_BUTTON_CLASS}>
            {isCopied ? "Copied" : "Copy run ID"}
          </button>
        </div>
      </header>

      <main className="flex w-full max-w-[1120px] flex-col gap-7 px-4 pt-8 pb-10 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-4">
          <div className="grid gap-2">
            {pill ? (
              <span className={`${STATUS_CLASS} ${STATUS_TONES[pill.tone]}`}>{pill.label}</span>
            ) : (
              <span aria-hidden className="h-6 w-32 animate-pulse rounded-full bg-sunken" />
            )}
            <h1 className="max-w-[720px] font-serif text-[30px] leading-[1.15] md:text-[38px]">
              {hasStatus || run ? headline(run, runStatus) : "Loading run"}
            </h1>
          </div>
          <dl className="flex gap-8">
            <RunStat label="Duration" value={run?.duration_ms != null ? formatToolDuration(run.duration_ms) : "..."} />
            <RunStat label="Steps" value={stepCount !== null ? String(stepCount) : "..."} />
            {ruleCount > 0 && <RunStat label="Rules" value={String(ruleCount)} />}
          </dl>
        </div>

        {loadError && (
          <p role="alert" className="text-danger">
            <span aria-hidden>✕ </span>
            {loadError}
          </p>
        )}
        {run?.error && (
          <p role="alert" className="text-danger">
            <span aria-hidden>✕ </span>
            {run.error}
          </p>
        )}
        {runStatus === null && !loadError && (
          <div aria-hidden className="flex flex-col gap-4">
            {[0, 1, 2, 3, 4].map((row) => (
              <div key={row} className="flex items-center gap-4">
                <span className="size-7 animate-pulse rounded-full bg-sunken" />
                <span className="h-3.5 w-2/3 animate-pulse rounded bg-sunken" />
              </div>
            ))}
          </div>
        )}
        {runStatus && <RunTimeline run={run} runStatus={runStatus} activity={activity} isRunning={isRunning} />}
      </main>

      <RawTracePanel trace={loadError ? null : isRunning ? undefined : trace} />
    </ConsoleShell>
  );
}

function RunStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-serif text-[26px] tabular-nums">{value}</dd>
    </div>
  );
}
