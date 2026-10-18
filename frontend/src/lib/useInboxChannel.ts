"use client";

import { events } from "aws-amplify/data";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import { currentUserId, tokenStore } from "./api";
import {
  type ChannelState,
  ensureAmplifyConfigured,
  inboxChannel,
  isRealtimeConfigured,
  parseRealtimeEvent,
  REALTIME_AUTH_MODE,
} from "./realtime";
import type { RealtimeEvent } from "./types";

const RECONNECT_BASE_DELAY_MS = 2000;
const RECONNECT_MAX_DELAY_MS = 30000;
const RECONNECT_MIN_JITTER = 0.5;

type EventsChannel = Awaited<ReturnType<typeof events.connect>>;

function reconnectDelayMs(attempt: number): number {
  const backoffMs = Math.min(RECONNECT_MAX_DELAY_MS, RECONNECT_BASE_DELAY_MS * 2 ** attempt);
  const jitter = RECONNECT_MIN_JITTER + Math.random() * (1 - RECONNECT_MIN_JITTER);
  return Math.max(RECONNECT_BASE_DELAY_MS, backoffMs * jitter);
}

function canSubscribe(): boolean {
  return isRealtimeConfigured() && currentUserId() !== null;
}

export function useInboxChannel(onEvent: (event: RealtimeEvent) => void): ChannelState {
  const [channelState, setChannelState] = useState<ChannelState>(() =>
    canSubscribe() ? "connecting" : "offline",
  );
  const [reconnectKey, setReconnectKey] = useState(0);
  const consecutiveFailures = useRef(0);
  const handleEvent = useEffectEvent(onEvent);

  useEffect(() => {
    const userId = currentUserId();
    const loginToken = tokenStore.get();
    if (!userId || !loginToken || !isRealtimeConfigured()) return;
    ensureAmplifyConfigured();
    let isCancelled = false;
    let channel: EventsChannel | null = null;
    let reconnectTimer: number | undefined;

    const goOffline = () => {
      if (isCancelled) return;
      setChannelState("offline");
      const retryDelayMs = reconnectDelayMs(consecutiveFailures.current);
      consecutiveFailures.current += 1;
      reconnectTimer = window.setTimeout(() => setReconnectKey((key) => key + 1), retryDelayMs);
    };

    events
      .connect(inboxChannel(userId), { authMode: REALTIME_AUTH_MODE, authToken: loginToken })
      .then((connectedChannel) => {
        channel = connectedChannel;
        if (isCancelled) {
          connectedChannel.close();
          return;
        }
        connectedChannel.subscribe({
          next: (message: { event?: unknown }) => {
            const realtimeEvent = parseRealtimeEvent(message.event);
            if (realtimeEvent) handleEvent(realtimeEvent);
          },
          error: goOffline,
        });
        consecutiveFailures.current = 0;
        setChannelState("live");
      })
      .catch(goOffline);

    return () => {
      isCancelled = true;
      window.clearTimeout(reconnectTimer);
      channel?.close();
    };
  }, [reconnectKey]);

  return channelState;
}
