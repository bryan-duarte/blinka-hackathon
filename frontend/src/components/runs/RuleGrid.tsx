import { POLICY_RULE_IDS, RULE_OUTCOME_LABELS, ruleLabel } from "@/lib/labels";
import type { RuleEventPayload, RuleOutcome } from "@/lib/types";

const RULE_CELL_CLASSES: Record<RuleOutcome, string> = {
  pass: "border-ink bg-white text-ink",
  review: "border-ink bg-sunken text-ink",
  hold: "border-ink bg-ink text-white",
};
const RULE_OUTCOME_GLYPHS: Record<RuleOutcome, string> = {
  pass: "✓",
  review: "!",
  hold: "✕",
};

export function RuleGrid({ rules }: { rules: RuleEventPayload[] }) {
  const rulesByCode = new Map(rules.map((rule) => [rule.code, rule]));
  const flaggedRules = rules.filter((rule) => rule.outcome !== "pass");
  const passedCount = rules.length - flaggedRules.length;
  return (
    <section aria-label="Payment rules" className="flex flex-col gap-3">
      <p className="text-sm">
        <span className="font-medium">Payment rules</span>
        <span className="text-muted">
          {" "}
          · {passedCount} of {POLICY_RULE_IDS.length} passed
        </span>
      </p>
      <ul className="grid grid-cols-4 gap-1 sm:grid-cols-8">
        {POLICY_RULE_IDS.map((ruleId) => (
          <RuleCell key={ruleId} ruleId={ruleId} rule={rulesByCode.get(ruleId)} />
        ))}
      </ul>
      {flaggedRules.length > 0 && (
        <ul aria-label="Rules that stopped the payment" className="flex flex-col gap-1.5 text-[13px]">
          {flaggedRules.map((rule) => (
            <li key={rule.code} className="animate-enter">
              <strong className="font-medium">
                {rule.code} {ruleLabel(rule.code)}:
              </strong>{" "}
              {rule.detail}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RuleCell({ ruleId, rule }: { ruleId: string; rule: RuleEventPayload | undefined }) {
  const label = ruleLabel(ruleId);
  if (!rule) {
    return (
      <li
        aria-label={`${ruleId} ${label}: not evaluated yet`}
        className="flex h-9 items-center justify-center rounded border border-dashed border-ash text-[11px] text-muted"
      >
        {ruleId}
      </li>
    );
  }
  const outcomeLabel = RULE_OUTCOME_LABELS[rule.outcome];
  return (
    <li
      tabIndex={0}
      title={`${ruleId} ${label}: ${rule.detail}`}
      aria-label={`${ruleId} ${label}: ${outcomeLabel}. ${rule.detail}`}
      className={`flex h-9 animate-enter items-center justify-center gap-1 rounded border text-[11px] font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${RULE_CELL_CLASSES[rule.outcome]}`}
    >
      <span aria-hidden>{RULE_OUTCOME_GLYPHS[rule.outcome]}</span>
      {ruleId}
    </li>
  );
}
