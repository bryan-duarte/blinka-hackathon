import { type SubmitEvent, useEffect, useState } from "react";
import { INPUT_CLASS, QUIET_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { maskContact, maskEmail, maskPhone } from "@/lib/mask";
import type { KitDestinations, TrustedForwarderView } from "@/lib/types";

const EMAIL_SEPARATOR = "@";
const COPIED_RESET_MS = 1500;
const TILE_CLASS = "flex min-w-0 flex-col gap-2 rounded-lg border border-line bg-panel p-4";
const SMALL_GHOST_BUTTON_CLASS = `${SECONDARY_BUTTON_CLASS} h-8 self-start px-3 text-[13px]`;

type SelfSendCardProps = {
  destinations: KitDestinations;
  selfSendableCount: number;
};

export function SelfSendCard({ destinations, selfSendableCount }: SelfSendCardProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [kitError, setKitError] = useState<string | null>(null);

  async function downloadKit() {
    setIsDownloading(true);
    setKitError(null);
    try {
      await api.downloadDemoKit();
    } catch {
      setKitError("The kit could not be downloaded.");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section aria-labelledby="self-send-title" className="grid grid-cols-2 gap-2.5">
      <div className="col-span-2 flex flex-col gap-2 rounded-lg bg-ink p-5 text-white">
        <p className="text-sm font-bold text-white/70 [font-variant-caps:all-small-caps]">Test it yourself</p>
        <h3 id="self-send-title" className="font-serif text-[26px] leading-[1.13]">
          Send real files from your own inbox
        </h3>
        <p className="text-sm leading-[1.5] text-white/80">
          {selfSendableCount} cases come with their invoice files and the subject to use. Each row with a download
          button below is one of them.
        </p>
        <button
          type="button"
          onClick={downloadKit}
          disabled={isDownloading}
          className="mt-1 inline-flex h-10 items-center gap-1.5 self-start rounded-full border border-white bg-white px-5 text-[15px] font-medium text-ink transition-opacity hover:opacity-86 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:cursor-wait disabled:opacity-60"
        >
          <DownloadIcon />
          {isDownloading ? "Preparing kit…" : "Download the kit (.zip)"}
        </button>
        {kitError && (
          <p role="alert" className="text-sm">
            <span aria-hidden>✕ </span>
            {kitError}
          </p>
        )}
      </div>
      <DestinationTile
        label="Email to"
        icon={<MailIcon />}
        value={destinations.email_address}
        shownValue={destinations.email_address ? maskEmail(destinations.email_address) : null}
        emptyText="Connect a Gmail inbox in the console"
      />
      <DestinationTile
        label="WhatsApp to"
        icon={<ChatIcon />}
        value={destinations.whatsapp_number}
        shownValue={destinations.whatsapp_number ? maskPhone(destinations.whatsapp_number) : null}
        emptyText="Register a sandbox phone first"
      />
      <TrustedForwarders />
    </section>
  );
}

function DestinationTile({
  label,
  icon,
  value,
  shownValue,
  emptyText,
}: {
  label: string;
  icon: React.ReactNode;
  value: string | null;
  shownValue: string | null;
  emptyText: string;
}) {
  const [isCopied, setIsCopied] = useState(false);

  async function copyValue() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), COPIED_RESET_MS);
    } catch {
      setIsCopied(false);
    }
  }

  return (
    <div className={TILE_CLASS}>
      <span className="flex items-center gap-1.5 text-xs text-muted">
        {icon}
        {label}
      </span>
      {shownValue ? (
        <>
          <span className="text-[13px] font-medium break-all tabular-nums">{shownValue}</span>
          <button type="button" onClick={copyValue} className={SMALL_GHOST_BUTTON_CLASS} aria-live="polite">
            {isCopied ? "Copied" : "Copy"}
          </button>
        </>
      ) : (
        <span className="text-[13px] text-muted">{emptyText}</span>
      )}
    </div>
  );
}

