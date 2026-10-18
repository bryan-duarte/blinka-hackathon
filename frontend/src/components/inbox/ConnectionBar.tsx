"use client";

import { useState } from "react";
import { SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";
import { WhatsAppCard } from "./WhatsAppCard";
import type {
  ConnectableProvider,
  MailAccountStatus,
  MailboxConnectionView,
} from "@/lib/types";

const PROVIDER_LABELS: Record<ConnectableProvider, string> = {
  gmail: "Gmail",
  outlook: "Outlook",
};

const STATUS_LABELS: Record<MailAccountStatus, string> = {
  initiated: "pending",
  active: "connected",
  failed: "failed",
  expired: "expired",
};

const CONNECTABLE_PROVIDERS: ConnectableProvider[] = ["gmail", "outlook"];

type ConnectionBarProps = {
  connections: MailboxConnectionView[];
  onUnauthorized: (error: unknown) => boolean;
  onChanged: () => void;
};

export function ConnectionBar({ connections, onUnauthorized, onChanged }: ConnectionBarProps) {
  const [connectingProvider, setConnectingProvider] =
    useState<ConnectableProvider | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const mailConnections = connections.filter((connection) => connection.provider !== "whatsapp");
  const activeProviders = new Set(
    mailConnections
      .filter((connection) => connection.status === "active")
      .map((connection) => connection.provider),
  );
  const visibleConnections = mailConnections.filter(
    (connection) => connection.status !== "initiated",
  );
  const hasActiveWhatsApp = connections.some(
    (connection) => connection.provider === "whatsapp" && connection.status === "active",
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
          ? `${PROVIDER_LABELS[provider]} already connected`
          : "The connection could not be started",
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
            ? "Redirecting..."
            : `Connect ${PROVIDER_LABELS[provider]}`}
        </button>
      ))}
      <details className="relative">
        <summary
          className={`${SECONDARY_BUTTON_CLASS} h-9 cursor-pointer list-none px-4 select-none [&::-webkit-details-marker]:hidden`}
        >
          {hasActiveWhatsApp && (
            <span aria-hidden className="mr-1">
              ✓
            </span>
          )}
          WhatsApp
        </summary>
        <div className="absolute right-0 z-10 mt-1 w-80 rounded border border-line bg-panel p-6">
          <WhatsAppCard
            connections={connections}
            onUnauthorized={onUnauthorized}
            onChanged={onChanged}
          />
        </div>
      </details>
      {connectError && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {connectError}
        </p>
      )}
    </div>
  );
}
