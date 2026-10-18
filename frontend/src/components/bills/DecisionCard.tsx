import { useState } from "react";
import { MoneyWithUsd } from "@/components/money/MoneyWithUsd";
import { EYEBROW_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import { ACTOR_LABELS, CATEGORY_LABELS, FIELD_LABELS, VERDICT_LABELS } from "@/lib/labels";
import type {
  BillDecisionView,
  FieldEvidence,
  PaymentCandidate,
  RuleEffect,
  RuleResult,
  Verdict,
} from "@/lib/types";
import { BillProvenance } from "./BillProvenance";
import { ReviewActions } from "./ReviewActions";

type DecisionCardProps = {
  decision: BillDecisionView;
  onResolved: () => void;
  onSelectEmail: (emailId: string) => void;
  showsProvenance?: boolean;
};

const CHECKER_RULE_PREFIX = "CHK";
const PERCENT = 100;

const VERDICT_CHIP: Record<Verdict, { className: string; glyph: string }> = {
  pay: { className: "border-transparent bg-sunken text-nav-ink", glyph: "✓" },
  hold: { className: "border-night bg-panel text-night", glyph: "✕" },
  review: { className: "border-transparent bg-accent-wash text-accent", glyph: "!" },
};

const EFFECT_ROW: Record<RuleEffect, { glyph: string; glyphColor: string; label: string }> = {
  hold: { glyph: "✕", glyphColor: "text-danger", label: "Blocks" },
  review: { glyph: "!", glyphColor: "text-accent", label: "Review" },
  pass: { glyph: "✓", glyphColor: "text-muted", label: "Passes" },
};

const RULE_ROW_CLASS = "grid grid-cols-[1rem_minmax(0,1fr)] gap-4 border-t border-line py-4";

const EFFECT_ORDER: Record<RuleEffect, number> = { hold: 0, review: 1, pass: 2 };

const DISCLOSURE_SUMMARY_CLASS =
  "cursor-pointer list-none rounded text-sm text-muted select-none hover:text-ink focus-visible:outline-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden";

const DUPLICATE_CHIP = { className: "border-line bg-panel text-muted", glyph: "" };

export function DecisionCard({
  decision,
  onResolved,
  onSelectEmail,
  showsProvenance = false,
}: DecisionCardProps) {
  const policyRules = decision.rule_results.filter((rule) => !isCheckerRule(rule));
  const checkerRules = decision.rule_results.filter(isCheckerRule);
  const failingRules = policyRules
    .filter((rule) => rule.effect !== "pass")
    .sort((first, second) => EFFECT_ORDER[first.effect] - EFFECT_ORDER[second.effect]);
  const passingRules = policyRules.filter((rule) => rule.effect === "pass");

  return (
    <section className="flex flex-col gap-6">
      {showsProvenance && <BillProvenance billId={decision.bill_id} />}
      <VerdictHeader decision={decision} />
      {decision.duplicate_of_bill_id && (
        <DuplicateLink originalBillId={decision.duplicate_of_bill_id} onSelectEmail={onSelectEmail} />
      )}
      {failingRules.length > 0 && (
        <div className="space-y-2">
          <h3 className={EYEBROW_CLASS}>Points that stop automatic payment</h3>
          <RuleList rules={failingRules} />
        </div>
      )}
      {passingRules.length > 0 && (
        <details className="group">
          <summary className={DISCLOSURE_SUMMARY_CLASS}>
            <DisclosureChevron />
            {passingRules.length} rules passed
          </summary>
          <div className="mt-2">
            <RuleList rules={passingRules} />
          </div>
        </details>
      )}
      {decision.candidate && <EvidenceTable candidate={decision.candidate} />}
      {checkerRules.length > 0 && <CheckerOpinion rules={checkerRules} />}
      <DecisionHistory billId={decision.bill_id} />
      {decision.can_approve && <ReviewActions billId={decision.bill_id} onResolved={onResolved} />}
    </section>
  );
}

function VerdictHeader({ decision }: { decision: BillDecisionView }) {
  const decidedBy = decision.actor === "human" ? "Decision by a person" : "Decision by the agent";
  const chip = decision.status === "duplicate" ? DUPLICATE_CHIP : VERDICT_CHIP[decision.verdict];
  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className={EYEBROW_CLASS}>{decidedBy}</p>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-normal ${chip.className}`}
        >
          {chip.glyph && <span aria-hidden>{chip.glyph}</span>}
          {verdictLabel(decision)}
        </span>
      </div>
      <p className="text-base leading-[1.4] text-ink">{decision.explanation}</p>
      {decision.note && (
        <p className="text-sm text-muted">
          Note: <span className="text-ink">{decision.note}</span>
        </p>
      )}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 border-y border-line py-4 text-sm sm:grid-cols-4">
        <Fact label="Payee" value={decision.payee_name} />
        <div className="min-w-0 sm:col-span-2">
          <dt className="text-xs text-muted">Amount</dt>
          <dd className="mt-1 text-base">
            <MoneyWithUsd
              amount={decision.amount}
              currency={decision.currency}
              amountUsd={decision.amount_usd}
              usdPerUnit={decision.fx_usd_per_unit}
              rateDate={decision.fx_rate_date}
              fxSource={decision.fx_source}
            />
          </dd>
        </div>
        <Fact label="Category" value={decision.category ? CATEGORY_LABELS[decision.category] : null} />
      </dl>
    </header>
  );
}

function DisclosureChevron() {
  return (
    <span aria-hidden className="mr-1.5 inline-block transition-transform group-open:rotate-90">
      ›
    </span>
  );
}

function verdictLabel(decision: BillDecisionView): string {
  if (decision.status === "duplicate") return "Duplicate";
  if (decision.status === "rejected") return "Rejected";
  return VERDICT_LABELS[decision.verdict];
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 truncate text-base text-ink">{value ?? "No data"}</dd>
    </div>
  );
}

function RuleList({ rules }: { rules: RuleResult[] }) {
  return (
    <ul className="flex flex-col">
      {rules.map((rule) => (
        <RuleRow key={rule.rule_id} rule={rule} />
      ))}
    </ul>
  );
}

function RuleRow({ rule }: { rule: RuleResult }) {
  const row = EFFECT_ROW[rule.effect];
  const evidenceEntries = Object.entries(rule.evidence);
  return (
    <li className={RULE_ROW_CLASS}>
      <span aria-hidden className={`text-center text-sm font-normal ${row.glyphColor}`}>
        {row.glyph}
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="text-sm leading-[1.4] text-ink">
          <span className="sr-only">{row.label}: </span>
          {rule.reason}
        </p>
        <p className="text-xs text-muted">
          {rule.rule_id} · {rule.name.replaceAll("_", " ")}
        </p>
        {evidenceEntries.length > 0 && (
          <p className="text-xs break-words text-muted">
            {evidenceEntries.map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")}
          </p>
        )}
      </div>
    </li>
  );
}

function EvidenceTable({ candidate }: { candidate: PaymentCandidate }) {
  const evidenceByField = new Map<string, FieldEvidence>(
    candidate.evidence.map((evidence) => [evidence.field, evidence]),
  );
  const readFields = Object.entries(FIELD_LABELS).flatMap(([field, label]) => {
    const value = (candidate as Record<string, unknown>)[field];
    if (value === null || value === undefined || value === "") return [];
    const shownValue = field === "amount" ? formatMoney(String(value), null) : String(value);
    return [{ field, label, value: shownValue, evidence: evidenceByField.get(field) }];
  });
  if (readFields.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className={EYEBROW_CLASS}>Data read from the invoice</h3>
      <dl className="divide-y divide-line border-y border-line">
        {readFields.map((readField) => (
          <div key={readField.field} className="grid gap-1 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
            <dt className="text-xs text-muted sm:pt-0.5">{readField.label}</dt>
            <dd className="min-w-0 space-y-1">
              <p className="text-sm break-words text-ink tabular-nums">{readField.value}</p>
              {readField.evidence && (
                <p className="text-xs text-muted">
                  <q className="text-ink/80">{readField.evidence.quote}</q>
                  <span className="ml-2 tabular-nums">
                    confidence {Math.round(readField.evidence.confidence * PERCENT)}%
                  </span>
                </p>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CheckerOpinion({ rules }: { rules: RuleResult[] }) {
  return (
    <div className="space-y-2">
      <h3 className={EYEBROW_CLASS}>Checker opinion (model)</h3>
      <p className="text-xs text-muted">
        A second model reviews invoices that pass the rules. It can only send them to review, never approve.
      </p>
      <ul className="flex flex-col">
        {rules.map((rule) => (
          <li key={rule.rule_id} className={RULE_ROW_CLASS}>
            <span aria-hidden className={`text-center text-sm ${EFFECT_ROW[rule.effect].glyphColor}`}>
              {EFFECT_ROW[rule.effect].glyph}
            </span>
            <div className="min-w-0 space-y-0.5">
              {rule.evidence.question && <p className="text-xs text-muted">{rule.evidence.question}</p>}
              <p className="text-sm text-ink">{rule.reason}</p>
              {rule.evidence.probability && (
                <p className="text-xs text-muted tabular-nums">probability {rule.evidence.probability}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DuplicateLink({
  originalBillId,
  onSelectEmail,
}: {
  originalBillId: string;
  onSelectEmail: (emailId: string) => void;
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function openOriginal() {
    setIsLoading(true);
    setMessage(null);
    try {
      const original = await api.bill(originalBillId);
      const originalEmailId = original.sources.find((source) => source.inbox_email_id)?.inbox_email_id;
      if (originalEmailId) {
        onSelectEmail(originalEmailId);
        return;
      }
      setMessage("The original invoice did not arrive by email; it was registered from chat or an upload.");
    } catch {
      setMessage("The original invoice could not be opened.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="rounded border border-line bg-panel px-4 py-3 text-sm">
      <button
        type="button"
        onClick={openOriginal}
        disabled={isLoading}
        className="rounded font-normal text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
      >
        {isLoading ? "Opening..." : "View the original invoice ›"}
      </button>
      {message && (
        <p role="alert" className="mt-1 text-muted">
          {message}
        </p>
      )}
    </div>
  );
}

function DecisionHistory({ billId }: { billId: string }) {
  const [history, setHistory] = useState<BillDecisionView[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  function loadHistory(isOpen: boolean) {
    if (!isOpen || history !== null) return;
    api
      .bill(billId)
      .then((detail) => setHistory(detail.history))
      .catch(() => setLoadError(true));
  }

  return (
    <details onToggle={(event) => loadHistory(event.currentTarget.open)} className="group">
      <summary className={DISCLOSURE_SUMMARY_CLASS}>
        <DisclosureChevron />
        Decision history
      </summary>
      <div className="mt-2" aria-live="polite">
        {loadError && <p className="text-sm text-danger">The history could not be loaded.</p>}
        {!loadError && history === null && (
          <div aria-hidden className="space-y-2">
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-sunken" />
            <div className="h-3.5 w-1/2 animate-pulse rounded bg-sunken" />
          </div>
        )}
        {history && (
          <ol className="space-y-2 border-l border-line pl-4">
            {history.map((entry) => (
              <li key={`${entry.decided_at}-${entry.actor}`} className="text-sm">
                <p className="text-ink">
                  <span className="font-medium">{ACTOR_LABELS[entry.actor]}</span> · {VERDICT_LABELS[entry.verdict]}
                  <span className="ml-2 text-xs text-muted">{formatDateTime(entry.decided_at)}</span>
                </p>
                {entry.note && <p className="text-muted">{entry.note}</p>}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  );
}

function isCheckerRule(rule: RuleResult): boolean {
  return rule.rule_id.startsWith(CHECKER_RULE_PREFIX);
}
