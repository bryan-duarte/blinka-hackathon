import Link from "next/link";
import { SourceBadge } from "@/components/inbox/SourceBadge";
import { formatDateTime, formatDuration, formatRelative } from "@/lib/format";
import { VERDICT_LABELS } from "@/lib/labels";
import type { RunListItemView } from "@/lib/types";
import { RunStatusBadge } from "./RunStatusBadge";

export function RunsTable({ runs }: { runs: RunListItemView[] | null }) {
  if (runs === null) {
    return (
      <ul aria-hidden className="divide-y divide-line">
        {[0, 1, 2, 3].map((row) => (
          <li key={row} className="px-6 py-4">
            <div className="h-3.5 w-2/3 animate-pulse rounded bg-sunken" />
          </li>
        ))}
      </ul>
    );
  }
  if (runs.length === 0) {
    return (
      <p className="px-6 py-12 text-sm text-muted">No executions yet. Send a demo scenario from the inbox.</p>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {runs.map((run) => (
        <li key={run.run_id}>
          <Link
            href={`/runs/${run.run_id}`}
            className="grid gap-2 px-6 py-4 transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent md:grid-cols-[8rem_7rem_minmax(0,1fr)_7rem_4rem_5rem_1rem] md:items-center md:gap-4"
          >
            <span className="text-xs text-muted" title={formatDateTime(run.created_at)}>
              {formatRelative(run.created_at)}
            </span>
            <span>
              <RunStatusBadge status={run.status} />
            </span>
            <span className="flex min-w-0 items-center gap-2">
              {run.channel && <SourceBadge type={run.channel} />}
              <span className="min-w-0">
                <span className="block truncate text-sm text-ink">{run.subject ?? "(no subject)"}</span>
                <span className="block truncate text-xs text-muted">{run.sender ?? run.error ?? ""}</span>
              </span>
            </span>
            <span className="text-sm text-ink">{run.verdict ? VERDICT_LABELS[run.verdict] : "No decision"}</span>
            <span className="text-xs text-muted tabular-nums">{run.tool_count} tools</span>
            <span className="text-xs text-muted tabular-nums">
              {run.duration_ms !== null ? formatDuration(run.duration_ms) : "..."}
            </span>
            <span aria-hidden className="hidden text-muted md:block">
              ›
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
