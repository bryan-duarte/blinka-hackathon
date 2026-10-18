"use client";

import { Amplify } from "aws-amplify";
import type { RealtimeEvent } from "./types";

export type ChannelState = "connecting" | "live" | "offline";

const INBOX_NAMESPACE = "inbox";
export const REALTIME_AUTH_MODE = "lambda";

const realtimeConfig = {
  endpoint: process.env.NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT ?? "",
  region: process.env.NEXT_PUBLIC_APPSYNC_EVENTS_REGION ?? "",
};

let isAmplifyConfigured = false;

export function isRealtimeConfigured(): boolean {
  return Boolean(realtimeConfig.endpoint && realtimeConfig.region);
}

export function ensureAmplifyConfigured(): void {
  if (isAmplifyConfigured || !isRealtimeConfigured()) return;
  Amplify.configure({
    API: {
      Events: {
        endpoint: realtimeConfig.endpoint,
        region: realtimeConfig.region,
        defaultAuthMode: REALTIME_AUTH_MODE,
      },
    },
  });
  isAmplifyConfigured = true;
}

export function inboxChannel(userId: string): string {
  return `/${INBOX_NAMESPACE}/${userId}`;
}

export function parseRealtimeEvent(rawEvent: unknown): RealtimeEvent | null {
  const candidate: unknown = typeof rawEvent === "string" ? safeJsonParse(rawEvent) : rawEvent;
  const isRealtimeEvent =
    candidate !== null &&
    typeof candidate === "object" &&
    "type" in candidate &&
    "step" in candidate &&
    "payload" in candidate;
  return isRealtimeEvent ? (candidate as RealtimeEvent) : null;
}

function safeJsonParse(serialized: string): unknown {
  try {
    return JSON.parse(serialized);
  } catch {
    return null;
  }
}
