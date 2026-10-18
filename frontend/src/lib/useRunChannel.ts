"use client";

import { useState } from "react";
import type { ChannelState } from "./realtime";
import { withEvent } from "./runEvents";
import type { RealtimeEvent } from "./types";
import { useInboxChannel } from "./useInboxChannel";

const THINKING_EVENT_TYPE = "agent.thinking";

export type RunChannel = {
  events: RealtimeEvent[];
  state: ChannelState;
};

export function useRunChannel(runId: string): RunChannel {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const state = useInboxChannel((event) => {
    const isRunEvent = event.run_id === runId && event.type !== THINKING_EVENT_TYPE;
    if (isRunEvent) setEvents((current) => withEvent(current, event));
  });
  return { events, state };
}
