import { INBOX_STATUS_LABELS } from "@/lib/labels";
import type { DemoExpectation, DemoLaunchStepView, DemoLaunchView } from "@/lib/types";

const CHIP_CLASS = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-normal";
const PENDING_CHIP = `${CHIP_CLASS} bg-sunken text-muted`;
const MATCHED_CHIP = `${CHIP_CLASS} bg-sunken text-nav-ink`;
const MISMATCHED_CHIP = `${CHIP_CLASS} border border-night bg-panel text-night`;

type LaunchProgressProps = {
  launch: DemoLaunchView | undefined;
  expectations: DemoExpectation[];
};

export function LaunchProgress({ launch, expectations }: LaunchProgressProps) {
  return (
    <div className="flex flex-col gap-1">
      <ol aria-label="Steps" className="flex flex-wrap gap-1">
        {expectations.map((expectation, index) => (
          <li key={index}>
            <StepChip index={index} expectation={expectation} step={launch?.steps[index]} />
          </li>
        ))}
      </ol>
      {launch?.status === "failed" && (
        <p role="alert" className="text-xs text-danger">
          <span aria-hidden>✕ </span>
          {launch.error ?? "The sequence stopped."}
        </p>
      )}
      {launch?.status === "cancelled" && <p className="text-xs text-muted">Cancelled by a reset.</p>}
    </div>
  );
}

function StepChip({
  index,
  expectation,
  step,
}: {
  index: number;
  expectation: DemoExpectation;
  step: DemoLaunchStepView | undefined;
}) {
  const stepLabel = `Step ${index + 1}`;
  const expectedLabel = INBOX_STATUS_LABELS[expectation.outcome];
  if (!step?.status) {
    return <span className={PENDING_CHIP}>{`${stepLabel} · ${expectedLabel}`}</span>;
  }
  if (step.is_as_expected === null) {
    return (
      <span className={PENDING_CHIP}>
        {`${stepLabel} · Waiting`}
        <span aria-hidden className="animate-pulse">
          …
        </span>
      </span>
    );
  }
  if (step.is_as_expected) {
    return (
      <span className={MATCHED_CHIP}>
        {`${stepLabel} · ${INBOX_STATUS_LABELS[step.status]}`}
        <span aria-hidden> ✓</span>
      </span>
    );
  }
  return (
    <span className={MISMATCHED_CHIP}>
      <span aria-hidden>✕ </span>
      {`${stepLabel} · expected ${expectedLabel}, got ${INBOX_STATUS_LABELS[step.status]}`}
    </span>
  );
}
