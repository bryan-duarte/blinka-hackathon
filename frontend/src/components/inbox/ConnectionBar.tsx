"use client";

import { useState } from "react";
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
      {visibleConnections.map((connection) => (
        <span
          key={connection.connection_id}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 text-xs text-muted"
        >
          <span
            aria-hidden
            className={`size-1.5 rounded-full ${connection.status === "active" ? "bg-success" : "bg-danger"}`}
          />
          <span className="font-medium text-ink">
            {PROVIDER_LABELS[connection.provider as ConnectableProvider]}
          </span>
          {STATUS_LABELS[connection.status]}
        </span>
      ))}
      {CONNECTABLE_PROVIDERS.filter(
        (provider) => !activeProviders.has(provider),
      ).map((provider) => (
        <button
          key={provider}
          type="button"
          disabled={connectingProvider !== null}
          onClick={() => connect(provider)}
          className="h-9 rounded-md border border-line bg-panel px-3 text-sm font-medium text-ink transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {connectingProvider === provider
            ? "Redirigiendo..."
            : `Conectar ${PROVIDER_LABELS[provider]}`}
        </button>
      ))}
      {connectError && (
        <p role="alert" className="text-sm text-danger">
          {connectError}
        </p>
      )}
    </div>
  );
}
