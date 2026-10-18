import { ruleLabel } from "@/lib/labels";

const CHECKER_LABEL_PREFIX = "Checker: ";
const PERCENT = 100;

export type CheckerMeter = {
  questionId: string;
  probability: number;
};

export function CheckerMeters({ answers }: { answers: CheckerMeter[] }) {
  return (
    <div className="mt-2.5 grid max-w-[640px] grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
      {answers.map((answer) => {
        const label = ruleLabel(answer.questionId).replace(CHECKER_LABEL_PREFIX, "");
        return (
          <div key={answer.questionId} className="grid gap-1">
            <span className="text-xs text-muted">
              {label.charAt(0).toUpperCase() + label.slice(1)} ·{" "}
              <span className="tabular-nums">{answer.probability.toFixed(2)}</span>
            </span>
            <span className="h-1.5 overflow-hidden rounded-full bg-sunken">
              <span className="block h-full bg-ink" style={{ width: `${answer.probability * PERCENT}%` }} />
            </span>
          </div>
        );
      })}
    </div>
  );
}
