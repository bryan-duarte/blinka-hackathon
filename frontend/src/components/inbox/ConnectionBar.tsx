"use client";

import { useState } from "react";
import { EYEBROW_CLASS } from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";
import { maskPhone } from "@/lib/mask";
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

const CHIP_CLASS =
  "inline-flex h-8 items-center gap-2 rounded-full px-3 text-[13px] whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";
const CONNECTED_CHIP_CLASS = `${CHIP_CLASS} border border-ink bg-panel text-ink`;
const MISSING_CHIP_CLASS = `${CHIP_CLASS} cursor-pointer border border-dashed border-selection bg-transparent text-ink hover:border-ink hover:bg-panel disabled:cursor-wait disabled:opacity-60`;

type ConnectionBarProps = {
  connections: MailboxConnectionView[];
  onUnauthorized: (error: unknown) => boolean;
  onChanged: () => void;
};

function latestConnection(
  connections: MailboxConnectionView[],
  provider: ConnectableProvider,
): MailboxConnectionView | undefined {
  const providerConnections = connections.filter(
    (connection) => connection.provider === provider && connection.status !== "initiated",
  );
  return providerConnections.find((connection) => connection.status === "active") ?? providerConnections[0];
}

export function ConnectionBar({ connections, onUnauthorized, onChanged }: ConnectionBarProps) {
  const [connectingProvider, setConnectingProvider] =
    useState<ConnectableProvider | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const activeWhatsApp = connections.find(
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
    <div
      aria-label="Channels"
      className="flex flex-wrap items-center gap-2 border-b border-line bg-sunken px-4 py-2.5 md:px-8"
    >
      <span className={`${EYEBROW_CLASS} mr-1`}>Channels</span>
      {CONNECTABLE_PROVIDERS.map((provider) => {
        const connection = latestConnection(connections, provider);
        if (connection?.status === "active") {
          return (
            <span key={provider} className={CONNECTED_CHIP_CLASS}>
              <MailIcon />
              <span className="font-medium">{PROVIDER_LABELS[provider]}</span>
              <span className="text-muted">{STATUS_LABELS.active}</span>
              <CheckIcon />
            </span>
          );
        }
        const isConnecting = connectingProvider === provider;
        return (
          <button
            key={provider}
            type="button"
            disabled={connectingProvider !== null}
            onClick={() => connect(provider)}
            className={MISSING_CHIP_CLASS}
          >
            {connection ? <MailIcon /> : <PlusIcon />}
            {isConnecting
              ? "Redirecting…"
              : connection
                ? `${PROVIDER_LABELS[provider]} ${STATUS_LABELS[connection.status]} · Reconnect`
                : `Connect ${PROVIDER_LABELS[provider]}`}
          </button>
        );
      })}
      <details className="relative">
        <summary
          className={`${activeWhatsApp ? CONNECTED_CHIP_CLASS : MISSING_CHIP_CLASS} cursor-pointer list-none select-none [&::-webkit-details-marker]:hidden`}
        >
          {activeWhatsApp ? <ChatIcon /> : <PlusIcon />}
          <span className={activeWhatsApp ? "font-medium" : undefined}>
            {activeWhatsApp ? "WhatsApp" : "Set up WhatsApp"}
          </span>
          {activeWhatsApp && (
            <>
              <span className="text-muted tabular-nums">
                {activeWhatsApp.mode === "sandbox" ? "sandbox" : "own number"}
                {activeWhatsApp.phone_number && ` · ${maskPhone(activeWhatsApp.phone_number)}`}
              </span>
              <CheckIcon />
            </>
          )}
        </summary>
        <div className="absolute left-0 z-10 mt-2 w-80 rounded-lg border border-ink bg-panel p-6">
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

const ICON_CLASS = "size-4 shrink-0 fill-none stroke-current";

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

function PlusIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={ICON_CLASS} strokeWidth={1.5} strokeLinecap="round">
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-3.5 shrink-0 fill-none stroke-current" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="m3.5 8.5 3 3 6-7" />
    </svg>
  );
}
