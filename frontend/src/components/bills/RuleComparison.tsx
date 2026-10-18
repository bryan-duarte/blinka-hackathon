import { ruleLabel } from "@/lib/labels";
import type { RuleEffect, RuleResult } from "@/lib/types";

const EFFECT_ORDER: Record<RuleEffect, number> = { hold: 0, review: 1, pass: 2 };

const RESULT_TAGS: Record<RuleEffect, { label: string; className: string }> = {
  hold: { label: "✕ Blocks", className: "bg-ink text-white" },
  review: { label: "! Needs you", className: "border border-ink text-ink" },
  pass: { label: "✓ Passes", className: "bg-sunken text-ink" },
};

const HEADER_CELL_CLASS = "border-b border-ink px-4 py-3 text-left text-xs font-medium text-muted";
const CELL_CLASS = "border-b border-line px-4 py-3.5 align-top text-sm";

export function RuleComparison({ rules }: { rules: RuleResult[] }) {
  const flaggedRules = rules
    .filter((rule) => rule.effect !== "pass")
    .sort((first, second) => EFFECT_ORDER[first.effect] - EFFECT_ORDER[second.effect]);
  const passedRules = rules.filter((rule) => rule.effect === "pass");
  return (
    <section aria-label="Rule checks" className="flex flex-col gap-3">
      {flaggedRules.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[560px] border-collapse">
            <thead>
              <tr>
                <th scope="col" className={`${HEADER_CELL_CLASS} w-[30%]`}>
                  Check
                </th>
                <th scope="col" className={HEADER_CELL_CLASS}>
                  What the agent found
                </th>
                <th scope="col" className={`${HEADER_CELL_CLASS} w-28`}>
                  Result
                </th>
              </tr>
            </thead>
            <tbody>
              {flaggedRules.map((rule) => (
                <RuleRow key={rule.rule_id} rule={rule} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {passedRules.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer list-none rounded text-sm text-muted select-none hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink [&::-webkit-details-marker]:hidden">
            <span aria-hidden className="mr-1.5 inline-block transition-transform group-open:rotate-90">
              ›
            </span>
            {passedRules.length} rules passed
          </summary>
          <div className="mt-3 overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[560px] border-collapse">
              <tbody>
                {passedRules.map((rule) => (
                  <RuleRow key={rule.rule_id} rule={rule} />
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}

function RuleRow({ rule }: { rule: RuleResult }) {
  const tag = RESULT_TAGS[rule.effect];
  const evidenceEntries = Object.entries(rule.evidence);
  const isFlagged = rule.effect !== "pass";
  return (
    <tr className={isFlagged ? "bg-route-wash" : undefined}>
      <td className={`${CELL_CLASS} w-[30%]`}>
        <span className={isFlagged ? "font-medium" : undefined}>{ruleLabel(rule.rule_id)}</span>
        <span className="block text-xs text-muted">{rule.rule_id}</span>
      </td>
      <td className={CELL_CLASS}>
        <span className="leading-[1.5]">{rule.reason}</span>
        {evidenceEntries.length > 0 && (
          <span className="mt-1 block text-xs break-words text-muted">
            {evidenceEntries.map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")}
          </span>
        )}
      </td>
      <td className={`${CELL_CLASS} w-28`}>
        <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs whitespace-nowrap ${tag.className}`}>
          {tag.label}
        </span>
      </td>
    </tr>
  );
}
