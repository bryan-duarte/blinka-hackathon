import { formatMoney, formatRate, formatShortDate, isForeignCurrency } from "@/lib/format";
import { FX_SOURCE_LABELS } from "@/lib/labels";
import type { Decimal, FxSource } from "@/lib/types";

type MoneyWithUsdProps = {
  amount: Decimal | null;
  currency: string | null;
  amountUsd: Decimal | null;
  usdPerUnit?: Decimal | null;
  rateDate?: string | null;
  fxSource?: FxSource | null;
  layout?: "inline" | "stacked";
};

export function MoneyWithUsd({
  amount,
  currency,
  amountUsd,
  usdPerUnit = null,
  rateDate = null,
  fxSource = null,
  layout = "stacked",
}: MoneyWithUsdProps) {
  if (amount === null) {
    return <span className="text-muted">No amount</span>;
  }
  const original = <span className="text-ink tabular-nums">{formatMoney(amount, currency)}</span>;
  if (!isForeignCurrency(currency)) {
    return original;
  }
  const conversion =
    amountUsd === null ? (
      <span className="text-warning">No USD rate</span>
    ) : (
      <span className="text-muted tabular-nums">
        {usdLine(amountUsd, currency, usdPerUnit, rateDate, fxSource)}
      </span>
    );
  const containerClass = layout === "stacked" ? "flex flex-col gap-0.5" : "inline-flex flex-wrap gap-x-2";
  return (
    <span className={containerClass}>
      {original}
      <span className="text-xs">{conversion}</span>
    </span>
  );
}

function usdLine(
  amountUsd: Decimal,
  currency: string | null,
  usdPerUnit: Decimal | null,
  rateDate: string | null,
  fxSource: FxSource | null,
): string {
  const parts = [`≈ ${formatMoney(amountUsd, "USD")}`];
  if (usdPerUnit !== null && currency) parts.push(formatRate(usdPerUnit, currency));
  if (rateDate) parts.push(formatShortDate(rateDate));
  if (fxSource) parts.push(FX_SOURCE_LABELS[fxSource]);
  return parts.join(" · ");
}
