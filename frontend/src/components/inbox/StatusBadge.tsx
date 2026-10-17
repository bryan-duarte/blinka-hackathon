import type { InboxEmailStatus } from "@/lib/types";

const BADGES: Record<InboxEmailStatus, { label: string; className: string }> = {
  received: { label: "Recibido", className: "bg-sunken text-muted" },
  processing: { label: "Revisando", className: "bg-sunken text-muted" },
  blocked: { label: "Bloqueado", className: "bg-danger-soft text-danger" },
  analyzing: { label: "Evaluando", className: "bg-warning-soft text-warning" },
  paid: { label: "Pagado", className: "bg-success-soft text-success" },
  held: { label: "Frenado", className: "bg-danger-soft text-danger" },
  review: { label: "En revisión", className: "bg-warning-soft text-warning" },
  duplicate: { label: "Duplicado", className: "bg-sunken text-muted" },
  no_invoice: { label: "Sin factura", className: "bg-sunken text-muted" },
  error: {
    label: "Error",
    className: "border border-danger/40 bg-panel text-danger",
  },
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
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
    >
      {isPulsing && (
        <span
          aria-hidden
          className="size-1.5 animate-pulse rounded-full bg-current"
        />
      )}
      {badge.label}
    </span>
  );
}
