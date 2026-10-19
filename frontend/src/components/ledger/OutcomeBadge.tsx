import { STATUS_BADGE_CLASS, STATUS_TONE } from "@/components/settings/styles";
import { LEDGER_OUTCOME_LABELS } from "@/lib/labels";
import type { LedgerOutcome } from "@/lib/types";

const OUTCOME_BADGES: Record<LedgerOutcome, { glyph: string; className: string }> = {
  paid: { glyph: "✓", className: STATUS_TONE.settled },
  approved_by_human: { glyph: "✓", className: STATUS_TONE.settled },
  escalated: { glyph: "!", className: STATUS_TONE.action },
  held: { glyph: "✕", className: STATUS_TONE.stopped },
  rejected_by_human: { glyph: "✕", className: STATUS_TONE.stopped },
  blocked: { glyph: "✕", className: STATUS_TONE.stopped },
  error: { glyph: "✕", className: STATUS_TONE.stopped },
  duplicate: { glyph: "", className: STATUS_TONE.neutral },
  not_an_invoice: { glyph: "", className: STATUS_TONE.neutral },
  missing_info: { glyph: "!", className: STATUS_TONE.neutral },
};

export function OutcomeBadge({ outcome }: { outcome: LedgerOutcome }) {
  const badge = OUTCOME_BADGES[outcome];
  return (
    <span className={`${STATUS_BADGE_CLASS} ${badge.className}`}>
      {badge.glyph && <span aria-hidden>{badge.glyph}</span>}
      {LEDGER_OUTCOME_LABELS[outcome]}
    </span>
  );
}
