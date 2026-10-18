"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { CurrencyBreakdown } from "@/components/ledger/CurrencyBreakdown";
import { DecisionsOverTimeChart } from "@/components/ledger/DecisionsOverTimeChart";
import { LedgerFilters } from "@/components/ledger/LedgerFilters";
import { LedgerKpis } from "@/components/ledger/LedgerKpis";
import { LedgerTable } from "@/components/ledger/LedgerTable";
import { LimitsChart } from "@/components/ledger/LimitsChart";
import { TopReasonsChart } from "@/components/ledger/TopReasonsChart";
import { CARD_CLASS, EYEBROW_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import { currentPeriod, formatPeriod } from "@/lib/format";
import { entriesInTab, tabCounts } from "@/lib/ledgerTabs";
import { TERMINAL_RUN_STEPS } from "@/lib/runEvents";
import type {
  LedgerEntryView,
  LedgerFilters as LedgerFiltersValue,
  LedgerSummaryView,
  LedgerTab,
  PayeeView,
} from "@/lib/types";
import { useInboxChannel } from "@/lib/useInboxChannel";

const SUMMARY_MONTHS = 4;
const ALL_TIME_PARAM = "all";
const LEDGER_TABS: ReadonlySet<string> = new Set<LedgerTab>(["all", "paid", "escalated", "stopped"]);
const EXCHANGE_RATE_API_URL = "https://www.exchangerate-api.com";

export default function LedgerPage() {
  return (
    <ConsoleShell>
      <Suspense fallback={<ConsoleTopBar title="Agent ledger" caption="Every decision the agent made, and why" />}>
        <LedgerContent />
      </Suspense>
    </ConsoleShell>
  );
}

function LedgerContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = filtersFromParams(searchParams);
  const [summary, setSummary] = useState<LedgerSummaryView | null>(null);
  const [entries, setEntries] = useState<LedgerEntryView[] | null>(null);
  const [payees, setPayees] = useState<PayeeView[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const { period, payee_id: payeeId, currency } = filters;

  useInboxChannel((event) => {
    const isTerminalStep = event.type === "run.step" && TERMINAL_RUN_STEPS.has(event.step);
    if (isTerminalStep) setRefreshCount((count) => count + 1);
  });

  const handleLoadError = useCallback(
    (error: unknown) => {
      if (error instanceof UnauthorizedError) {
        router.replace("/login");
        return;
      }
      setLoadError("The ledger could not be loaded.");
    },
    [router],
  );

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    api
      .payees()
      .then(setPayees)
      .catch(() => setPayees([]));
  }, [router]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    let isCancelled = false;
    Promise.all([
      api.ledgerSummary(period, SUMMARY_MONTHS),
      api.ledgerEntries({ period, tab: "all", payee_id: payeeId, currency }),
    ])
      .then(([loadedSummary, loadedEntries]) => {
        if (isCancelled) return;
        setSummary(loadedSummary);
        setEntries(loadedEntries);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (!isCancelled) handleLoadError(error);
      });
    return () => {
      isCancelled = true;
    };
  }, [period, payeeId, currency, refreshCount, handleLoadError]);

  function updateFilters(changes: Partial<LedgerFiltersValue>) {
    const nextFilters = { ...filters, ...changes };
    const params = new URLSearchParams();
    params.set("period", nextFilters.period ?? ALL_TIME_PARAM);
    if (nextFilters.tab !== "all") params.set("tab", nextFilters.tab);
    if (nextFilters.payee_id) params.set("payee", nextFilters.payee_id);
    if (nextFilters.currency) params.set("currency", nextFilters.currency);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  async function exportCsv() {
    setIsExporting(true);
    setExportError(null);
    try {
      await api.exportLedgerCsv(filters);
    } catch {
      setExportError("The CSV could not be exported.");
    } finally {
      setIsExporting(false);
    }
  }

  const currencies = [...new Set((summary?.currencies ?? []).map((total) => total.currency))];
  const visibleEntries = entries ? entriesInTab(entries, filters.tab) : null;

  return (
    <>
      <ConsoleTopBar
        title="Agent ledger"
        caption="Every decision the agent made, and why"
        actions={
          <button type="button" onClick={exportCsv} disabled={isExporting} className={`${SECONDARY_BUTTON_CLASS} h-9 px-4`}>
            {isExporting ? "Exporting…" : "Export CSV"}
          </button>
        }
      />
      {(loadError || exportError) && (
        <p role="alert" className="border-b border-line bg-danger-soft px-4 py-2 text-sm text-danger md:px-8">
          <span aria-hidden>✕ </span>
          {loadError ?? exportError}
        </p>
      )}
      <LedgerKpis kpis={summary?.kpis ?? null} />
      {summary && filters.period === null && (
        <p className="border-b border-line px-4 py-2 text-xs text-muted md:px-8">
          The figures and charts show {formatPeriod(summary.period)}; the table below lists all time.
        </p>
      )}
      <main className="flex flex-1 flex-col gap-6 px-4 py-6 md:px-8">
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <ChartCard title="Decisions over time" isLoading={summary === null}>
            {summary && <DecisionsOverTimeChart timeline={summary.timeline} />}
          </ChartCard>
          <ChartCard title="Spend against limits" isLoading={summary === null}>
            {summary && <LimitsChart limits={summary.limits} />}
          </ChartCard>
          <ChartCard title="Top reasons to stop or escalate" isLoading={summary === null}>
            {summary && <TopReasonsChart reasons={summary.top_reasons} />}
          </ChartCard>
          <ChartCard title="Paid by currency" isLoading={summary === null}>
            {summary && <CurrencyBreakdown currencies={summary.currencies} />}
          </ChartCard>
        </div>
        <LedgerFilters
          filters={filters}
          tabCounts={entries ? tabCounts(entries) : null}
          payees={payees}
          currencies={currencies}
          onChange={updateFilters}
        />
        <section aria-label="Ledger entries" className="overflow-hidden rounded-lg border border-line bg-panel">
          <LedgerTable entries={visibleEntries} />
        </section>
        <p className="text-xs text-muted">
          Exchange rates:{" "}
          <a
            href={EXCHANGE_RATE_API_URL}
            target="_blank"
            rel="noreferrer"
            className="text-ink underline decoration-line underline-offset-2 hover:decoration-current"
          >
            live rates by Exchange Rate API
          </a>{" "}
          (open.er-api.com), cached daily; fallback table when offline.
        </p>
      </main>
    </>
  );
}

function ChartCard({ title, isLoading, children }: { title: string; isLoading: boolean; children: React.ReactNode }) {
  return (
    <section className={`${CARD_CLASS} flex flex-col gap-4 p-6`}>
      <h2 className={EYEBROW_CLASS}>{title}</h2>
      {isLoading ? <div aria-hidden className="h-48 animate-pulse rounded bg-sunken" /> : children}
    </section>
  );
}

function filtersFromParams(searchParams: URLSearchParams): LedgerFiltersValue {
  const periodParam = searchParams.get("period");
  const tabParam = searchParams.get("tab") ?? "all";
  return {
    period: periodParam === ALL_TIME_PARAM ? null : (periodParam ?? currentPeriod()),
    tab: LEDGER_TABS.has(tabParam) ? (tabParam as LedgerTab) : "all",
    payee_id: searchParams.get("payee"),
    currency: searchParams.get("currency"),
  };
}
