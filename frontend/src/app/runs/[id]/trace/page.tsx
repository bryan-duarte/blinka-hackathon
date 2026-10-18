"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { RunHeader } from "@/components/runs/RunHeader";
import { TraceMessageCard } from "@/components/runs/TraceMessageCard";
import { EYEBROW_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import type { RunListItemView, RunTraceView } from "@/lib/types";

const COPY_FEEDBACK_MS = 1500;
const JSON_INDENT = 2;

export default function RunTracePage() {
  const { id: runId } = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunListItemView | null>(null);
  const [trace, setTrace] = useState<RunTraceView | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    let isCancelled = false;
    Promise.all([api.run(runId), api.runTrace(runId)])
      .then(([loadedRun, loadedTrace]) => {
        if (isCancelled) return;
        setRun(loadedRun);
        setTrace(loadedTrace);
      })
      .catch((error: unknown) => {
        if (isCancelled) return;
        if (error instanceof UnauthorizedError) {
          router.replace("/login");
          return;
        }
        setLoadError("The trace could not be loaded.");
      });
    return () => {
      isCancelled = true;
    };
  }, [router, runId]);

  async function copyTrace() {
    if (!trace) return;
    await navigator.clipboard.writeText(JSON.stringify(trace, null, JSON_INDENT));
    setIsCopied(true);
    window.setTimeout(() => setIsCopied(false), COPY_FEEDBACK_MS);
  }

  const toolCalls = (trace?.messages ?? []).flatMap((message) =>
    message.tool_calls.map((toolCall, position) => ({
      index: message.index,
      name: toolCall.name,
      key: `${message.index}-${position}`,
    })),
  );

  return (
    <ConsoleShell>
      <ConsoleTopBar
        title="Full LLM trace"
        caption="System prompt, task, agent turns, tool calls and outputs"
        actions={
          <button
            type="button"
            onClick={copyTrace}
            disabled={!trace?.is_available}
            className={`${SECONDARY_BUTTON_CLASS} h-9 px-4`}
          >
            {isCopied ? "Copied" : "Copy full trace (JSON)"}
          </button>
        }
      />
      <main className="flex flex-1 flex-col gap-6 px-4 py-6 md:px-8">
        <RunHeader run={run} runId={runId} links={[{ href: `/runs/${runId}`, label: "Back to summary ›" }]} />
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {loadError}
          </p>
        )}
        {trace === null && !loadError && <div aria-hidden className="h-64 animate-pulse rounded bg-sunken" />}
        {trace && !trace.is_available && (
          <p className="text-sm text-muted">
            The full trace is no longer available for this execution (the checkpoint was cleared).
          </p>
        )}
        {trace?.is_available && (
          <div className="grid gap-8 lg:grid-cols-[14rem_minmax(0,1fr)]">
            <nav aria-label="Tool calls" className="hidden lg:block">
              <div className="sticky top-6 flex flex-col gap-2">
                <p className={EYEBROW_CLASS}>Tool calls</p>
                <ol className="flex flex-col gap-1">
                  {toolCalls.map((toolCall) => (
                    <li key={toolCall.key}>
                      <a
                        href={`#trace-message-${toolCall.index}`}
                        className="block truncate rounded px-2 py-1 font-mono text-xs text-nav-ink hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
                      >
                        {toolCall.name}
                      </a>
                    </li>
                  ))}
                </ol>
              </div>
            </nav>
            <div className="flex min-w-0 flex-col gap-4">
              {trace.messages.map((message) => (
                <TraceMessageCard key={message.index} message={message} />
              ))}
            </div>
          </div>
        )}
      </main>
    </ConsoleShell>
  );
}
