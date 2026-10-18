"use client";

import { type SubmitEvent, useState } from "react";
import {
  EYEBROW_CLASS,
  HINT_CLASS,
  INPUT_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
} from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";
import type { MailboxConnectionView, WhatsAppSandboxView } from "@/lib/types";

const HTTP_UNPROCESSABLE = 422;
const FALLBACK_SANDBOX_NUMBER = "the Kapso demo number";

type WhatsAppCardProps = {
  connections: MailboxConnectionView[];
  onUnauthorized: (error: unknown) => boolean;
  onChanged: () => void;
};

function activeWhatsAppConnection(
  connections: MailboxConnectionView[],
  mode: MailboxConnectionView["mode"],
): MailboxConnectionView | undefined {
  return connections.find(
    (connection) =>
      connection.provider === "whatsapp" && connection.mode === mode && connection.status === "active",
  );
}

function sandboxRegistrationError(error: unknown): string {
  if (!(error instanceof ApiError)) return "The demo could not be activated";
  if (error.status === HTTP_UNPROCESSABLE) return "Check the number: use the format +56 9 1234 5678";
  if (error.status === HTTP_CONFLICT) return "Another account already registered that number";
  return "The demo could not be activated";
}

export function WhatsAppCard({ connections, onUnauthorized, onChanged }: WhatsAppCardProps) {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [registeredSandbox, setRegisteredSandbox] = useState<WhatsAppSandboxView | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const ownNumber = activeWhatsAppConnection(connections, "own_number");
  const sandbox = activeWhatsAppConnection(connections, "sandbox");
  const sandboxPhone = registeredSandbox?.phone_number ?? sandbox?.phone_number ?? null;
  const sandboxNumber =
    registeredSandbox?.sandbox_number || sandbox?.sandbox_number || FALLBACK_SANDBOX_NUMBER;

  async function registerSandbox(submitEvent: SubmitEvent<HTMLFormElement>) {
    submitEvent.preventDefault();
    setIsSubmitting(true);
    setCardError(null);
    try {
      setRegisteredSandbox(await api.registerWhatsAppSandbox(phoneNumber));
      onChanged();
    } catch (error) {
      if (!onUnauthorized(error)) setCardError(sandboxRegistrationError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function connectOwnNumber() {
    setIsRedirecting(true);
    setCardError(null);
    try {
      const started = await api.connectWhatsAppNumber();
      window.location.assign(started.redirect_url);
    } catch (error) {
      setIsRedirecting(false);
      if (onUnauthorized(error)) return;
      const isAlreadyConnected = error instanceof ApiError && error.status === HTTP_CONFLICT;
      setCardError(isAlreadyConnected ? "WhatsApp already connected" : "The connection could not be started");
    }
  }

  const connectOwnNumberButton = (
    <button
      type="button"
      disabled={isRedirecting}
      onClick={connectOwnNumber}
      className={`${SECONDARY_BUTTON_CLASS} self-start`}
    >
      {isRedirecting ? "Redirecting…" : "Connect my number"}
    </button>
  );

  return (
    <section aria-label="WhatsApp" className="flex flex-col gap-4">
      <p className={EYEBROW_CLASS}>WhatsApp</p>
      {ownNumber ? (
        <div className="flex flex-col gap-1">
          <p className="text-sm text-ink">Connected: {ownNumber.phone_number}</p>
          <p className={HINT_CLASS}>We scan the documents your number receives.</p>
        </div>
      ) : sandboxPhone ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink">Demo mode (sandbox)</p>
          <p className="text-sm text-nav-ink">
            Forward your PDF, ZIP or XML invoices to {sandboxNumber} from {sandboxPhone}.
          </p>
          <p className={HINT_CLASS}>
            To activate it, message {sandboxNumber} with the activation code we share from the Kapso
            panel. The code expires in 15 minutes.
          </p>
          {connectOwnNumberButton}
        </div>
      ) : (
        <form onSubmit={registerSandbox} className="flex flex-col gap-3">
          <p className="text-sm text-nav-ink">By default we use the Blinka demo number.</p>
          <label htmlFor="whatsapp-phone" className={LABEL_CLASS}>
            Your WhatsApp number
          </label>
          <input
            id="whatsapp-phone"
            type="tel"
            required
            autoComplete="tel"
            placeholder="+56 9 1234 5678"
            value={phoneNumber}
            onChange={(changeEvent) => setPhoneNumber(changeEvent.target.value)}
            className={INPUT_CLASS}
          />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={isSubmitting} className={PRIMARY_BUTTON_CLASS}>
              {isSubmitting ? "Activating…" : "Activate demo"}
            </button>
            {connectOwnNumberButton}
          </div>
        </form>
      )}
      {cardError && (
        <p role="alert" className="text-sm text-danger">
          {cardError}
        </p>
      )}
    </section>
  );
}
