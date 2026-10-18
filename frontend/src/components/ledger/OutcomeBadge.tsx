import { LEDGER_OUTCOME_LABELS } from "@/lib/labels";
import type { LedgerOutcome } from "@/lib/types";

const NEEDS_ACTION = "border-transparent bg-accent-wash text-accent";
const SETTLED = "border-transparent bg-sunken text-nav-ink";
const STOPPED = "border-night bg-panel text-night";
const NEUTRAL = "border-line bg-panel text-muted";

const OUTCOME_BADGES: Record<LedgerOutcome, { glyph: string; className: string }> = {
  paid: { glyph: "✓", className: SETTLED },
  approved_by_human: { glyph: "✓", className: SETTLED },
  escalated: { glyph: "!", className: NEEDS_ACTION },
  held: { glyph: "✕", className: STOPPED },
  rejected_by_human: { glyph: "✕", className: STOPPED },
  blocked: { glyph: "✕", className: STOPPED },
  error: { glyph: "✕", className: STOPPED },
  duplicate: { glyph: "", className: NEUTRAL },
  not_an_invoice: { glyph: "", className: NEUTRAL },
  missing_info: { glyph: "!", className: NEUTRAL },
};

export function OutcomeBadge({ outcome }: { outcome: LedgerOutcome }) {
  const badge = OUTCOME_BADGES[outcome];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-normal ${badge.className}`}
    >
      {badge.glyph && <span aria-hidden>{badge.glyph}</span>}
      {LEDGER_OUTCOME_LABELS[outcome]}
    </span>
  );
}
