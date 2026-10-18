import { formatMoney, formatPercent } from "@/lib/format";
import type { LedgerKpis as LedgerKpisView } from "@/lib/types";

type KpiProps = { label: string; value: string; caption: string };

export function LedgerKpis({ kpis }: { kpis: LedgerKpisView | null }) {
  return (
    <section
      aria-label="Ledger summary"
      className="grid divide-y divide-line border-b border-line bg-panel md:grid-cols-4 md:divide-x md:divide-y-0"
    >
      {kpis === null ? (
        [0, 1, 2, 3].map((slot) => <KpiSkeleton key={slot} />)
      ) : (
        <>
          <Kpi label="Paid" value={`USD ${formatMoney(kpis.paid_usd, null)}`} caption={countCaption(kpis.paid_count)} />
          <Kpi
            label="Escalated to a person"
            value={`USD ${formatMoney(kpis.escalated_usd, null)}`}
            caption={countCaption(kpis.escalated_count)}
          />
          <Kpi
            label="Stopped by the agent"
            value={`USD ${formatMoney(kpis.stopped_usd, null)}`}
            caption={`${countCaption(kpis.stopped_count)} · money protected`}
          />
          <Kpi
            label="Auto-pay rate"
            value={formatPercent(kpis.auto_pay_rate)}
            caption="Agent bill decisions paid without a person"
          />
        </>
      )}
    </section>
  );
}

function Kpi({ label, value, caption }: KpiProps) {
  return (
    <div className="flex flex-col gap-2 px-4 py-6 md:px-8">
      <p className="text-xs tracking-[0.5px] text-muted uppercase">{label}</p>
      <p className="text-[32px] leading-[1.03] font-light tracking-[-0.64px] text-ink tabular-nums">{value}</p>
      <p className="text-xs text-muted">{caption}</p>
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-2 px-4 py-6 md:px-8">
      <div className="h-3 w-1/3 animate-pulse rounded bg-sunken" />
      <div className="h-8 w-2/3 animate-pulse rounded bg-sunken" />
      <div className="h-3 w-1/2 animate-pulse rounded bg-sunken" />
    </div>
  );
}

function countCaption(count: number): string {
  return count === 1 ? "1 decision" : `${count} decisions`;
}
