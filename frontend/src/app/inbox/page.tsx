"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConsoleShell, ConsoleTopBar } from "@/components/console/ConsoleShell";
import { ConnectionBar } from "@/components/inbox/ConnectionBar";
import { EmailDetail } from "@/components/inbox/EmailDetail";
import { EmailList, EmailListSkeleton } from "@/components/inbox/EmailList";
import { InboxMetrics } from "@/components/inbox/InboxMetrics";
import { DemoScenariosPanel } from "@/components/demo/DemoScenariosPanel";
import { SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { UnauthorizedError, api, tokenStore } from "@/lib/api";
import { SOURCE_LABELS } from "@/lib/labels";
import { TERMINAL_RUN_STEPS } from "@/lib/runEvents";
import type {
  BudgetUsageView,
  DemoCatalogView,
  InboxChannel,
  InboxEmailDetail,
  InboxEmailStatus,
  InboxEmailView,
  MailboxConnectionView,
  RealtimeEvent,
} from "@/lib/types";
import { PENDING_STATUSES } from "@/lib/types";
import { useInboxChannel } from "@/lib/useInboxChannel";

const POLL_INTERVAL_MS = 4000;
const IDLE_POLL_INTERVAL_MS = 15000;
const SAFETY_REFRESH_MS = 60000;
const THINKING_BUFFER_CHARS = 400;
const RESET_ITEM_STATUS = "reset";
const SOURCE_FILTERS: InboxChannel[] = ["email", "whatsapp"];

type InboxFilter = "all" | "review";

type InboxSnapshot = {
  emails: InboxEmailView[];
  selectedEmail: InboxEmailDetail | null;
  budgets: BudgetUsageView[];
};

async function fetchInboxSnapshot(
  selectedEmailId: string | null,
  sourceFilter: InboxChannel | null,
): Promise<InboxSnapshot> {
  const [emails, selectedEmail, budgets] = await Promise.all([
    api.emails(sourceFilter ?? undefined),
    selectedEmailId ? api.email(selectedEmailId) : Promise.resolve(null),
    api.budgets(),
  ]);
  return { emails, selectedEmail, budgets };
}

function pollIntervalMs(isChannelLive: boolean, hasPendingEmails: boolean): number {
  if (isChannelLive) return hasPendingEmails ? IDLE_POLL_INTERVAL_MS : SAFETY_REFRESH_MS;
  return hasPendingEmails ? POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;
}

function withEvent(existingEvents: RealtimeEvent[] = [], event: RealtimeEvent): RealtimeEvent[] {
  const isDuplicate = existingEvents.some((existing) => existing.sequence === event.sequence);
  return isDuplicate ? existingEvents : [...existingEvents, event];
}

export default function InboxPage() {
  const router = useRouter();
  const [connections, setConnections] = useState<MailboxConnectionView[]>([]);
  const [emails, setEmails] = useState<InboxEmailView[] | null>(null);
  const [budgets, setBudgets] = useState<BudgetUsageView[] | null>(null);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<InboxEmailDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [demoCatalog, setDemoCatalog] = useState<DemoCatalogView | null>(null);
  const [isDemoPanelOpen, setIsDemoPanelOpen] = useState(false);
  const [inboxFilter, setInboxFilter] = useState<InboxFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<InboxChannel | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const [snapshotVersion, setSnapshotVersion] = useState(0);
  const [runEvents, setRunEvents] = useState<Record<string, RealtimeEvent[]>>({});
  const [thinkingByRun, setThinkingByRun] = useState<Record<string, string>>({});
  const wasChannelLive = useRef(false);
  const reviewEmails = (emails ?? []).filter((email) => email.status === "review");
  const isReviewFilter = inboxFilter === "review";
  const visibleEmails = emails && isReviewFilter ? reviewEmails : emails;
  const reviewCount = reviewEmails.length;
  const hasPendingEmails = (emails ?? []).some((email) => PENDING_STATUSES.has(email.status));
  const isReviewQueueEmpty = isReviewFilter && visibleEmails?.length === 0;
  const caption = emails
    ? `${emails.length} messages · ${reviewCount} in review`
    : "Loading messages…";
  const requestRefresh = useCallback(() => setRefreshCount((count) => count + 1), []);

  function resetInboxView() {
    setSelectedEmailId(null);
    setRunEvents({});
    setThinkingByRun({});
    requestRefresh();
  }

  function routeInboxItemEvent(event: RealtimeEvent) {
    const itemStatus = event.payload.status;
    if (itemStatus === RESET_ITEM_STATUS) {
      resetInboxView();
      return;
    }
    const isKnownItem = (emails ?? []).some((email) => email.email_id === event.item_id);
    const isSelectedItem = event.item_id === selectedEmailId;
    if (!isKnownItem || isSelectedItem || typeof itemStatus !== "string") {
      requestRefresh();
      return;
    }
    setEmails((current) =>
      (current ?? []).map((email) =>
        email.email_id === event.item_id
          ? { ...email, status: itemStatus as InboxEmailStatus }
          : email,
      ),
    );
  }

  const channelState = useInboxChannel((event) => {
    if (event.type === "inbox.item") {
      routeInboxItemEvent(event);
      return;
    }
    if (!event.run_id) return;
    const runId = event.run_id;
    if (event.type === "agent.thinking") {
      const thinkingDelta = typeof event.payload.text === "string" ? event.payload.text : "";
      setThinkingByRun((current) => ({
        ...current,
        [runId]: `${current[runId] ?? ""}${thinkingDelta}`.slice(-THINKING_BUFFER_CHARS),
      }));
      return;
    }
    setRunEvents((current) => ({ ...current, [runId]: withEvent(current[runId], event) }));
    setThinkingByRun((current) => ({ ...current, [runId]: "" }));
    const isTerminalStep = event.type === "run.step" && TERMINAL_RUN_STEPS.has(event.step);
    if (isTerminalStep) requestRefresh();
  });
  const isChannelLive = channelState === "live";

  const handleUnauthorized = useCallback(
    (error: unknown): boolean => {
      if (!(error instanceof UnauthorizedError)) return false;
      router.replace("/login");
      return true;
    },
    [router],
  );

  const reloadConnections = useCallback(() => {
    api
      .connections()
      .then(setConnections)
      .catch((error: unknown) => handleUnauthorized(error));
  }, [handleUnauthorized]);

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace("/login");
      return;
    }
    reloadConnections();
    api
      .demoCatalog()
      .then(setDemoCatalog)
      .catch(() => setDemoCatalog(null));
  }, [router, reloadConnections]);

  useEffect(() => {
    const isReconnected = isChannelLive && !wasChannelLive.current;
    wasChannelLive.current = isChannelLive;
    if (isReconnected) setRefreshCount((count) => count + 1);
  }, [isChannelLive]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    let isCancelled = false;
    let isLoading = false;
    const loadInbox = () => {
      if (isLoading) return;
      isLoading = true;
      fetchInboxSnapshot(selectedEmailId, sourceFilter)
        .then((snapshot) => {
          if (isCancelled) return;
          setEmails(snapshot.emails);
          setSelectedEmail(snapshot.selectedEmail);
          setBudgets(snapshot.budgets);
          setSnapshotVersion((version) => version + 1);
          setLoadError(null);
        })
        .catch((error: unknown) => {
          if (isCancelled || handleUnauthorized(error)) return;
          setLoadError("The inbox could not be loaded. Retrying…");
        })
        .finally(() => {
          isLoading = false;
        });
    };
    loadInbox();
    const pollTimer = setInterval(loadInbox, pollIntervalMs(isChannelLive, hasPendingEmails));
    return () => {
      isCancelled = true;
      clearInterval(pollTimer);
    };
  }, [selectedEmailId, sourceFilter, hasPendingEmails, isChannelLive, handleUnauthorized, refreshCount]);

  function selectSourceFilter(nextFilter: InboxChannel | null) {
    setSourceFilter(nextFilter);
    const isSelectedOutsideFilter =
      nextFilter !== null && selectedEmail !== null && selectedEmail.source_type !== nextFilter;
    if (isSelectedOutsideFilter) setSelectedEmailId(null);
  }

  return (
    <ConsoleShell>
      <ConsoleTopBar
        title="Inbox"
        caption={caption}
        actions={
          <>
            <ConnectionBar
              connections={connections}
              onUnauthorized={handleUnauthorized}
              onChanged={reloadConnections}
            />
            {demoCatalog && (
              <button
                type="button"
                onClick={() => setIsDemoPanelOpen(true)}
                className={`${SECONDARY_BUTTON_CLASS} h-9 px-4`}
              >
                Demo scenarios
              </button>
            )}
          </>
        }
      />

      {loadError && (
        <p role="alert" className="border-b border-line bg-danger-soft px-4 py-2 text-sm text-danger md:px-8">
          <span aria-hidden>✕ </span>
          {loadError}
        </p>
      )}

      {demoCatalog && (
        <DemoScenariosPanel
          catalog={demoCatalog}
          isOpen={isDemoPanelOpen}
          onClose={() => setIsDemoPanelOpen(false)}
          onLaunched={requestRefresh}
          onReset={resetInboxView}
        />
      )}

      <InboxMetrics emails={emails} budgets={budgets} />

      <div className="flex flex-1 flex-col gap-4 px-4 py-6 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div role="group" aria-label="Filter messages" className="flex gap-1">
            <FilterTab label="All" isActive={inboxFilter === "all"} onSelect={() => setInboxFilter("all")} />
            <FilterTab
              label="In review"
              count={reviewCount}
              isActive={isReviewFilter}
              onSelect={() => setInboxFilter("review")}
            />
          </div>
          <div role="group" aria-label="Filter by channel" className="flex gap-1">
            <SourceChip
              label="All"
              isActive={sourceFilter === null}
              onSelect={() => selectSourceFilter(null)}
            />
            {SOURCE_FILTERS.map((source) => (
              <SourceChip
                key={source}
                label={SOURCE_LABELS[source]}
                isActive={sourceFilter === source}
                onSelect={() => selectSourceFilter(source)}
              />
            ))}
          </div>
        </div>
        <main className="grid flex-1 items-start gap-8 md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]">
          <section
            aria-label="Messages"
            className={`overflow-hidden rounded-lg border border-line bg-panel ${selectedEmailId ? "hidden md:block" : ""}`}
          >
            {visibleEmails === null ? (
              <EmailListSkeleton />
            ) : isReviewQueueEmpty ? (
              <p className="px-6 py-12 text-sm text-muted">
                No invoices are waiting for a decision.
              </p>
            ) : (
              <EmailList
                emails={visibleEmails}
                selectedEmailId={selectedEmailId}
                onSelect={setSelectedEmailId}
              />
            )}
          </section>
          <section
            aria-label="Message detail"
            className={selectedEmailId ? "" : "hidden md:block"}
          >
            {selectedEmail && selectedEmail.email_id === selectedEmailId ? (
              <EmailDetail
                email={selectedEmail}
                onBack={() => setSelectedEmailId(null)}
                onDecisionChanged={requestRefresh}
                onSelectEmail={setSelectedEmailId}
                runEvents={selectedEmail.run_id ? (runEvents[selectedEmail.run_id] ?? []) : []}
                thinking={selectedEmail.run_id ? (thinkingByRun[selectedEmail.run_id] ?? "") : ""}
                refreshKey={snapshotVersion}
              />
            ) : (
              <p className="py-4 text-sm text-muted">
                {selectedEmailId
                  ? "Loading message…"
                  : "Select a message to see the agent's decision."}
              </p>
            )}
          </section>
        </main>
      </div>
    </ConsoleShell>
  );
}

function FilterTab({
  label,
  count,
  isActive,
  onSelect,
}: {
  label: string;
  count?: number;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onSelect}
      className={`min-h-10 rounded px-3 text-sm font-normal transition-colors focus-visible:outline-2 focus-visible:outline-accent ${isActive ? "bg-accent-wash text-accent" : "text-ink hover:bg-sunken"}`}
    >
      {label}
      {count ? <span className="ml-2 text-accent">{count}</span> : null}
    </button>
  );
}

function SourceChip({
  label,
  isActive,
  onSelect,
}: {
  label: string;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onSelect}
      className={`min-h-8 rounded-full px-3 text-xs font-normal transition-colors focus-visible:outline-2 focus-visible:outline-accent ${isActive ? "bg-accent-wash text-accent" : "bg-sunken text-nav-ink hover:bg-sunken-hover"}`}
    >
      {label}
    </button>
  );
}
