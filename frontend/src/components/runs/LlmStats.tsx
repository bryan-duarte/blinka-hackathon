import { formatToolDuration } from "@/lib/format";
import type { LlmCallTotals } from "@/lib/runEvents";

const tokenFormatter = new Intl.NumberFormat("en-US");

export function LlmStats({ totals }: { totals: LlmCallTotals }) {
  if (totals.calls.length === 0) return null;
  const callWord = totals.calls.length === 1 ? "model call" : "model calls";
  return (
    <details className="group text-xs text-muted">
      <summary className="cursor-pointer list-none rounded tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink [&::-webkit-details-marker]:hidden">
        {totals.calls.length} {callWord} · {tokenFormatter.format(totals.inputTokens)} in /{" "}
        {tokenFormatter.format(totals.outputTokens)} out tokens · {formatToolDuration(totals.totalMs)}
        <span className="group-open:hidden"> · show</span>
        <span className="hidden group-open:inline"> · hide</span>
      </summary>
      <ol className="mt-2 flex flex-col gap-1 font-mono tracking-normal tabular-nums">
        {totals.calls.map((call, position) => (
          <li key={position} className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3">
            <span className="truncate">
              {call.parent_tool ?? call.node} · {call.model}
            </span>
            <span>
              {tokenFormatter.format(call.input_tokens)}/{tokenFormatter.format(call.output_tokens)}
            </span>
            <span>{formatToolDuration(call.duration_ms)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}
