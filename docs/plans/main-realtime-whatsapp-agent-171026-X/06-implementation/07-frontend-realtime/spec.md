# Frontend Realtime Implementation

## Overview

Subscribe the inbox page to `/inbox/{userId}` with aws-amplify v6 Events. Routing:
- Inbox item events patch the list.
- Run, tool, todo and thinking events feed a new `AgentActivity` panel, which replaces `RunTimeline`.

Polling drops to a 60 s safety refresh while the socket is live and comes back while it is not.

## Files to Modify/Create

- `frontend/package.json`: `"aws-amplify": "6.22.2"` (`pnpm --filter @blinka/web add aws-amplify@6.22.2`).
- `frontend/.env.example`: `NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT=`, `NEXT_PUBLIC_APPSYNC_EVENTS_REGION=us-east-1`, `NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY=`.
- `frontend/src/lib/types.ts`: `RealtimeEvent`, `RealtimeEventType`, `AgentTodo`. `PaymentRunEvent.id: number`.
- `frontend/src/lib/api.ts`: `currentUserId(): string | null` decodes the `sub` claim from `tokenStore`'s JWT (base64url JSON, no verification).
- `frontend/src/lib/realtime.ts` (new):
  - `isRealtimeConfigured(): boolean` (all 3 env vars set).
  - `ensureAmplifyConfigured()`, idempotent.
  - `type ChannelState = "connecting" | "live" | "offline"`.
- `frontend/src/lib/useInboxChannel.ts` (new): `useInboxChannel(onEvent: (event: RealtimeEvent) => void): ChannelState`.
- `frontend/src/lib/labels.ts`
  - Add `RUN_STEP_LABELS` for `todos_updated`, `tool_started`, `tool_finished`, `agent_summary`.
  - Add `TODO_STATUS_LABELS: Record<AgentTodo["status"], string>`.
- `frontend/src/components/inbox/AgentActivity.tsx` (new): `AgentActivity({ runId, liveEvents, thinking, isRunning })`.
- `frontend/src/components/inbox/RunTimeline.tsx`: **delete**, since `EmailDetail` was its only consumer.
- `frontend/src/components/inbox/EmailDetail.tsx`
  - In `ResultCard` (`:73-83`), replace `<RunTimeline runId=…/>` with `<AgentActivity …/>`.
  - When the status is not pending and `email.run_id` exists, render `AgentActivity` collapsed above the decision card.
  - New props: `runEvents: RealtimeEvent[]` and `thinking: string`, passed down from the page.
- `frontend/src/app/inbox/page.tsx`
  - Subscribe with `useInboxChannel`.
  - Keep per-run live buffers: `Map<runId, RealtimeEvent[]>` and `Map<runId, string>` for thinking.
  - Make the polling adaptive.
  - Resync over REST on (re)connect.

## Implementation Guidelines

- **Before writing code,** read `frontend/DESIGN.md` fully, then the Next guides `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md` and `.../02-guides/single-page-applications.md`, as `frontend/AGENTS.md` requires.

### Amplify config + hook

```ts
// orientative — aws-amplify@6.22.2
"use client";
import { Amplify } from "aws-amplify";
import { events } from "aws-amplify/data";

let configured = false;
export function ensureAmplifyConfigured() {
  if (configured || !isRealtimeConfigured()) return;
  Amplify.configure({ API: { Events: {
    endpoint: process.env.NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT!,
    region: process.env.NEXT_PUBLIC_APPSYNC_EVENTS_REGION!,
    defaultAuthMode: "apiKey",
    apiKey: process.env.NEXT_PUBLIC_APPSYNC_EVENTS_API_KEY!,
  } } });
  configured = true;
}

export function useInboxChannel(onEvent: (event: RealtimeEvent) => void): ChannelState {
  const [state, setState] = useState<ChannelState>("connecting");
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;
  useEffect(() => {
    const userId = currentUserId();
    if (!userId || !isRealtimeConfigured()) { setState("offline"); return; }
    ensureAmplifyConfigured();
    let isCancelled = false;
    let channel: Awaited<ReturnType<typeof events.connect>> | null = null;
    (async () => {
      try {
        channel = await events.connect(`/inbox/${userId}`);
        if (isCancelled) { channel.close(); return; }
        channel.subscribe({
          next: (message) => handlerRef.current(message.event as RealtimeEvent),
          error: () => setState("offline"),
        });
        setState("live");
      } catch { setState("offline"); }
    })();
    return () => { isCancelled = true; channel?.close(); };
  }, []);
  return state;
}
```

