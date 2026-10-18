import { formatToolDuration } from "@/lib/format";
import { TODO_STATUS_LABELS } from "@/lib/labels";
import { collectToolRuns, latestSummary, latestTodos, persistedActivity } from "@/lib/runEvents";
import type { PaymentRunEvent } from "@/lib/types";
import { EYEBROW_CLASS } from "@/components/settings/styles";

const TOOL_TITLES: Record<string, string> = {
  classify_document: "Classify document",
  extract_invoice: "Extract invoice",
  register_bill: "Register bill",
  evaluate_rules: "Evaluate rules",
  run_checker: "Second review",
  settle_decision: "Record decision",
};

export function RunTimeline({ events, isRunning }: { events: PaymentRunEvent[]; isRunning: boolean }) {
  const activity = persistedActivity(events);
  const todos = latestTodos(activity);
  const toolRuns = collectToolRuns(activity, isRunning);
  const summary = latestSummary(activity);
  return (
    <section aria-labelledby="run-steps-title" className="flex flex-col gap-6">
      {todos.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className={EYEBROW_CLASS}>Plan</h2>
          <ul className="flex flex-col gap-1">
            {todos.map((todo, index) => (
              <li key={`${index}-${todo.content}`} className="text-sm text-ink">
                <span className="text-muted">{TODO_STATUS_LABELS[todo.status]} · </span>
                {todo.content}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-col gap-2">
        <h2 id="run-steps-title" className={EYEBROW_CLASS}>
          Steps
        </h2>
        {toolRuns.length === 0 && <p className="text-sm text-muted">No agent steps were recorded.</p>}
        <ol className="flex flex-col border-l border-line">
          {toolRuns.map((toolRun) => (
            <li key={toolRun.callId} className="flex flex-col gap-1 py-2 pl-4">
              <p className="flex flex-wrap items-baseline justify-between gap-x-4 text-sm">
                <span className={toolRun.status === "error" ? "text-danger" : "text-ink"}>
                  <span aria-hidden>{toolRun.status === "error" ? "✕ " : toolRun.status === "ok" ? "✓ " : "… "}</span>
                  {(toolRun.tool && TOOL_TITLES[toolRun.tool]) ?? toolRun.tool ?? "Step"}
                </span>
                {toolRun.durationMs !== null && (
                  <span className="text-xs text-muted tabular-nums">{formatToolDuration(toolRun.durationMs)}</span>
                )}
              </p>
              <p className="text-xs text-muted">{toolRun.message}</p>
              {toolRun.summary && (
                <details className="group">
                  <summary className="cursor-pointer list-none text-xs text-muted select-none hover:text-ink [&::-webkit-details-marker]:hidden">
                    <span aria-hidden className="mr-1 inline-block transition-transform group-open:rotate-90">
                      ›
                    </span>
                    Output summary
                  </summary>
                  <p className="mt-1 font-mono text-xs break-words text-nav-ink">{toolRun.summary}</p>
                  <p className="mt-1 text-xs text-muted">The full output is on the trace page.</p>
                </details>
              )}
            </li>
          ))}
        </ol>
      </div>
      {summary && (
        <div className="flex flex-col gap-2">
          <h2 className={EYEBROW_CLASS}>Agent summary</h2>
          <p className="text-sm leading-[1.4] text-ink">{summary}</p>
        </div>
      )}
    </section>
  );
}
