"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DecisionCard } from "@/components/bills/DecisionCard";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { MoneyWithUsd } from "@/components/money/MoneyWithUsd";
import { RunHeader } from "@/components/runs/RunHeader";
import { RunTimeline } from "@/components/runs/RunTimeline";
import { CARD_CLASS, EYEBROW_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import { formatRate, formatShortDate, isForeignCurrency } from "@/lib/format";
import { FX_SOURCE_LABELS } from "@/lib/labels";
import type { BillDecisionView, PaymentRunStatus, RunListItemView } from "@/lib/types";

const ACTIVE_POLL_MS = 3000;

export default function RunSummaryPage() {
  const { id: runId } = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunListItemView | null>(null);
  const [runStatus, setRunStatus] = useState<PaymentRunStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const isRunning = runStatus?.status === "pending" || runStatus?.status === "running";

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
        setLoadError("This execution could not be loaded.");
      });
    return () => {
      isCancelled = true;
    };
  }, [router, runId, refreshCount]);

  useEffect(() => {
    if (!isRunning) return;
    const pollTimer = setInterval(() => setRefreshCount((count) => count + 1), ACTIVE_POLL_MS);
    return () => clearInterval(pollTimer);
  }, [isRunning]);

  return (
    <ConsoleShell>
      <ConsoleTopBar title="Execution" caption="Business summary of one agent run" />
      <main className="flex w-full max-w-4xl flex-1 flex-col gap-8 px-4 py-6 md:px-8">
        <RunHeader
          run={run}
          runId={runId}
          links={[
            { href: `/runs/${runId}/trace`, label: "View full LLM trace ›" },
            { href: "/ledger", label: "Back to ledger" },
          ]}
        />
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {loadError}
          </p>
        )}
        {runStatus === null && !loadError && <div aria-hidden className="h-48 animate-pulse rounded bg-sunken" />}
        {runStatus && (
          <>
            <RunTimeline events={runStatus.events} isRunning={isRunning} />
            {runStatus.decision && (
              <>
                <section aria-labelledby="decision-title" className={`${CARD_CLASS} flex flex-col gap-4 p-6`}>
                  <h2 id="decision-title" className={EYEBROW_CLASS}>
                    Decision
                  </h2>
                  <DecisionCard
                    decision={runStatus.decision}
                    onResolved={() => setRefreshCount((count) => count + 1)}
                    onSelectEmail={() => router.push("/inbox")}
                  />
                </section>
                <ExchangeRatePanel decision={runStatus.decision} />
              </>
            )}
            <EvidenceSection evidence={runStatus.evidence} />
          </>
        )}
      </main>
    </ConsoleShell>
  );
}

function ExchangeRatePanel({ decision }: { decision: BillDecisionView }) {
  const isConverted = isForeignCurrency(decision.currency) && decision.fx_usd_per_unit !== null;
  if (!isConverted || !decision.currency || !decision.fx_usd_per_unit) return null;
  return (
    <section aria-labelledby="fx-title" className={`${CARD_CLASS} flex flex-col gap-3 p-6`}>
      <h2 id="fx-title" className={EYEBROW_CLASS}>
        Exchange rate
      </h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted">Amount</dt>
          <dd className="mt-1">
            <MoneyWithUsd amount={decision.amount} currency={decision.currency} amountUsd={decision.amount_usd} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Rate</dt>
          <dd className="mt-1 text-ink tabular-nums">{formatRate(decision.fx_usd_per_unit, decision.currency)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Rate date</dt>
          <dd className="mt-1 text-ink">{decision.fx_rate_date ? formatShortDate(decision.fx_rate_date) : "Unknown"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Source</dt>
          <dd className="mt-1 text-ink">{decision.fx_source ? FX_SOURCE_LABELS[decision.fx_source] : "Unknown"}</dd>
        </div>
      </dl>
    </section>
  );
}
