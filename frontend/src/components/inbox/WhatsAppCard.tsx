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
const FALLBACK_SANDBOX_NUMBER = "demo de Kapso";

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
  if (!(error instanceof ApiError)) return "No se pudo activar el demo";
  if (error.status === HTTP_UNPROCESSABLE) return "Revisa el número: usa el formato +56 9 1234 5678";
  if (error.status === HTTP_CONFLICT) return "Ese número ya está registrado por otra cuenta";
  return "No se pudo activar el demo";
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
      setCardError(isAlreadyConnected ? "WhatsApp ya conectado" : "No se pudo iniciar la conexión");
    }
  }

  const connectOwnNumberButton = (
    <button
      type="button"
      disabled={isRedirecting}
      onClick={connectOwnNumber}
      className={`${SECONDARY_BUTTON_CLASS} self-start`}
    >
      {isRedirecting ? "Redirigiendo…" : "Conectar mi número"}
    </button>
  );

  return (
    <section aria-label="WhatsApp" className="flex flex-col gap-4">
      <p className={EYEBROW_CLASS}>WhatsApp</p>
      {ownNumber ? (
        <div className="flex flex-col gap-1">
          <p className="text-sm text-ink">Conectado: {ownNumber.phone_number}</p>
          <p className={HINT_CLASS}>Escaneamos los documentos que recibe tu número.</p>
        </div>
      ) : sandboxPhone ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink">Modo demo (sandbox)</p>
          <p className="text-sm text-nav-ink">
            Reenvía tus facturas en PDF, ZIP o XML al número {sandboxNumber} desde {sandboxPhone}.
          </p>
          <p className={HINT_CLASS}>
            Para activarlo, escríbele al número {sandboxNumber} con el código de activación que te
            compartimos desde el panel de Kapso. El código vence en 15 minutos.
          </p>
          {connectOwnNumberButton}
        </div>
      ) : (
        <form onSubmit={registerSandbox} className="flex flex-col gap-3">
          <p className="text-sm text-nav-ink">Por defecto usamos el número demo de Blinka.</p>
          <label htmlFor="whatsapp-phone" className={LABEL_CLASS}>
            Tu número de WhatsApp
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
              {isSubmitting ? "Activando…" : "Activar demo"}
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
