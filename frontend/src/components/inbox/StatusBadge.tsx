import { STATUS_BADGE_CLASS, STATUS_TONE } from "@/components/settings/styles";
import type { InboxEmailStatus } from "@/lib/types";

const BADGES: Record<InboxEmailStatus, { label: string; glyph: string; className: string }> = {
  received: { label: "Received", glyph: "…", className: STATUS_TONE.neutral },
  processing: { label: "Checking", glyph: "…", className: STATUS_TONE.neutral },
  blocked: { label: "Blocked", glyph: "✕", className: STATUS_TONE.stopped },
  analyzing: { label: "Analyzing", glyph: "…", className: STATUS_TONE.neutral },
  paid: { label: "Paid", glyph: "✓", className: STATUS_TONE.settled },
  held: { label: "Held", glyph: "✕", className: STATUS_TONE.stopped },
  review: { label: "Needs you", glyph: "!", className: STATUS_TONE.action },
  duplicate: { label: "Duplicate", glyph: "", className: STATUS_TONE.neutral },
  no_invoice: { label: "Not an invoice", glyph: "", className: STATUS_TONE.neutral },
  no_info: { label: "Missing data", glyph: "!", className: STATUS_TONE.neutral },
  error: { label: "Error", glyph: "✕", className: STATUS_TONE.stopped },
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
    <span className={`${STATUS_BADGE_CLASS} ${badge.className}`}>
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
