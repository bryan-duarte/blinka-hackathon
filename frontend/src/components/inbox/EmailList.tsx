import { formatMoney, formatRelative, isForeignCurrency } from "@/lib/format";
import { maskEmailsIn } from "@/lib/mask";
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
      <div className="px-4 py-10">
        <p className="text-sm font-normal text-ink">Your inbox is empty</p>
        <p className="mt-1 text-sm text-muted">
          Connect an email inbox or WhatsApp, or send a demo scenario to see how the agent
          decides.
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
              title={email.subject || undefined}
              className={`flex w-full flex-col gap-1.5 px-4 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink ${isSelected ? "bg-ink text-white" : "text-ink hover:bg-sunken"}`}
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className={`flex min-w-0 items-center gap-1.5 ${isSelected ? "[&_svg]:stroke-white" : ""}`}>
                  <SourceBadge type={email.source_type} />
                  <span className="truncate text-sm font-medium">
                    {maskEmailsIn(email.sender) || "Unknown sender"}
                  </span>
                </span>
                <span className={`shrink-0 text-xs ${isSelected ? "text-white/70" : "text-muted"}`}>
                  {email.received_at ? formatRelative(email.received_at) : "simulated"}
                </span>
              </span>
              <span className="flex items-center justify-between gap-3">
                <StatusBadge status={email.status} />
                {decision?.amount != null && (
                  <span className="text-right text-[13px] tabular-nums">
                    {formatMoney(decision.amount, decision.currency)}
                    {showsUsdEquivalent && decision.amount_usd != null && (
                      <span className={`block text-xs ${isSelected ? "text-white/70" : "text-muted"}`}>
                        ≈ USD {formatMoney(decision.amount_usd, null)}
                      </span>
                    )}
                  </span>
                )}
              </span>
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
      {[0, 1, 2, 3].map((row) => (
        <li key={row} className="space-y-2 px-4 py-3">
          <div className="h-3.5 w-2/3 animate-pulse rounded bg-sunken" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-sunken" />
        </li>
      ))}
    </ul>
  );
}
