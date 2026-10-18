import type { LedgerEntryView, LedgerOutcome, LedgerTab } from "./types";

const TAB_OUTCOMES: Record<Exclude<LedgerTab, "all">, ReadonlySet<LedgerOutcome>> = {
  paid: new Set(["paid", "approved_by_human"]),
  escalated: new Set(["escalated"]),
  stopped: new Set([
    "held",
    "rejected_by_human",
    "duplicate",
    "blocked",
    "not_an_invoice",
    "missing_info",
    "error",
  ]),
};

export function entriesInTab(entries: LedgerEntryView[], tab: LedgerTab): LedgerEntryView[] {
  if (tab === "all") return entries;
  return entries.filter((entry) => TAB_OUTCOMES[tab].has(entry.outcome));
}

export function tabCounts(entries: LedgerEntryView[]): Record<LedgerTab, number> {
  return {
    all: entries.length,
    paid: entriesInTab(entries, "paid").length,
    escalated: entriesInTab(entries, "escalated").length,
    stopped: entriesInTab(entries, "stopped").length,
  };
}
