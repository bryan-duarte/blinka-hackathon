const dateTimeFormatter = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "medium",
  timeStyle: "short",
});

const relativeFormatter = new Intl.RelativeTimeFormat("es", {
  numeric: "auto",
});

const MS_PER_SECOND = 1000;

export const USD_CURRENCY = "USD";
export const CURRENCY_CODE_LENGTH = 3;

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

export function formatDateTime(isoDate: string): string {
  return dateTimeFormatter.format(new Date(isoDate));
}

export function formatRelative(isoDate: string): string {
  const elapsedSeconds = (new Date(isoDate).getTime() - Date.now()) / MS_PER_SECOND;
  for (const [unit, unitSeconds] of RELATIVE_UNITS) {
    if (Math.abs(elapsedSeconds) >= unitSeconds) {
      return relativeFormatter.format(Math.round(elapsedSeconds / unitSeconds), unit);
    }
  }
  return "ahora";
}

const moneyFormatter = new Intl.NumberFormat("es-CL", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatMoney(amount: string | number, currency: string | null): string {
  const formatted = moneyFormatter.format(Number(amount));
  return currency ? `${currency} ${formatted}` : formatted;
}

export function isForeignCurrency(currency: string | null): boolean {
  return currency !== null && currency !== USD_CURRENCY;
}
