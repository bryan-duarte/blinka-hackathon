import { formatMoney, formatRate, formatToolDuration, isForeignCurrency } from "@/lib/format";
import { FX_SOURCE_LABELS, SCAN_LABELS, ruleLabel } from "@/lib/labels";
import { type ToolRun, collectToolRuns, persistedActivity } from "@/lib/runEvents";
import type {
  BillDecisionView,
  BillSourceType,
  CheckerAnswer,
  PaymentRunStatus,
  RuleResult,
  RunListItemView,
  Verdict,
} from "@/lib/types";

const TOOL_TITLES: Record<string, string> = {
  classify_document: "Classified the document",
  extract_invoice: "Read the invoice",
  register_bill: "Registered the bill",
  evaluate_rules: "Checked the payment policy",
  run_checker: "Asked for a second opinion",
  settle_decision: "Recorded the decision",
};

const RECEIVED_TITLES: Record<BillSourceType, string> = {
  email: "Received an email",
  whatsapp: "Received a WhatsApp message",
  telegram: "Received a Telegram message",
  chat: "Received a chat message",
  upload: "Received an upload",
};

const DECIDED_LABELS: Record<Verdict, string> = {
  pay: "pay it",
  hold: "hold it",
  review: "escalate to a person",
};

const EVALUATE_RULES_TOOL = "evaluate_rules";
const CHECKER_TOOL = "run_checker";
const TOOL_FINISHED_STEP = "tool_finished";
const CHECKER_RULE_PREFIX = "CHK";
const CHECKER_LABEL_PREFIX = "Checker: ";
const PERCENT = 100;

type TimelineNode = {
  key: string;
  title: string;
  detail?: string;
  isKey?: boolean;
  isError?: boolean;
  offsetMs?: number | null;
  body?: React.ReactNode;
  isCollapsible?: boolean;
};

type RunTimelineProps = {
  run: RunListItemView | null;
  runStatus: PaymentRunStatus;
  isRunning: boolean;
};

export function policyRules(decision: BillDecisionView | null): RuleResult[] {
  return decision?.rule_results.filter((rule) => !rule.rule_id.startsWith(CHECKER_RULE_PREFIX)) ?? [];
}

export function runToolRuns(runStatus: PaymentRunStatus, isRunning: boolean): ToolRun[] {
  return collectToolRuns(persistedActivity(runStatus.events), isRunning);
}

