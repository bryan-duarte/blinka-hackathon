import Link from "next/link";
import { useEffect, useState } from "react";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { SourceBadge } from "@/components/inbox/SourceBadge";
import { MoneyWithUsd } from "@/components/money/MoneyWithUsd";
import { api } from "@/lib/api";
import { formatDateTime, formatRate, formatShortDate } from "@/lib/format";
import { FX_SOURCE_LABELS, PAYEE_KIND_LABELS, ruleLabel } from "@/lib/labels";
import type { EvidenceFileView, LedgerEntryView } from "@/lib/types";
import { OutcomeBadge } from "./OutcomeBadge";

const VISIBLE_REASONS = 2;
const LINK_CLASS =
  "rounded text-sm font-normal text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent";

export function LedgerTable({ entries }: { entries: LedgerEntryView[] | null }) {
  const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);
  if (entries === null) return <LedgerTableSkeleton />;
  if (entries.length === 0) {
    return (
      <p className="px-6 py-12 text-sm text-muted">
        No decisions in this period yet. Send a demo scenario from the inbox.
      </p>
    );
  }
  return (
    <>
      <div
        aria-hidden
        className="hidden gap-4 border-b border-line px-6 py-2.5 text-sm font-bold text-muted [font-variant-caps:all-small-caps] md:grid md:grid-cols-[7rem_10rem_minmax(0,1fr)_12rem_minmax(0,1.4fr)_auto]"
      >
        <span>Date</span>
        <span>Outcome</span>
        <span>Payee</span>
        <span>Amount</span>
        <span>Why</span>
        <span className="text-right">Run</span>
      </div>
      <ul className="divide-y divide-line">
        {entries.map((entry) => {
          const isExpanded = expandedEntryId === entry.entry_id;
          return (
            <li key={entry.entry_id}>
              <LedgerRow
                entry={entry}
                isExpanded={isExpanded}
                onToggle={() => setExpandedEntryId(isExpanded ? null : entry.entry_id)}
              />
              {isExpanded && <LedgerRowDetail entry={entry} />}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function LedgerRow({
  entry,
  isExpanded,
  onToggle,
}: {
  entry: LedgerEntryView;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const hiddenReasonCount = entry.reasons.length - VISIBLE_REASONS;
  return (
    <div className="grid gap-3 px-6 py-4 md:grid-cols-[7rem_10rem_minmax(0,1fr)_12rem_minmax(0,1.4fr)_auto] md:items-start md:gap-4">
      <p className="text-xs text-muted tabular-nums">{formatDateTime(entry.occurred_at)}</p>
      <div>
        <OutcomeBadge outcome={entry.outcome} />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm text-ink">{entry.payee_name ?? entry.subject ?? "Unknown payee"}</p>
        <p className="text-xs text-muted">
          {entry.payee_kind ? PAYEE_KIND_LABELS[entry.payee_kind] : "No bill"}
          {entry.actor === "human" && " · decided by a person"}
        </p>
      </div>
      <div className="text-sm">
        <MoneyWithUsd amount={entry.amount} currency={entry.currency} amountUsd={entry.amount_usd} layout="stacked" />
      </div>
      <div className="min-w-0 space-y-1">
        {entry.reasons.slice(0, VISIBLE_REASONS).map((reason) => (
          <p key={`${reason.rule_id}-${reason.reason}`} className="text-xs leading-[1.4] text-nav-ink">
            <span className="text-ink">{reason.rule_id}</span> · {reason.reason}
          </p>
        ))}
        {hiddenReasonCount > 0 && <p className="text-xs text-muted">+{hiddenReasonCount} more</p>}
        {entry.reasons.length === 0 && <p className="text-xs text-muted">All rules passed</p>}
      </div>
      <div className="flex flex-wrap items-center gap-3 md:flex-col md:items-end">
        {entry.channel && <SourceBadge type={entry.channel} />}
        <ExecutionLink entry={entry} />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={isExpanded}
          className="rounded px-1 text-xs text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          {isExpanded ? "Hide details" : "Details and files"}
        </button>
      </div>
    </div>
  );
}

function ExecutionLink({ entry }: { entry: LedgerEntryView }) {
  if (entry.run_id) {
    return (
      <Link href={`/runs/${entry.run_id}`} className={LINK_CLASS}>
        View execution ›
      </Link>
    );
  }
  const fallbackLabel = executionFallbackLabel(entry);
  return <span className="text-xs text-muted">{fallbackLabel}</span>;
}

function executionFallbackLabel(entry: LedgerEntryView): string {
  if (entry.is_seeded) return "Imported history";
  if (entry.actor === "human") return "Decided by a person";
  if (entry.bill_id) return "No agent run";
  return "Stopped before the agent";
}

function LedgerRowDetail({ entry }: { entry: LedgerEntryView }) {
  const hasConversion = entry.fx_usd_per_unit !== null && entry.currency !== null && entry.currency !== "USD";
  return (
    <div className="space-y-3 bg-sunken/60 px-6 py-4 text-sm">
      <p className="leading-[1.4] text-ink">{entry.explanation}</p>
      {entry.note && (
        <p className="text-nav-ink">
          <span className="text-muted">Human note: </span>
          {entry.note}
        </p>
      )}
      {entry.reasons.length > 0 && (
        <ul className="space-y-1">
          {entry.reasons.map((reason) => (
            <li key={`${reason.rule_id}-${reason.reason}`} className="text-xs leading-[1.4] text-nav-ink">
              <span className="text-ink">
                {reason.rule_id} · {ruleLabel(reason.rule_id)}
              </span>
              : {reason.reason}
            </li>
          ))}
        </ul>
      )}
      {hasConversion && entry.fx_usd_per_unit && entry.currency && (
        <p className="text-xs text-muted tabular-nums">
          Exchange rate: {formatRate(entry.fx_usd_per_unit, entry.currency)}
          {entry.fx_rate_date && ` · ${formatShortDate(entry.fx_rate_date)}`}
          {entry.fx_source && ` · ${FX_SOURCE_LABELS[entry.fx_source]}`}
        </p>
      )}
      {entry.subject && <p className="text-xs text-muted">Subject: {entry.subject}</p>}
      {entry.bill_id && <LedgerEvidence billId={entry.bill_id} />}
    </div>
  );
}

function LedgerEvidence({ billId }: { billId: string }) {
  const [evidence, setEvidence] = useState<EvidenceFileView[] | null>(null);
  const [hasFailed, setHasFailed] = useState(false);

  useEffect(() => {
    let isActive = true;
    api
      .bill(billId)
      .then((detail) => isActive && setEvidence(detail.evidence))
      .catch(() => isActive && setHasFailed(true));
    return () => {
      isActive = false;
    };
  }, [billId]);

  if (hasFailed) return <p className="text-xs text-muted">The invoice files could not be loaded.</p>;
  if (evidence === null) return <div aria-hidden className="h-16 animate-pulse rounded-lg bg-sunken" />;
  return <EvidenceSection evidence={evidence} />;
}

function LedgerTableSkeleton() {
  return (
    <ul aria-hidden className="divide-y divide-line">
      {[0, 1, 2, 3].map((row) => (
        <li key={row} className="space-y-2 px-6 py-4">
          <div className="h-3.5 w-1/2 animate-pulse rounded bg-sunken" />
          <div className="h-3.5 w-3/4 animate-pulse rounded bg-sunken" />
        </li>
      ))}
    </ul>
  );
}
