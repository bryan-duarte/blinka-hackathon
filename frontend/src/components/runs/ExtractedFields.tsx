import { formatMoney, formatRate } from "@/lib/format";
import { EXTRACTION_METHOD_LABELS, FIELD_LABELS, FX_SOURCE_LABELS } from "@/lib/labels";
import type { ExtractionPayload, FxPayload } from "@/lib/types";

const PERCENT = 100;
const CATEGORY_FIELD = "category";
const CATEGORY_LABEL = "Category";

type ExtractedFieldsProps = {
  extraction: ExtractionPayload;
  fx: FxPayload | null;
};

export function ExtractedFields({ extraction, fx }: ExtractedFieldsProps) {
  const methodLabel = EXTRACTION_METHOD_LABELS[extraction.method] ?? extraction.method;
  return (
    <section aria-label="Extracted fields" className="flex flex-col gap-2">
      <p className="text-sm">
        <span className="font-medium">Read from the invoice</span>
        <span className="text-muted"> · {methodLabel}</span>
      </p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)_64px] items-center gap-x-4 gap-y-1.5 text-[13px]">
        {extraction.fields.map((field) => (
          <div key={field.name} className="contents">
            <dt className="text-muted">{field.name === CATEGORY_FIELD ? CATEGORY_LABEL : (FIELD_LABELS[field.name] ?? field.name)}</dt>
            <dd className="truncate">{field.value ?? <span className="text-muted">not found</span>}</dd>
            <dd>
              {field.confidence !== null && (
                <span
                  role="meter"
                  aria-label="Confidence"
                  aria-valuemin={0}
                  aria-valuemax={1}
                  aria-valuenow={field.confidence}
                  className="block h-1 overflow-hidden rounded-full bg-sunken"
                >
                  <span className="block h-full bg-ink" style={{ width: `${field.confidence * PERCENT}%` }} />
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {fx && <FxLine fx={fx} />}
    </section>
  );
}

function FxLine({ fx }: { fx: FxPayload }) {
  if (!fx.amount || !fx.currency || !fx.amount_usd) return null;
  const parts = [
    `${formatMoney(fx.amount, fx.currency)} → ${formatMoney(fx.amount_usd, "USD")}`,
    fx.usd_per_unit ? formatRate(fx.usd_per_unit, fx.currency) : null,
    [fx.source ? FX_SOURCE_LABELS[fx.source] : null, fx.rate_date].filter(Boolean).join(" "),
  ];
  return <p className="text-[13px] tabular-nums">{parts.filter(Boolean).join(" · ")}</p>;
}
