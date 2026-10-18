import { formatToolDuration } from "@/lib/format";
import { type AgentPhase, INTAKE_SCAN_LABELS, PHASE_LABELS, STAGE_LABELS } from "@/lib/labels";
import type { ToolRun } from "@/lib/runEvents";
import type { PipelineStageRecord } from "@/lib/types";

type PhaseStatus = "done" | "active" | "pending" | "error";

type PhaseView = {
  phase: AgentPhase;
  status: PhaseStatus;
  durationMs: number | null;
};

const AGENT_PHASE_BY_TOOL: Record<string, AgentPhase> = {
  classify_document: "classify",
  extract_invoice: "extract",
  register_bill: "register",
  evaluate_rules: "rules",
  run_checker: "checker",
  settle_decision: "settle",
};
const AGENT_PHASES: AgentPhase[] = ["classify", "extract", "register", "rules", "checker", "settle"];
const TOOL_STATUS_PHASES: Record<ToolRun["status"], PhaseStatus> = {
  running: "active",
  ok: "done",
  error: "error",
};
const PHASE_DOT_CLASSES: Record<PhaseStatus, string> = {
  done: "border-ink bg-ink",
  active: "border-ink bg-white animate-pulse",
  pending: "border-ash bg-white",
  error: "border-ink bg-white",
};
const PHASE_STATUS_LABELS: Record<PhaseStatus, string> = {
  done: "done",
  active: "in progress",
  pending: "not started",
  error: "failed",
};

type StageRailProps = {
  stages: PipelineStageRecord[];
  toolRuns: ToolRun[];
};

export function StageRail({ stages, toolRuns }: StageRailProps) {
  const phases = [intakePhase(stages), ...AGENT_PHASES.map((phase) => agentPhase(phase, toolRuns))];
  return (
    <section aria-label="Progress" className="flex flex-col gap-3">
      <ol className="grid grid-cols-7 gap-1">
        {phases.map((phaseView) => (
          <PhaseCell key={phaseView.phase} phaseView={phaseView} />
        ))}
      </ol>
      {stages.length > 0 && <IntakeChecks stages={stages} />}
    </section>
  );
}

export function IntakeChecks({ stages }: { stages: PipelineStageRecord[] }) {
  return (
    <ul aria-label="Intake checks" className="flex flex-col gap-1 text-[13px]">
      {stages.map((stage) => (
        <li key={stage.stage} className="flex items-baseline justify-between gap-4">
          <span className={stage.status === "failed" ? "text-danger" : "text-ink"}>
            {STAGE_LABELS[stage.stage]}
            {stageDetail(stage) && <span className="text-muted"> · {stageDetail(stage)}</span>}
            {stage.status === "started" && <span className="text-muted"> · working</span>}
          </span>
          {stage.duration_ms !== null && (
            <span className="shrink-0 font-mono text-xs tracking-normal text-muted tabular-nums">
              {formatToolDuration(stage.duration_ms)}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function PhaseCell({ phaseView }: { phaseView: PhaseView }) {
  const isPending = phaseView.status === "pending";
  return (
    <li className="flex min-w-0 flex-col items-center gap-1 text-center">
      <span
        aria-hidden
        className={`grid size-3 place-items-center rounded-full border text-[9px] leading-none ${PHASE_DOT_CLASSES[phaseView.status]}`}
      >
        {phaseView.status === "error" ? "!" : null}
      </span>
      <span className={`w-full truncate text-xs ${isPending ? "text-muted" : "text-ink"}`}>
        {PHASE_LABELS[phaseView.phase]}
        <span className="sr-only">: {PHASE_STATUS_LABELS[phaseView.status]}</span>
      </span>
      <span className="font-mono text-[11px] tracking-normal text-muted tabular-nums">
        {phaseView.durationMs !== null ? formatToolDuration(phaseView.durationMs) : " "}
      </span>
    </li>
  );
}

function intakePhase(stages: PipelineStageRecord[]): PhaseView {
  const durationMs = stages.reduce((total, stage) => total + (stage.duration_ms ?? 0), 0);
  const hasFailed = stages.some((stage) => stage.status === "failed");
  const isHandedOff = stages.some((stage) => stage.stage === "handoff" && stage.status === "finished");
  const status: PhaseStatus = hasFailed ? "error" : isHandedOff ? "done" : stages.length > 0 ? "active" : "pending";
  return { phase: "intake", status, durationMs: durationMs > 0 ? durationMs : null };
}

function agentPhase(phase: AgentPhase, toolRuns: ToolRun[]): PhaseView {
  const toolRun = toolRuns.findLast((candidate) => candidate.tool && AGENT_PHASE_BY_TOOL[candidate.tool] === phase);
  if (!toolRun) return { phase, status: "pending", durationMs: null };
  return { phase, status: TOOL_STATUS_PHASES[toolRun.status], durationMs: toolRun.durationMs };
}

function stageDetail(stage: PipelineStageRecord): string | null {
  const { detail } = stage;
  if (stage.stage === "malware_scan" && typeof detail.files === "number") {
    const fileWord = detail.files === 1 ? "file" : "files";
    const scanLabel = INTAKE_SCAN_LABELS[String(detail.scan_status)] ?? null;
    return [`${detail.files} ${fileWord}`, scanLabel].filter(Boolean).join(", ");
  }
  if (stage.stage === "guardrail" && typeof detail.guardrail_action === "string") {
    return detail.guardrail_action;
  }
  if (stage.stage === "dedup" && typeof detail.duplicate === "boolean") {
    return detail.duplicate ? "already received" : "new";
  }
  return null;
}
