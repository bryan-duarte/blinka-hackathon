import { SourceBadge } from "@/components/inbox/SourceBadge";
import { PRIMARY_BUTTON_CLASS, QUIET_BUTTON_CLASS } from "@/components/settings/styles";
import type { DemoLaunchView, DemoScenarioView } from "@/lib/types";
import { LaunchProgress } from "./LaunchProgress";

type ScenarioRowProps = {
  scenario: DemoScenarioView;
  launch: DemoLaunchView | undefined;
  isSendDisabled: boolean;
  disabledHint: string | null;
  onSend: (scenarioId: string) => void;
  onDownload: (scenarioId: string) => void;
};

export function ScenarioRow({
  scenario,
  launch,
  isSendDisabled,
  disabledHint,
  onSend,
  onDownload,
}: ScenarioRowProps) {
  const isRunning = launch?.status === "running";
  const ruleIds = [...new Set(scenario.steps.flatMap((step) => step.rule_ids))];
  return (
    <li className="flex flex-col gap-2 border-t border-line py-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-ink">{scenario.title}</p>
        <SourceBadge type={scenario.channel} showsLabel />
      </div>
      <p className="text-[13px] leading-[1.4] text-muted">{scenario.description}</p>
      <div className="flex flex-wrap items-center gap-1 text-xs text-muted">
        <span>Expected:</span>
        <LaunchProgress launch={launch} expectations={scenario.steps} />
        {ruleIds.map((ruleId) => (
          <span key={ruleId} className="rounded-full bg-sunken px-2 py-0.5 text-nav-ink">
            {ruleId}
          </span>
        ))}
      </div>
      {disabledHint && <p className="text-xs text-muted">{disabledHint}</p>}
      <div className="flex items-center justify-between gap-2">
        {scenario.is_self_sendable ? (
          <button
            type="button"
            onClick={() => onDownload(scenario.scenario_id)}
            title={scenario.self_send_hint}
            className={QUIET_BUTTON_CLASS}
          >
            Files ↓
          </button>
        ) : (
          <span className="text-xs text-quiet" title={scenario.self_send_hint}>
            In-app only
          </span>
        )}
        <button
          type="button"
          onClick={() => onSend(scenario.scenario_id)}
          disabled={isSendDisabled || isRunning}
          className={`${PRIMARY_BUTTON_CLASS} h-9 px-4`}
        >
          {isRunning ? "Sending…" : "Send"}
        </button>
      </div>
    </li>
  );
}
