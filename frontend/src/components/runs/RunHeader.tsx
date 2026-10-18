import Link from "next/link";
import { SourceBadge } from "@/components/inbox/SourceBadge";
import { PAGE_HEADING_CLASS } from "@/components/settings/styles";
import { formatDateTime, formatDuration } from "@/lib/format";
import type { RunListItemView } from "@/lib/types";
import { RunStatusBadge } from "./RunStatusBadge";

const LINK_CLASS =
  "rounded text-sm font-normal text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent";

type RunHeaderProps = {
  run: RunListItemView | null;
  runId: string;
  links: { href: string; label: string }[];
};

export function RunHeader({ run, runId, links }: RunHeaderProps) {
  return (
    <header className="flex flex-col gap-3 border-b border-line pb-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {run?.channel && <SourceBadge type={run.channel} showsLabel />}
        {run && <span>Started {formatDateTime(run.created_at)}</span>}
        {run?.duration_ms != null && <span>· {formatDuration(run.duration_ms)}</span>}
        <span className="font-mono text-quiet">{runId}</span>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h2 className={PAGE_HEADING_CLASS}>{run?.subject ?? "Execution"}</h2>
        {run && <RunStatusBadge status={run.status} />}
      </div>
      {run?.sender && <p className="text-sm text-muted">From {run.sender}</p>}
      {run?.error && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {run.error}
        </p>
      )}
      <nav aria-label="Execution views" className="flex flex-wrap gap-4">
        {links.map((link) => (
          <Link key={link.href} href={link.href} className={LINK_CLASS}>
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
