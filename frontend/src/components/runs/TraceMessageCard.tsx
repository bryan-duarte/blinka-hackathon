import { useState } from "react";
import { EYEBROW_CLASS, QUIET_BUTTON_CLASS } from "@/components/settings/styles";
import { TRACE_ROLE_LABELS } from "@/lib/labels";
import type { TraceMessage } from "@/lib/types";
import { JsonBlock } from "./JsonBlock";

const COLLAPSED_LINE_COUNT = 12;

export function TraceMessageCard({ message }: { message: TraceMessage }) {
  const isHighlighted = isFinalOrError(message.output_json);
  return (
    <article
      id={`trace-message-${message.index}`}
      className={`flex scroll-mt-24 flex-col gap-3 rounded-lg border bg-panel p-6 ${isHighlighted ? "border-selection bg-accent-wash" : "border-line"}`}
    >
      <p className={EYEBROW_CLASS}>
        {TRACE_ROLE_LABELS[message.role]} · #{message.index}
        {message.tool_name && ` · ${message.tool_name}`}
      </p>
      {message.role === "tool" ? (
        <ToolOutput message={message} />
      ) : (
        <>
          {message.text && <CollapsibleText text={message.text} />}
          {message.tool_calls.map((toolCall, position) => (
            <div key={`${toolCall.call_id}-${position}`} className="flex flex-col gap-2">
              <p className="font-mono text-sm text-ink">{toolCall.name}()</p>
              {Object.keys(toolCall.args).length > 0 && <JsonBlock value={toolCall.args} label="arguments" />}
            </div>
          ))}
        </>
      )}
    </article>
  );
}

function ToolOutput({ message }: { message: TraceMessage }) {
  if (message.output_json !== null) return <JsonBlock value={message.output_json} label="tool output" />;
  return <CollapsibleText text={message.text} />;
}

function CollapsibleText({ text }: { text: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const lines = text.split("\n");
  const isLong = lines.length > COLLAPSED_LINE_COUNT;
  const visibleText = isLong && !isExpanded ? lines.slice(0, COLLAPSED_LINE_COUNT).join("\n") : text;
  return (
    <div className="flex flex-col gap-2">
      <pre className="font-sans text-sm leading-[1.5] whitespace-pre-wrap break-words text-ink">{visibleText}</pre>
      {isLong && (
        <button type="button" onClick={() => setIsExpanded(!isExpanded)} className={`${QUIET_BUTTON_CLASS} self-start`}>
          {isExpanded ? "Show less" : `Show all ${lines.length} lines`}
        </button>
      )}
    </div>
  );
}

function isFinalOrError(output: TraceMessage["output_json"]): boolean {
  if (!output || Array.isArray(output)) return false;
  return output.final === true || "error" in output;
}
