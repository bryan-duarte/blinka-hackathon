"use client";

import { useState } from "react";
import { SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { ApiError, api } from "@/lib/api";
import type {
  ConnectableProvider,
  MailAccountStatus,
  MailboxConnectionView,
} from "@/lib/types";

const HTTP_CONFLICT = 409;

const PROVIDER_LABELS: Record<ConnectableProvider, string> = {
  gmail: "Gmail",
  outlook: "Outlook",
};

const STATUS_LABELS: Record<MailAccountStatus, string> = {
  initiated: "pendiente",
  active: "conectado",
  failed: "falló",
  expired: "expirado",
};

const CONNECTABLE_PROVIDERS: ConnectableProvider[] = ["gmail", "outlook"];

type ConnectionBarProps = {
  connections: MailboxConnectionView[];
  onUnauthorized: (error: unknown) => boolean;
};

export function ConnectionBar({ connections, onUnauthorized }: ConnectionBarProps) {
  const [connectingProvider, setConnectingProvider] =
    useState<ConnectableProvider | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const activeProviders = new Set(
    connections
      .filter((connection) => connection.status === "active")
      .map((connection) => connection.provider),
  );
  const visibleConnections = connections.filter(
    (connection) => connection.status !== "initiated",
  );

  async function connect(provider: ConnectableProvider) {
    setConnectingProvider(provider);
    setConnectError(null);
    try {
      const started = await api.connect(provider);
      window.location.assign(started.redirect_url);
    } catch (error) {
      setConnectingProvider(null);
      if (onUnauthorized(error)) return;
      const isAlreadyConnected =
        error instanceof ApiError && error.status === HTTP_CONFLICT;
      setConnectError(
        isAlreadyConnected
          ? `${PROVIDER_LABELS[provider]} ya conectado`
          : "No se pudo iniciar la conexión",
      );
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {visibleConnections.map((connection) => {
        const isActive = connection.status === "active";
        return (
          <span
            key={connection.connection_id}
            className={`mr-2 inline-flex items-center gap-1 text-xs ${isActive ? "text-muted" : "text-danger"}`}
          >
            <span aria-hidden className={isActive ? "text-accent" : undefined}>
              {isActive ? "✓" : "✕"}
            </span>
            {PROVIDER_LABELS[connection.provider as ConnectableProvider]}{" "}
            {STATUS_LABELS[connection.status]}
          </span>
        );
      })}
      {CONNECTABLE_PROVIDERS.filter(
        (provider) => !activeProviders.has(provider),
      ).map((provider) => (
        <button
          key={provider}
          type="button"
          disabled={connectingProvider !== null}
          onClick={() => connect(provider)}
          className={`${SECONDARY_BUTTON_CLASS} h-9 px-4`}
        >
          {connectingProvider === provider
            ? "Redirigiendo..."
            : `Conectar ${PROVIDER_LABELS[provider]}`}
        </button>
      ))}
      {connectError && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {connectError}
        </p>
      )}
    </div>
  );
}
