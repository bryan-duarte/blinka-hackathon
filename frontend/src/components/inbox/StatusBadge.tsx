import type { InboxEmailStatus } from "@/lib/types";

const NEEDS_ACTION = "border-transparent bg-accent-wash text-accent";
const SETTLED = "border-transparent bg-sunken text-nav-ink";
const STOPPED = "border-night bg-panel text-night";
const NEUTRAL = "border-line bg-panel text-muted";

const BADGES: Record<InboxEmailStatus, { label: string; glyph: string; className: string }> = {
  received: { label: "Recibido", glyph: "…", className: NEUTRAL },
  processing: { label: "Revisando", glyph: "…", className: NEUTRAL },
  blocked: { label: "Bloqueado", glyph: "✕", className: STOPPED },
  analyzing: { label: "Evaluando", glyph: "…", className: NEUTRAL },
  paid: { label: "Pagado", glyph: "✓", className: SETTLED },
  held: { label: "Frenado", glyph: "✕", className: STOPPED },
  review: { label: "En revisión", glyph: "!", className: NEEDS_ACTION },
  duplicate: { label: "Duplicado", glyph: "", className: NEUTRAL },
  no_invoice: { label: "Sin factura", glyph: "", className: NEUTRAL },
  error: { label: "Error", glyph: "✕", className: STOPPED },
};

const PULSING_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "received",
  "processing",
  "analyzing",
]);

export function StatusBadge({ status }: { status: InboxEmailStatus }) {
  const badge = BADGES[status];
  const isPulsing = PULSING_STATUSES.has(status);
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-normal ${badge.className}`}
    >
      {badge.glyph && !isPulsing && <span aria-hidden>{badge.glyph}</span>}
      {badge.label}
      {isPulsing && (
        <span aria-hidden className="animate-pulse">
          {badge.glyph}
        </span>
      )}
    </span>
  );
}
