import { formatMoney } from "@/lib/format";
import type { BudgetUsageView, InboxEmailView } from "@/lib/types";

const GLOBAL_SCOPE = "global";
const PERCENT = 100;
const NEAR_LIMIT_PERCENT = 90;

const monthFormatter = new Intl.DateTimeFormat("en-US", { month: "long" });

type InboxMetricsProps = {
  emails: InboxEmailView[] | null;
  budgets: BudgetUsageView[] | null;
};

type BudgetSummary = {
  limitUsd: number | null;
  reservedUsd: number;
  pendingUsd: number;
};

function summarizePending(emails: InboxEmailView[]): { count: number; totalUsd: number } {
  const pending = emails.filter((email) => email.status === "review");
  const totalUsd = pending.reduce((sum, email) => sum + Number(email.decision?.amount_usd ?? 0), 0);
  return { count: pending.length, totalUsd };
}

function usagePercent(amountUsd: number, limitUsd: number): number {
  if (limitUsd <= 0) return PERCENT;
  return Math.min(PERCENT, (amountUsd / limitUsd) * PERCENT);
}

export function InboxMetrics({ emails, budgets }: InboxMetricsProps) {
  const pending = emails ? summarizePending(emails) : null;
  const globalBudget = budgets?.find((budget) => budget.scope === GLOBAL_SCOPE) ?? null;
  const month = monthFormatter.format(new Date());

  return (
    <section aria-label="Month summary" className="grid divide-y divide-line border-b border-line md:grid-cols-3 md:divide-x md:divide-y-0">
      <Metric label="Waiting for you" isLoading={pending === null}>
        {pending && (
          <>
            <MetricValue amountUsd={pending.totalUsd} />
            <p className="text-xs text-muted">
              {pending.count === 1 ? "1 invoice in review" : `${pending.count} invoices in review`}
            </p>
          </>
        )}
      </Metric>
      <Metric label={`Paid in ${month}`} isLoading={budgets === null}>
        {budgets && (
          <>
            <MetricValue amountUsd={Number(globalBudget?.reserved_usd ?? 0)} />
            <p className="text-xs text-muted">Payments executed and in progress this month.</p>
          </>
        )}
      </Metric>
      <Metric label="Budget available" isLoading={budgets === null || pending === null}>
        {budgets && pending && (
          <BudgetLeft
            limitUsd={globalBudget?.limit_usd != null ? Number(globalBudget.limit_usd) : null}
            reservedUsd={Number(globalBudget?.reserved_usd ?? 0)}
            pendingUsd={pending.totalUsd}
          />
        )}
      </Metric>
    </section>
  );
}

function Metric({ label, isLoading, children }: { label: string; isLoading: boolean; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-6 md:px-8 md:py-8">
      <p className="text-xs tracking-[0.5px] text-muted uppercase">{label}</p>
      {isLoading ? (
        <div aria-hidden className="flex flex-col gap-2">
          <div className="h-10 w-2/3 animate-pulse rounded bg-sunken" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-sunken" />
        </div>
      ) : (
        children
      )}
    </div>
  );
}

function MetricValue({ amountUsd }: { amountUsd: number }) {
  return (
    <p className="text-[32px] leading-[1.03] font-light tracking-[-0.64px] text-ink md:text-[48px] md:tracking-[-0.96px]">
      <span className="mr-2 text-xl tracking-[-0.2px] text-muted">USD</span>
      {formatMoney(amountUsd, null)}
    </p>
  );
}

function BudgetLeft({ limitUsd, reservedUsd, pendingUsd }: BudgetSummary) {
  if (limitUsd === null) {
    return (
      <>
        <p className="text-[32px] leading-[1.03] font-light tracking-[-0.64px] text-ink md:text-[48px]">No cap</p>
        <p className="text-xs text-muted">The policy sets no monthly budget.</p>
      </>
    );
  }
  const reservedPercent = usagePercent(reservedUsd, limitUsd);
  const pendingPercent = Math.min(PERCENT - reservedPercent, usagePercent(pendingUsd, limitUsd));
  const isNearLimit = reservedPercent >= NEAR_LIMIT_PERCENT;
  return (
    <>
      <MetricValue amountUsd={Math.max(0, limitUsd - reservedUsd)} />
      <div
        role="progressbar"
        aria-label="Budget used"
        aria-valuemin={0}
        aria-valuemax={limitUsd}
        aria-valuenow={reservedUsd}
        className="relative h-1 overflow-hidden rounded bg-sunken"
      >
        <span
          className={`absolute inset-y-0 left-0 rounded ${isNearLimit ? "bg-night" : "bg-accent"}`}
          style={{ width: `${reservedPercent}%` }}
        />
        <span
          className="absolute inset-y-0 bg-selection"
          style={{ left: `${reservedPercent}%`, width: `${pendingPercent}%` }}
        />
      </div>
      <p className="text-xs text-muted">
        of USD {formatMoney(limitUsd, null)}. The grey part is waiting for your approval.
      </p>
    </>
  );
}
