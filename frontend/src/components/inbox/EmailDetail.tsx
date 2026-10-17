import { DecisionCard } from "@/components/bills/DecisionCard";
import { formatDateTime } from "@/lib/format";
import type { InboxEmailDetail, InboxEmailStatus } from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

type EmailDetailProps = {
  email: InboxEmailDetail;
  onBack: () => void;
  onDecisionChanged: () => void;
  onSelectEmail: (emailId: string) => void;
};

const DECIDED_STATUSES: ReadonlySet<InboxEmailStatus> = new Set([
  "paid",
  "held",
  "review",
  "duplicate",
]);

export function EmailDetail({ email, onBack, onDecisionChanged, onSelectEmail }: EmailDetailProps) {
  return (
    <article className="flex flex-col gap-5 p-5 md:p-7">
      <button
        type="button"
        onClick={onBack}
        className="-ml-1 self-start rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent md:hidden"
      >
        ← Volver
      </button>
      <header className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-[450] tracking-[-0.02em] text-ink">
            {email.subject || "(sin asunto)"}
          </h2>
          <StatusBadge status={email.status} />
        </div>
        <p className="text-sm text-muted">
          {email.sender}
          {email.received_at && ` · ${formatDateTime(email.received_at)}`}
        </p>
      </header>
      <ResultCard
        email={email}
        onDecisionChanged={onDecisionChanged}
        onSelectEmail={onSelectEmail}
      />
      <pre className="max-h-96 overflow-auto rounded-md border border-line bg-sunken p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap text-ink">
        {email.body || "(cuerpo vacío)"}
      </pre>
    </article>
  );
}

function ResultCard({
  email,
  onDecisionChanged,
  onSelectEmail,
}: {
  email: InboxEmailDetail;
  onDecisionChanged: () => void;
  onSelectEmail: (emailId: string) => void;
}) {
  if (PENDING_STATUSES.has(email.status)) {
    return (
      <section
        aria-live="polite"
        className="flex items-center gap-3 rounded-md border border-line bg-panel p-4 text-sm text-muted"
      >
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-line border-t-accent"
        />
        {email.status === "analyzing"
          ? "El agente está evaluando la factura contra las reglas..."
          : "Revisando el correo con guardrails..."}
      </section>
    );
  }
  if (email.status === "blocked") {
    return (
      <section className="rounded-md border border-danger/30 bg-danger-soft p-4">
        <h3 className="text-sm font-semibold text-danger">
          Bloqueado por guardrails
        </h3>
        <ul className="mt-2 space-y-1">
          {email.violations.map((violation) => (
            <li key={violation.code} className="text-sm text-ink">
              <code className="font-mono text-xs text-danger">
                {violation.code}
              </code>{" "}
              {violation.message}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">No se ejecutó ningún agente.</p>
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
      <section className="rounded-md border border-line bg-panel p-4">
        <h3 className="text-sm font-medium text-ink">Correo repetido</h3>
        <p className="mt-1 text-sm text-muted">
          Este mismo correo ya se había recibido. No se volvió a evaluar ni a pagar.
        </p>
      </section>
    );
  }
  if (email.status === "no_invoice") {
    return (
      <section className="rounded-md border border-line bg-panel p-4">
        <h3 className="text-sm font-semibold text-ink">Sin factura</h3>
        <p className="mt-1 text-sm text-muted">
          {email.error || "El agente no encontró una cuenta por pagar en este correo."}
        </p>
      </section>
    );
  }
  return (
    <section
      role="alert"
      className="rounded-md border border-danger/40 bg-panel p-4"
    >
      <h3 className="text-sm font-semibold text-danger">Error al procesar</h3>
      <p className="mt-1 text-sm text-muted">
        {email.error || "Error desconocido."}
      </p>
    </section>
  );
}
