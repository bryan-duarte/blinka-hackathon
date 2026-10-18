import { PRIMARY_BUTTON_CLASS } from "@/components/settings/styles";
import { SOURCE_LABELS } from "@/lib/labels";
import type { DemoLaunchView, DemoScenarioView } from "@/lib/types";
import { LaunchProgress } from "./LaunchProgress";
import { DownloadIcon } from "./SelfSendCard";

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
    <li className="flex flex-col gap-2 border-t border-line py-3">
      <div className="flex items-center gap-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink">{scenario.title}</p>
          <p className="mt-0.5 text-xs text-muted">
            {SOURCE_LABELS[scenario.channel]}
            {ruleIds.length > 0 && ` · ${ruleIds.join(", ")}`}
            {!scenario.is_self_sendable && " · in-app only"}
          </p>
        </div>
        {scenario.is_self_sendable && (
          <button
            type="button"
            onClick={() => onDownload(scenario.scenario_id)}
            title={scenario.self_send_hint}
            aria-label={`Download the files for ${scenario.title}`}
            className="flex size-8 shrink-0 items-center justify-center rounded-full border border-ink bg-panel text-ink transition-colors hover:bg-ink hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            <DownloadIcon />
          </button>
        )}
        <button
          type="button"
          onClick={() => onSend(scenario.scenario_id)}
          disabled={isSendDisabled || isRunning}
          className={`${PRIMARY_BUTTON_CLASS} h-8 px-3.5 text-[13px]`}
        >
          {isRunning ? "Sending…" : "Send"}
        </button>
      </div>
      <p className="line-clamp-2 text-[13px] leading-[1.4] text-muted">{scenario.description}</p>
      <LaunchProgress launch={launch} expectations={scenario.steps} />
      {disabledHint && <p className="text-xs text-muted">{disabledHint}</p>}
    </li>
  );
}
