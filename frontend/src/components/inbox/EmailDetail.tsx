import Link from "next/link";
import { DecisionCard, DecisionHistory } from "@/components/bills/DecisionCard";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { IntakeChecks } from "@/components/runs/StageRail";
import { EYEBROW_CLASS, PAGE_HEADING_CLASS, PRIMARY_BUTTON_CLASS } from "@/components/settings/styles";
import { formatDateTime } from "@/lib/format";
import { maskEmailsIn } from "@/lib/mask";
import type { InboxEmailDetail, InboxEmailStatus, RealtimeEvent } from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";
import { collectStages } from "@/lib/runEvents";
import { AgentActivity } from "./AgentActivity";
import { SourceBadge } from "./SourceBadge";
import { StatusBadge } from "./StatusBadge";

type EmailDetailProps = {
  email: InboxEmailDetail;
  onBack: () => void;
  onSelectEmail: (emailId: string) => void;
  runEvents: RealtimeEvent[];
  stageEvents: RealtimeEvent[];
  thinking: string;
  refreshKey: number;
};

const DECIDED_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "paid",
  "held",
  "review",
  "duplicate",
]);

const RUN_HEADLINES: Record<InboxEmailStatus, string> = {
  received: "Checking the message",
  processing: "Checking the message",
  analyzing: "The agent is deciding",
  paid: "Paid",
  held: "Held",
  review: "Escalated to a person",
  duplicate: "Duplicate",
  blocked: "Blocked before evaluation",
  no_invoice: "Not an invoice",
  no_info: "No readable data",
  error: "Processing error",
};

const PENDING_EXPLANATIONS: Partial<Record<InboxEmailStatus, string>> = {
  received: "Scanning the documents with AWS before the agent reads them.",
  processing: "Scanning the documents with AWS before the agent reads them.",
  analyzing: "The agent is checking the invoice against the payment rules.",
};

export function EmailDetail({
  email,
  onBack,
  onSelectEmail,
  runEvents,
  stageEvents,
  thinking,
  refreshKey,
}: EmailDetailProps) {
  const isPending = PENDING_STATUSES.has(email.status);
  const stages = collectStages(email.pipeline_stages, stageEvents);
  const decision = DECIDED_STATUSES.has(email.status) ? email.decision : null;
  const headline = decision?.status === "rejected" ? "Rejected by a person" : RUN_HEADLINES[email.status];
  return (
    <article className="grid min-w-0 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <section
        aria-label="Message"
        className="flex min-w-0 flex-col gap-5 border-b border-line p-6 xl:border-r xl:border-b-0"
      >
        <button
          type="button"
          onClick={onBack}
          className="-ml-1 self-start rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent md:hidden"
        >
          ← Back
        </button>
        <header className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex items-center gap-2 text-xs text-muted">
              <SourceBadge type={email.source_type} showsLabel />
              {email.received_at && <span>· {formatDateTime(email.received_at)}</span>}
            </span>
            <StatusBadge status={email.status} />
          </div>
          <h2 className={PAGE_HEADING_CLASS}>{email.subject || "(no subject)"}</h2>
          <p className="text-[13px] break-words text-muted">{maskEmailsIn(email.sender) || "Unknown sender"}</p>
        </header>
        <pre className="max-h-80 overflow-auto font-sans text-sm leading-[1.5] whitespace-pre-wrap text-ink">
          {email.body || "(empty body)"}
        </pre>
        <EvidenceSection evidence={email.evidence} />
      </section>

      <section aria-label="Agent run" className="flex min-w-0 flex-col gap-6 p-6 xl:px-8">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className={`${EYEBROW_CLASS} flex items-center gap-2`}>
              Agent run
              {isPending && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-ink px-2 py-0.5 text-[11px] text-white [font-variant-caps:normal]">
                  <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-white" />
                  Live
                </span>
              )}
            </p>
            <h3 aria-live="polite" className="font-serif text-[38px] leading-[1.15] text-ink">
              {headline}
            </h3>
          </div>
          {decision?.can_approve && (
            <Link href={`/bills?bill=${decision.bill_id}`} className={`${PRIMARY_BUTTON_CLASS} no-underline`}>
              Decide <span aria-hidden>→</span>
            </Link>
          )}
        </header>
        {isPending && <p className="text-base leading-[1.5] text-muted">{PENDING_EXPLANATIONS[email.status]}</p>}
        {decision && <DecisionCard decision={decision} onSelectEmail={onSelectEmail} isCompact={email.run_id !== null} />}
        <RunOutcomeNote email={email} />
        {email.run_id ? (
          <AgentActivity
            runId={email.run_id}
            liveEvents={runEvents}
            stages={stages}
            thinking={thinking}
            isRunning={isPending}
            refreshKey={refreshKey}
          />
        ) : (
          stages.length > 0 && <IntakeChecks stages={stages} />
        )}
        {decision && email.run_id && <DecisionHistory billId={decision.bill_id} />}
      </section>
    </article>
  );
}

function RunOutcomeNote({ email }: { email: InboxEmailDetail }) {
  if (PENDING_STATUSES.has(email.status)) return null;
  if (DECIDED_STATUSES.has(email.status) && email.decision) return null;
  if (email.status === "blocked") {
    return (
      <section className="flex flex-col gap-2">
        <ul className="flex flex-col gap-1">
          {email.violations.map((violation) => (
            <li key={violation.code} className="text-sm text-ink">
              <code className="font-mono text-xs text-danger">{violation.code}</code> {violation.message}
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">No agent was run.</p>
      </section>
    );
  }
  if (email.status === "duplicate") {
    return (
      <p className="text-base leading-[1.5] text-muted">
        This same message was already received. It was not evaluated or paid again.
      </p>
    );
  }
  if (email.status === "no_info") {
    return (
      <p className="text-base leading-[1.5] text-muted">
        The invoice details could not be read. No extraction method produced data, so the agent did not make a
        decision.
      </p>
    );
  }
  if (email.status === "no_invoice") {
    return (
      <p className="text-base leading-[1.5] text-muted">
        {email.error || "The agent found no bill to pay in this message."}
      </p>
    );
  }
  return (
    <p role="alert" className="text-base leading-[1.5] text-danger">
      <span aria-hidden>✕ </span>
      {email.error || "Unknown error."}
    </p>
  );
}
