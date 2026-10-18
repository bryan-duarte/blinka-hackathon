import { formatMoney } from "@/lib/format";
import type { CurrencyTotal } from "@/lib/types";

const PERCENT = 100;

export function CurrencyBreakdown({ currencies }: { currencies: CurrencyTotal[] }) {
  if (currencies.length === 0) {
    return <p className="text-sm text-muted">Nothing was paid in this period yet.</p>;
  }
  const totalUsd = currencies.reduce((sum, currency) => sum + Number(currency.amount_usd), 0);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-muted">
          <th scope="col" className="pb-2 font-light">Currency</th>
          <th scope="col" className="pb-2 text-right font-light">Original</th>
          <th scope="col" className="pb-2 text-right font-light">USD</th>
          <th scope="col" className="pb-2 text-right font-light">Paid</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line border-t border-line">
        {currencies.map((currency) => {
          const sharePercent = totalUsd > 0 ? (Number(currency.amount_usd) / totalUsd) * PERCENT : 0;
          return (
            <tr key={currency.currency}>
              <td className="py-2 text-ink">
                {currency.currency}
                <span aria-hidden className="mt-1 block h-1 rounded bg-sunken">
                  <span className="block h-full rounded bg-nav-ink" style={{ width: `${sharePercent}%` }} />
                </span>
              </td>
              <td className="py-2 text-right text-ink tabular-nums">{formatMoney(currency.amount, null)}</td>
              <td className="py-2 text-right text-ink tabular-nums">{formatMoney(currency.amount_usd, null)}</td>
              <td className="py-2 text-right text-muted tabular-nums">{currency.count}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
