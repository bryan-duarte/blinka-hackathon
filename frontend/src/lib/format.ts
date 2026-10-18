const LOCALE = "en-US";

const dateTimeFormatter = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "medium",
  timeStyle: "short",
});

const relativeFormatter = new Intl.RelativeTimeFormat(LOCALE, {
  numeric: "auto",
});

const MS_PER_SECOND = 1000;
const BYTES_PER_KILOBYTE = 1024;
const BYTES_PER_MEGABYTE = BYTES_PER_KILOBYTE * 1024;

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
  return "now";
}

const moneyFormatter = new Intl.NumberFormat(LOCALE, {
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

const sizeFormatter = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 });

export function formatBytes(sizeBytes: number): string {
  if (sizeBytes >= BYTES_PER_MEGABYTE) return `${sizeFormatter.format(sizeBytes / BYTES_PER_MEGABYTE)} MB`;
  if (sizeBytes >= BYTES_PER_KILOBYTE) return `${sizeFormatter.format(sizeBytes / BYTES_PER_KILOBYTE)} KB`;
  return `${sizeBytes} B`;
}

const RATE_SIGNIFICANT_DIGITS = 4;
const rateFormatter = new Intl.NumberFormat(LOCALE, {
  maximumSignificantDigits: RATE_SIGNIFICANT_DIGITS,
});

export function formatRate(usdPerUnit: string | number, currency: string): string {
  return `1 ${currency} = ${rateFormatter.format(Number(usdPerUnit))} USD`;
}

const shortDateFormatter = new Intl.DateTimeFormat(LOCALE, {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

export function formatShortDate(isoDate: string): string {
  return shortDateFormatter.format(new Date(isoDate));
}

const periodFormatter = new Intl.DateTimeFormat(LOCALE, {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function formatPeriod(period: string): string {
  return periodFormatter.format(new Date(`${period}-01T00:00:00Z`));
}

export function currentPeriod(): string {
  return new Date().toISOString().slice(0, "YYYY-MM".length);
}

const percentFormatter = new Intl.NumberFormat(LOCALE, {
  style: "percent",
  maximumFractionDigits: 0,
});

export function formatPercent(ratio: string | number): string {
  return percentFormatter.format(Number(ratio));
}

const SECONDS_PER_MINUTE = 60;

export function formatDuration(durationMs: number): string {
  const totalSeconds = Math.round(durationMs / MS_PER_SECOND);
  if (totalSeconds < SECONDS_PER_MINUTE) return `${totalSeconds} s`;
  const minutes = Math.floor(totalSeconds / SECONDS_PER_MINUTE);
  return `${minutes} min ${totalSeconds % SECONDS_PER_MINUTE} s`;
}

const toolDurationFormatter = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatToolDuration(durationMs: number): string {
  return `${toolDurationFormatter.format(durationMs / MS_PER_SECOND)} s`;
}
