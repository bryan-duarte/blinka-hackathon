import { formatMoney, formatRelative, isForeignCurrency } from "@/lib/format";
import type { InboxEmailView } from "@/lib/types";
import { SourceBadge } from "./SourceBadge";
import { StatusBadge } from "./StatusBadge";

type EmailListProps = {
  emails: InboxEmailView[];
  selectedEmailId: string | null;
  onSelect: (emailId: string) => void;
};

export function EmailList({ emails, selectedEmailId, onSelect }: EmailListProps) {
  if (emails.length === 0) {
    return (
      <div className="px-6 py-12">
        <p className="text-sm font-normal text-ink">Tu bandeja está vacía</p>
        <p className="mt-1 text-sm text-muted">
          Conecta un correo o usa &quot;Simular correo&quot; para ver cómo el
          agente decide.
        </p>
      </div>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {emails.map((email) => {
        const isSelected = email.email_id === selectedEmailId;
        const decision = email.decision;
        const showsUsdEquivalent = decision?.amount_usd != null && isForeignCurrency(decision.currency);
        return (
          <li key={email.email_id}>
            <button
              type="button"
              aria-current={isSelected}
              onClick={() => onSelect(email.email_id)}
              className={`block w-full border-l-2 px-6 py-4 text-left transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent ${isSelected ? "border-accent bg-route-wash" : "border-transparent hover:bg-sunken"}`}
            >
              <div className="flex items-baseline justify-between gap-4">
                <span className="flex min-w-0 items-center gap-2">
                  <SourceBadge type={email.source_type} />
                  <span className={`truncate text-sm font-normal ${isSelected ? "text-accent" : "text-ink"}`}>
                    {email.sender || "Remitente desconocido"}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {email.received_at
                    ? formatRelative(email.received_at)
                    : "simulado"}
                </span>
              </div>
              <p className="mt-1 truncate text-sm text-ink">
                {email.subject || "(sin asunto)"}
              </p>
              <p className="mt-1 truncate text-xs text-muted">
                {email.preview}
              </p>
              <div className="mt-2 flex items-center justify-between gap-4">
                <StatusBadge status={email.status} />
                {decision?.amount != null && (
                  <span className="text-right text-sm text-ink">
                    {formatMoney(decision.amount, decision.currency)}
                    {showsUsdEquivalent && decision.amount_usd != null && (
                      <span className="block text-xs text-muted">
                        ≈ USD {formatMoney(decision.amount_usd, null)}
                      </span>
                    )}
                  </span>
                )}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function EmailListSkeleton() {
  return (
    <ul aria-hidden className="divide-y divide-line">
      {[0, 1, 2].map((row) => (
        <li key={row} className="space-y-2 px-6 py-4">
          <div className="h-3.5 w-1/2 animate-pulse rounded bg-sunken" />
          <div className="h-3.5 w-3/4 animate-pulse rounded bg-sunken" />
          <div className="h-3 w-1/4 animate-pulse rounded bg-sunken" />
        </li>
      ))}
    </ul>
  );
}
