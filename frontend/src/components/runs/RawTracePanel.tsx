import Link from "next/link";
import { TRACE_ROLE_LABELS } from "@/lib/labels";
import type { RunTraceView, TraceMessage } from "@/lib/types";

const PREVIEW_CHAR_LIMIT = 280;

function countLabel(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function previewText(message: TraceMessage): string {
  const text = message.output_json !== null ? JSON.stringify(message.output_json) : message.text;
  return text.length > PREVIEW_CHAR_LIMIT ? `${text.slice(0, PREVIEW_CHAR_LIMIT)}...` : text;
}

function previewMessages(messages: TraceMessage[]): TraceMessage[] {
  const task = messages.find((message) => message.role === "human");
  const lastTool = messages.findLast((message) => message.role === "tool");
  const lastAgent = messages.findLast((message) => message.role === "ai" && message.text.trim() !== "");
  return [task, lastTool, lastAgent].filter((message): message is TraceMessage => message !== undefined);
}

export function RawTracePanel({ runId, trace }: { runId: string; trace: RunTraceView | null | undefined }) {
  const messages = trace?.messages ?? [];
  const toolCallCount = messages.reduce((total, message) => total + message.tool_calls.length, 0);
  const caption = !trace
    ? "For engineers and auditors."
    : trace.is_available
      ? `For engineers and auditors. ${countLabel(messages.length, "message")}, ${countLabel(toolCallCount, "tool call")}.`
      : "The full trace is no longer available for this run.";
  return (
    <section aria-labelledby="raw-trace-title" className="mt-auto flex flex-col gap-4 bg-carbon p-8 text-white">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="raw-trace-title" className="font-serif text-[26px] leading-[1.13]">
          Raw trace
        </h2>
        <span className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[13px] text-muted">
          {caption}
          {trace?.is_available && (
            <Link
              href={`/runs/${runId}/trace`}
              className="rounded text-white hover:text-iris hover:underline hover:underline-offset-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              Open the full trace <span aria-hidden>→</span>
            </Link>
          )}
        </span>
      </div>
      {trace === undefined && (
        <div aria-hidden className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-3">
          {[0, 1, 2].map((card) => (
            <div key={card} className="h-24 animate-pulse rounded bg-graphite" />
          ))}
        </div>
      )}
      {trace?.is_available && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-3">
          {previewMessages(messages).map((message) => (
            <div key={message.index} className="flex flex-col gap-2 rounded bg-graphite px-[18px] py-4">
              <span className="text-xs text-white/66">
                {TRACE_ROLE_LABELS[message.role]}
                {message.tool_name && ` · ${message.tool_name}`}
              </span>
              <span className="font-mono text-xs leading-[1.6] tracking-normal break-words">{previewText(message)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