- The payload lives in `message.event`, which Amplify has already JSON-parsed. If it arrives as a string, `JSON.parse` it defensively.
- Reconnect: when the state becomes `offline`, schedule a re-run of the effect after a jittered backoff of 2–30 s. Use a `reconnectKey` state included in the effect deps.

### Page routing (`inbox/page.tsx`)

- `inbox.item`:
  - If `item_id` is in the list, patch that row's `status`.
  - Otherwise (a new item), refetch the list.
  - If `item_id === selectedEmailId`, also refetch the detail.
- `run.step`, `agent.tool`, `agent.todos`: append to `runEvents[run_id]`, deduped by `sequence`.
  - On terminal steps (`completed`, `failed`, `cancelled`, `decided`, `not_a_bill`, `extraction_failed`), refetch the list and the selected detail. The derived inbox status changes then.
- `agent.thinking`: `thinking[run_id] += payload.text`, keeping only the last 400 characters. Clear it on the next `agent.tool` or `run.step` for that run.
- Polling interval:

  | Socket state | Interval |
  |---|---|
  | `live` | `SAFETY_REFRESH_MS = 60000` |
  | otherwise, with pending items | existing `POLL_INTERVAL_MS` (4000) |
  | otherwise, idle | `IDLE_POLL_INTERVAL_MS` (15000) |

- When the channel state goes from not-live to `live`, bump `refreshCount` once to resync.

### AgentActivity

- **Data.**
  - On mount, `api.runStatus(runId)` returns persisted events. Merge them with `liveEvents`, dedupe by `sequence` (`PaymentRunEvent.id`), and sort ascending.
  - No polling inside the component. The page owns refresh.
  - When `isRunning` and the socket is offline, the page's 4 s refresh re-fetches `runStatus` through a `refreshKey` prop.
- **Derived view.**
  - `todos` = payload of the latest `todos_updated`.
  - `toolFeed` = `tool_started`/`tool_finished` pairs grouped by `payload.call_id`. Each entry is `{tool, message, status: running|ok|error, duration_ms}`; it shows the start message while running and the finish message once done.
  - `summary` = `agent_summary.text`.
  - `verdict` = `decided.payload.verdict`.
- **Layout** (DESIGN.md tokens only: paper/white/sunken tints, cobalt accent, weight 300, 4 px radius, no shadows, Spanish copy, no em-dashes):
  1. **Plan checklist.** One row per todo. Status glyph as a 1.5 px cobalt line icon: empty circle, half, check. `in_progress` rows use `text-ink` with the `accent-wash` background.
  2. **Tool feed.** Each row is the friendly message, then a right-aligned duration in `tnum` (e.g. "1,2 s"). A running row shows a thin `animate-pulse` bar, which respects reduced motion.
  3. **Thinking line.** `text-muted text-sm`, prefixed "Pensando: ", showing the last 160 characters. Only rendered while `isRunning && thinking`.
  4. **Collapsed state** (not running): one line "Plan completado en N pasos · ver detalle" plus a ghost toggle button. It expands to sections 1–2 plus the summary.
- **Accessibility.** `aria-live="polite"` on the feed container only, not on the thinking line, to avoid screen-reader spam.

## Dependencies

- Module 03 (event wire contract), module 04 (env values), module 02 (step names).

## Integration Notes

- **Events consumed:** `RealtimeEvent` exactly as in `03-design.md`. `sequence` equals `PaymentRunEvent.id` from `GET /payments/runs/{id}`, and that is the dedupe key.
- **Missing env vars:** if the realtime env vars are absent, `useInboxChannel` returns `offline` and the page behaves exactly as today with polling. This is the dev fallback.