function TrustedForwarders() {
  const [forwarders, setForwarders] = useState<TrustedForwarderView[] | null>(null);
  const [newForwarder, setNewForwarder] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [forwarderError, setForwarderError] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;
    api
      .trustedForwarders()
      .then((loaded) => {
        if (!isCancelled) setForwarders(loaded);
      })
      .catch(() => {
        if (!isCancelled) setForwarderError("Trusted forwarders could not be loaded.");
      });
    return () => {
      isCancelled = true;
    };
  }, []);

  async function addForwarder(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const forwarderValue = newForwarder.trim();
    if (!forwarderValue) return;
    setIsSaving(true);
    setForwarderError(null);
    try {
      const kind = forwarderValue.includes(EMAIL_SEPARATOR) ? "email" : "domain";
      const created = await api.addTrustedForwarder({ kind, value: forwarderValue, note: "Added from the demo panel" });
      setForwarders((current) => [
        created,
        ...(current ?? []).filter((forwarder) => forwarder.forwarder_id !== created.forwarder_id),
      ]);
      setNewForwarder("");
    } catch {
      setForwarderError("That address could not be added.");
    } finally {
      setIsSaving(false);
    }
  }

  async function removeForwarder(forwarderId: string) {
    setForwarderError(null);
    try {
      await api.deleteTrustedForwarder(forwarderId);
      setForwarders((current) =>
        (current ?? []).filter((forwarder) => forwarder.forwarder_id !== forwarderId),
      );
    } catch {
      setForwarderError("That forwarder could not be removed.");
    }
  }

  const summary =
    forwarders === null
      ? "Loading trusted forwarders…"
      : forwarders.length === 0
        ? "Add your address so the agent judges the payee from the file, not from you."
        : `${forwarders.map((forwarder) => maskContact(forwarder.normalized_value)).join(", ")} ${forwarders.length === 1 ? "is" : "are"} trusted, so the agent judges the payee from the file.`;

  return (
    <details className="group col-span-2 rounded-lg bg-sunken">
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-lg p-4 text-[13px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink [&::-webkit-details-marker]:hidden">
        <svg aria-hidden viewBox="0 0 16 16" className="size-5 shrink-0 fill-none stroke-current" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="m3.5 8.5 3 3 6-7" />
        </svg>
        <span className="min-w-0 flex-1 break-words">{summary}</span>
        <span className="shrink-0 underline group-open:hidden">Edit</span>
        <span className="hidden shrink-0 underline group-open:inline">Done</span>
      </summary>
      <div className="flex flex-col gap-2 px-4 pb-4">
        <ul className="flex flex-col">
          {forwarders?.map((forwarder) => (
            <li
              key={forwarder.forwarder_id}
              className="flex items-center justify-between gap-2 border-t border-line py-2 text-sm"
            >
              <span className="min-w-0 truncate">{maskContact(forwarder.normalized_value)}</span>
              <button
                type="button"
                onClick={() => removeForwarder(forwarder.forwarder_id)}
                className={QUIET_BUTTON_CLASS}
                aria-label={`Remove ${maskContact(forwarder.normalized_value)}`}
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
        {forwarderError && (
          <p role="alert" className="text-sm text-danger">
            <span aria-hidden>✕ </span>
            {forwarderError}
          </p>
        )}
      </div>
    </details>
  );
}

const ICON_CLASS = "size-4 shrink-0 fill-none stroke-current";

export function DownloadIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={ICON_CLASS} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2.5v8" />
      <path d="m4.5 7 3.5 3.5L11.5 7" />
      <path d="M3 13.5h10" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={ICON_CLASS} strokeWidth={1.5} strokeLinejoin="round">
      <path d="M2.5 4h11v8h-11z" />
      <path d="M2.5 4.5 8 9l5.5-4.5" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={ICON_CLASS} strokeWidth={1.5} strokeLinejoin="round">
      <path d="M8 2.5a5.5 5.5 0 0 0-4.7 8.4l-.8 2.6 2.7-.8A5.5 5.5 0 1 0 8 2.5z" />
    </svg>
  );
}
