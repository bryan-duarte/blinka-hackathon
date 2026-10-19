import { filterTabClass } from "@/components/settings/styles";
import { formatPeriod } from "@/lib/format";
import type { LedgerFilters as LedgerFiltersValue, LedgerTab, PayeeView } from "@/lib/types";

const PERIOD_OPTION_COUNT = 6;
const ALL_TIME_VALUE = "";
const TABS: { tab: LedgerTab; label: string }[] = [
  { tab: "all", label: "All" },
  { tab: "paid", label: "Paid" },
  { tab: "escalated", label: "Escalated" },
  { tab: "stopped", label: "Stopped" },
];
const SELECT_CLASS =
  "h-9 rounded border border-line bg-panel px-3 text-sm text-ink focus-visible:border-accent focus-visible:outline-1 focus-visible:outline-accent";

type LedgerFiltersProps = {
  filters: LedgerFiltersValue;
  tabCounts: Record<LedgerTab, number> | null;
  payees: PayeeView[];
  currencies: string[];
  onChange: (changes: Partial<LedgerFiltersValue>) => void;
};

export function LedgerFilters({ filters, tabCounts, payees, currencies, onChange }: LedgerFiltersProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div role="group" aria-label="Outcome" className="flex flex-wrap gap-1">
        {TABS.map(({ tab, label }) => {
          const isActive = filters.tab === tab;
          return (
            <button
              key={tab}
              type="button"
              aria-pressed={isActive}
              onClick={() => onChange({ tab })}
              className={filterTabClass(isActive)}
            >
              {label}
              {tabCounts && <span className="tabular-nums opacity-70">{tabCounts[tab]}</span>}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="flex items-center gap-2 text-xs text-muted">
          Period
          <select
            value={filters.period ?? ALL_TIME_VALUE}
            onChange={(event) => onChange({ period: event.target.value || null })}
            className={SELECT_CLASS}
          >
            {recentPeriods().map((period) => (
              <option key={period} value={period}>
                {formatPeriod(period)}
              </option>
            ))}
            <option value={ALL_TIME_VALUE}>All time</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-muted">
          Payee
          <select
            value={filters.payee_id ?? ""}
            onChange={(event) => onChange({ payee_id: event.target.value || null })}
            className={SELECT_CLASS}
          >
            <option value="">All payees</option>
            {payees.map((payee) => (
              <option key={payee.payee_id} value={payee.payee_id}>
                {payee.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-muted">
          Currency
          <select
            value={filters.currency ?? ""}
            onChange={(event) => onChange({ currency: event.target.value || null })}
            className={SELECT_CLASS}
          >
            <option value="">All currencies</option>
            {currencies.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function recentPeriods(): string[] {
  const today = new Date();
  return Array.from({ length: PERIOD_OPTION_COUNT }, (_, monthsBack) => {
    const month = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - monthsBack, 1));
    return month.toISOString().slice(0, "YYYY-MM".length);
  });
}
