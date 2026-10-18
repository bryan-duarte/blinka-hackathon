import type { ReactNode } from "react";
import { DecisionCard } from "@/components/bills/DecisionCard";
import { EvidenceSection } from "@/components/files/EvidenceSection";
import { EYEBROW_CLASS, PAGE_HEADING_CLASS } from "@/components/settings/styles";
import { formatDateTime } from "@/lib/format";
import type { InboxEmailDetail, InboxEmailStatus, RealtimeEvent } from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";
import { AgentActivity } from "./AgentActivity";
import { SourceBadge } from "./SourceBadge";
import { StatusBadge } from "./StatusBadge";

type EmailDetailProps = {
  email: InboxEmailDetail;
  onBack: () => void;
  onDecisionChanged: () => void;
  onSelectEmail: (emailId: string) => void;
  runEvents: RealtimeEvent[];
  thinking: string;
  refreshKey: number;
};

const DECIDED_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "paid",
  "held",
  "review",
  "duplicate",
]);

const NOTICE_CLASS = "flex flex-col gap-2 border-t border-line pt-4";
const NOTICE_TITLE_CLASS = "text-base font-normal";

export function EmailDetail({
  email,
  onBack,
  onDecisionChanged,
  onSelectEmail,
  runEvents,
  thinking,
  refreshKey,
}: EmailDetailProps) {
  const isPending = PENDING_STATUSES.has(email.status);
  const agentActivity = email.run_id ? (
    <AgentActivity
      runId={email.run_id}
      liveEvents={runEvents}
      thinking={thinking}
      isRunning={isPending}
      refreshKey={refreshKey}
    />
  ) : null;
  return (
    <article className="flex flex-col gap-6">
      <button
        type="button"
        onClick={onBack}
        className="-ml-1 self-start rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent md:hidden"
      >
        ← Volver
      </button>
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <SourceBadge type={email.source_type} showsLabel />
          <p className={EYEBROW_CLASS}>
            {email.sender}
            {email.received_at && ` · ${formatDateTime(email.received_at)}`}
          </p>
        </div>
        <div className="flex items-start justify-between gap-4">
          <h2 className={PAGE_HEADING_CLASS}>{email.subject || "(sin asunto)"}</h2>
          <StatusBadge status={email.status} />
        </div>
      </header>
      {!isPending && agentActivity}
      <ResultCard
        email={email}
        agentActivity={agentActivity}
        onDecisionChanged={onDecisionChanged}
        onSelectEmail={onSelectEmail}
      />
      <pre className="max-h-96 overflow-auto rounded border border-line bg-panel p-4 font-sans text-sm leading-[1.4] whitespace-pre-wrap text-ink">
        {email.body || "(cuerpo vacío)"}
      </pre>
      <EvidenceSection evidence={email.evidence} />
    </article>
  );
}

function ResultCard({
  email,
  agentActivity,
  onDecisionChanged,
  onSelectEmail,
}: {
  email: InboxEmailDetail;
  agentActivity: ReactNode;
  onDecisionChanged: () => void;
  onSelectEmail: (emailId: string) => void;
}) {
  if (PENDING_STATUSES.has(email.status)) {
    return (
      <section aria-live="polite" className="flex flex-col gap-2 border-t border-line pt-4 text-sm text-muted">
        <div aria-hidden className="h-1 w-full animate-pulse rounded bg-accent-wash" />
        {email.status === "analyzing"
          ? "El agente está evaluando la factura contra las reglas…"
          : "Revisando el mensaje y escaneando documentos con AWS…"}
        {agentActivity}
      </section>
    );
  }
  if (email.status === "blocked") {
    return (
      <section className={NOTICE_CLASS}>
        <h3 className={`${NOTICE_TITLE_CLASS} text-danger`}>
          <span aria-hidden>✕ </span>Bloqueado antes de evaluar
        </h3>
        <ul className="flex flex-col gap-1">
          {email.violations.map((violation) => (
            <li key={violation.code} className="text-sm text-ink">
              <code className="font-mono text-xs text-danger">
                {violation.code}
              </code>{" "}
              {violation.message}
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">No se ejecutó ningún agente.</p>
      </section>
    );
  }
  if (DECIDED_STATUSES.has(email.status) && email.decision) {
    return (
      <DecisionCard
        decision={email.decision}
        onResolved={onDecisionChanged}
        onSelectEmail={onSelectEmail}
      />
    );
  }
  if (email.status === "duplicate") {
    return (
      <section className={NOTICE_CLASS}>
        <h3 className={`${NOTICE_TITLE_CLASS} text-ink`}>Mensaje repetido</h3>
        <p className="text-sm text-muted">
          Este mismo mensaje ya se había recibido. No se volvió a evaluar ni a pagar.
        </p>
      </section>
    );
  }
  if (email.status === "no_info") {
    return (
      <section className={NOTICE_CLASS}>
        <h3 className={`${NOTICE_TITLE_CLASS} text-ink`}>
          <span aria-hidden>! </span>Sin datos legibles
        </h3>
        <p className="text-sm text-muted">
          No se pudo leer la información de la factura. Ningún método de extracción produjo datos, así
          que el agente no tomó una decisión.
        </p>
      </section>
    );
  }
  if (email.status === "no_invoice") {
    return (
      <section className={NOTICE_CLASS}>
        <h3 className={`${NOTICE_TITLE_CLASS} text-ink`}>Sin factura</h3>
        <p className="text-sm text-muted">
          {email.error || "El agente no encontró una cuenta por pagar en este mensaje."}
        </p>
      </section>
    );
  }
  return (
    <section role="alert" className={NOTICE_CLASS}>
      <h3 className={`${NOTICE_TITLE_CLASS} text-danger`}>
        <span aria-hidden>✕ </span>Error al procesar
      </h3>
      <p className="text-sm text-muted">
        {email.error || "Error desconocido."}
      </p>
    </section>
  );
}