export function RunTimeline({ run, runStatus, isRunning }: RunTimelineProps) {
  const nodes = buildNodes(run, runStatus, isRunning);
  return (
    <section aria-label="Timeline" className="relative">
      <div aria-hidden className="absolute top-0 bottom-0 left-3.5 w-px bg-ink/15" />
      {nodes.length === 0 && <p className="py-4 pl-12 text-muted">No agent steps were recorded.</p>}
      <ol>
        {nodes.map((node, position) => (
          <li key={node.key}>
            <TimelineRow node={node} number={position + 1} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function TimelineRow({ node, number }: { node: TimelineNode; number: number }) {
  const row = (
    <>
      <span
        className={`relative z-1 grid size-7 place-items-center rounded-full border border-ink text-xs font-medium ${node.isKey ? "bg-ink text-white" : "bg-white"}`}
      >
        {node.isError ? <span aria-label="Failed">!</span> : number}
      </span>
      <span className="min-w-0">
        <strong className="font-medium">{node.title}</strong>
        {node.detail && <span className={node.isError ? "text-danger" : undefined}> · {node.detail}</span>}
        {node.isCollapsible && <span className="text-xs text-muted group-open:hidden"> · show</span>}
        {node.isCollapsible && <span className="hidden text-xs text-muted group-open:inline"> · hide</span>}
      </span>
      <span className="font-mono text-xs tracking-normal text-muted tabular-nums">
        {node.offsetMs != null ? formatToolDuration(node.offsetMs) : ""}
      </span>
    </>
  );
  const rowClass = "grid grid-cols-[32px_minmax(0,1fr)_auto] gap-x-4 gap-y-1 py-4";
  if (node.isCollapsible && node.body) {
    return (
      <details open className="group">
        <summary
          className={`${rowClass} cursor-pointer list-none rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink [&::-webkit-details-marker]:hidden`}
        >
          {row}
        </summary>
        <div className="mb-3 ml-12">{node.body}</div>
      </details>
    );
  }
  return (
    <div className={rowClass}>
      {row}
      {node.body && <div className="col-start-2 col-end-4">{node.body}</div>}
    </div>
  );
}

function buildNodes(run: RunListItemView | null, runStatus: PaymentRunStatus, isRunning: boolean): TimelineNode[] {
  const { decision, evidence } = runStatus;
  const firstEvent = runStatus.events[0];
  const runStartMs = firstEvent ? new Date(firstEvent.created_at).getTime() : null;
  const finishedAtByCallId = new Map(
    runStatus.events
      .filter((event) => event.step === TOOL_FINISHED_STEP && typeof event.payload.call_id === "string")
      .map((event) => [event.payload.call_id as string, new Date(event.created_at).getTime()]),
  );
  const offsetFor = (callId: string) => {
    const finishedAtMs = finishedAtByCallId.get(callId);
    return runStartMs !== null && finishedAtMs !== undefined ? finishedAtMs - runStartMs : null;
  };

  const nodes: TimelineNode[] = [];
  if (run?.channel) {
    const fileCount = evidence.filter((file) => file.role !== "archive").length;
    const senderPart = run.sender ? `from ${run.sender}` : undefined;
    const filePart = fileCount > 0 ? `with ${fileCount} ${fileCount === 1 ? "file" : "files"}` : undefined;
    nodes.push({
      key: "received",
      title: RECEIVED_TITLES[run.channel],
      detail: [senderPart, filePart].filter(Boolean).join(" ") || undefined,
      offsetMs: 0,
    });
  }
  if (evidence.length > 0) {
    nodes.push({ key: "scan", title: "Scanned for malware", detail: scanSummary(runStatus) });
  }
  for (const toolRun of runToolRuns(runStatus, isRunning)) {
    if (toolRun.tool === EVALUATE_RULES_TOOL && decision) {
      const fxNode = currencyNode(decision);
      if (fxNode) nodes.push(fxNode);
    }
    nodes.push(toolNode(toolRun, decision, offsetFor(toolRun.callId)));
  }
  if (decision) {
    nodes.push({
      key: "decided",
      title: `Decided: ${DECIDED_LABELS[decision.verdict]}.`,
      detail: decision.explanation,
      isKey: true,
      offsetMs: run?.duration_ms ?? null,
    });
  } else if (!isRunning && runStatus.error) {
    nodes.push({ key: "stopped", title: "Stopped", detail: runStatus.error, isError: true });
  }
  return nodes;
}

function toolNode(toolRun: ToolRun, decision: BillDecisionView | null, offsetMs: number | null): TimelineNode {
  const title = (toolRun.tool && TOOL_TITLES[toolRun.tool]) ?? toolRun.tool ?? "Step";
  const base: TimelineNode = {
    key: toolRun.callId,
    title,
    detail: toolRun.status === "running" ? "working" : toolRun.message,
    isError: toolRun.status === "error",
    offsetMs,
  };
  if (toolRun.tool === EVALUATE_RULES_TOOL && decision && toolRun.status === "ok") {
    const rules = policyRules(decision);
    if (rules.length === 0) return base;
    return { ...base, detail: rulesSummary(rules), isKey: true, isCollapsible: true, body: <RuleBreakdown rules={rules} /> };
  }
  if (toolRun.tool === CHECKER_TOOL && decision?.checker?.answers.length) {
    return { ...base, body: <CheckerMeters answers={decision.checker.answers} /> };
  }
  return base;
}

function currencyNode(decision: BillDecisionView): TimelineNode | null {
  const { amount, currency, amount_usd: amountUsd, fx_usd_per_unit: rate, fx_source: source } = decision;
  if (!isForeignCurrency(currency) || !currency || !amount || !amountUsd || !rate) return null;
  const sourcePart = source ? ` (${FX_SOURCE_LABELS[source]})` : "";
  return {
    key: "fx",
    title: "Converted currency",
    detail: `${formatMoney(amount, currency)} is ${formatMoney(amountUsd, "USD")} at ${formatRate(rate, currency)}${sourcePart}`,
  };
}

function scanSummary(runStatus: PaymentRunStatus): string {
  const countsByLabel = new Map<string, number>();
  for (const file of runStatus.evidence) {
    const label = SCAN_LABELS[file.scan_status];
    countsByLabel.set(label, (countsByLabel.get(label) ?? 0) + 1);
  }
  return [...countsByLabel]
    .map(([label, count]) => `${count} ${count === 1 ? "file" : "files"}, ${label}`)
    .join(" · ");
}

function rulesSummary(rules: RuleResult[]): string {
  const passed = rules.filter((rule) => rule.effect === "pass").length;
  const review = rules.filter((rule) => rule.effect === "review").length;
  const blocking = rules.filter((rule) => rule.effect === "hold").length;
  return [
    `${passed} ${passed === 1 ? "rule" : "rules"} passed`,
    review > 0 && `${review} ${review === 1 ? "needs" : "need"} a person`,
    blocking > 0 && `${blocking} ${blocking === 1 ? "blocks" : "block"} the payment`,
  ]
    .filter(Boolean)
    .join(", ");
}

function RuleBreakdown({ rules }: { rules: RuleResult[] }) {
  const flagged = rules.filter((rule) => rule.effect !== "pass");
  const passed = rules.filter((rule) => rule.effect === "pass");
  return (
    <div className="grid gap-3.5 rounded border border-line px-5 py-[18px]">
      {flagged.map((rule) => (
        <p key={rule.rule_id} className="flex items-start gap-2.5">
          <RuleIcon effect={rule.effect} />
          <span>
            <strong className="font-medium">
              {rule.rule_id} {ruleLabel(rule.rule_id)}.
            </strong>{" "}
            {rule.reason}
          </span>
        </p>
      ))}
      {passed.length > 0 && (
        <ul aria-label="Rules passed" className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-x-5 gap-y-1.5 text-[13px]">
          {passed.map((rule) => (
            <li key={rule.rule_id} className="flex items-center gap-2">
              <RuleIcon effect="pass" />
              {rule.rule_id} {ruleLabel(rule.rule_id)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RuleIcon({ effect }: { effect: RuleResult["effect"] }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-label={effect === "pass" ? "Passed" : effect === "review" ? "Needs a person" : "Blocks"}
      role="img"
      className="mt-0.5 size-4 flex-none fill-none stroke-current stroke-[1.5]"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {effect === "pass" && <path d="M5 12.5l4.5 4.5L19 7.5" />}
      {effect === "review" && (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v5M12 16h.01" />
        </>
      )}
      {effect === "hold" && (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M6.5 6.5l11 11" />
        </>
      )}
    </svg>
  );
}

function CheckerMeters({ answers }: { answers: CheckerAnswer[] }) {
  return (
    <div className="mt-2.5 grid max-w-[640px] grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
      {answers.map((answer) => {
        const label = ruleLabel(answer.question_id).replace(CHECKER_LABEL_PREFIX, "");
        return (
          <div key={answer.question_id} className="grid gap-1">
            <span className="text-xs text-muted">
              {label.charAt(0).toUpperCase() + label.slice(1)} · <span className="tabular-nums">{answer.probability.toFixed(2)}</span>
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
