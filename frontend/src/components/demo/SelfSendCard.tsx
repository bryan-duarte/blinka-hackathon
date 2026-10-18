import { type FormEvent, useEffect, useState } from "react";
import {
  EYEBROW_CLASS,
  HINT_CLASS,
  INPUT_CLASS,
  QUIET_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
} from "@/components/settings/styles";
import { api } from "@/lib/api";
import type { KitDestinations, TrustedForwarderView } from "@/lib/types";

const EMAIL_SEPARATOR = "@";

export function SelfSendCard({ destinations }: { destinations: KitDestinations }) {
  const [forwarders, setForwarders] = useState<TrustedForwarderView[] | null>(null);
  const [newForwarder, setNewForwarder] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;
    api
      .trustedForwarders()
      .then((loaded) => {
        if (!isCancelled) setForwarders(loaded);
      })
      .catch(() => {
        if (!isCancelled) setCardError("Trusted forwarders could not be loaded.");
      });
    return () => {
      isCancelled = true;
    };
  }, []);

  async function addForwarder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const forwarderValue = newForwarder.trim();
    if (!forwarderValue) return;
    setIsSaving(true);
    setCardError(null);
    try {
      const kind = forwarderValue.includes(EMAIL_SEPARATOR) ? "email" : "domain";
      const created = await api.addTrustedForwarder({ kind, value: forwarderValue, note: "Added from the demo panel" });
      setForwarders((current) => [
        created,
        ...(current ?? []).filter((forwarder) => forwarder.forwarder_id !== created.forwarder_id),
      ]);
      setNewForwarder("");
    } catch {
      setCardError("That address could not be added.");
    } finally {
      setIsSaving(false);
    }
  }

  async function removeForwarder(forwarderId: string) {
    setCardError(null);
    try {
      await api.deleteTrustedForwarder(forwarderId);
      setForwarders((current) =>
        (current ?? []).filter((forwarder) => forwarder.forwarder_id !== forwarderId),
      );
    } catch {
      setCardError("That forwarder could not be removed.");
    }
  }

  async function downloadKit() {
    setIsDownloading(true);
    setCardError(null);
    try {
      await api.downloadDemoKit();
    } catch {
      setCardError("The kit could not be downloaded.");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section aria-labelledby="self-send-title" className="flex flex-col gap-4 border-t border-line pt-6">
      <h3 id="self-send-title" className={EYEBROW_CLASS}>
        Send it yourself
      </h3>
      <dl className="grid grid-cols-[6rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted">Email</dt>
        <dd className="break-words text-ink">
          {destinations.email_address ?? "Connect a Gmail inbox in the console"}
        </dd>
        <dt className="text-muted">WhatsApp</dt>
        <dd className="break-words text-ink">
          {destinations.whatsapp_number ?? "Register a sandbox phone first"}
        </dd>
      </dl>
      <div className="flex flex-col gap-2">
        <p className="text-sm text-ink">Trusted forwarders</p>
        <p className={HINT_CLASS}>
          Add your address so the agent judges the payee from the document, not from your sender.
        </p>
        {forwarders === null && !cardError && (
          <div aria-hidden className="h-3.5 w-1/2 animate-pulse rounded bg-sunken" />
        )}
        {forwarders?.length === 0 && <p className={HINT_CLASS}>No trusted forwarders yet.</p>}
        <ul className="flex flex-col">
          {forwarders?.map((forwarder) => (
            <li
              key={forwarder.forwarder_id}
              className="flex items-center justify-between gap-2 border-t border-line py-2 text-sm"
            >
              <span className="min-w-0 truncate text-ink">{forwarder.normalized_value}</span>
              <button
                type="button"
                onClick={() => removeForwarder(forwarder.forwarder_id)}
                className={QUIET_BUTTON_CLASS}
                aria-label={`Remove ${forwarder.normalized_value}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={addForwarder} className="flex gap-2">
          <label htmlFor="trusted-forwarder" className="sr-only">
            Email or domain
          </label>
          <input
            id="trusted-forwarder"
            value={newForwarder}
            onChange={(event) => setNewForwarder(event.target.value)}
            placeholder="you@company.com or company.com"
            disabled={isSaving}
            className={INPUT_CLASS}
          />
          <button type="submit" disabled={isSaving || !newForwarder.trim()} className={`${SECONDARY_BUTTON_CLASS} px-4`}>
            {isSaving ? "Adding…" : "Add"}
          </button>
        </form>
      </div>
      <button type="button" onClick={downloadKit} disabled={isDownloading} className={SECONDARY_BUTTON_CLASS}>
        {isDownloading ? "Preparing kit…" : "Download full kit (.zip)"}
      </button>
      {cardError && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {cardError}
        </p>
      )}
    </section>
  );
}
