"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useReportError } from "@/components/settings/errors";
import {
  CARD_CLASS,
  DANGER_TEXT_BUTTON_CLASS,
  HINT_CLASS,
  QUIET_BUTTON_CLASS,
  SECTION_HEADING_CLASS,
} from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { HumanAction, MemoryView } from "@/lib/types";

const HUMAN_ACTION_BADGES: Record<HumanAction, { glyph: string; label: string; className: string }> = {
  approved: { glyph: "✓", label: "Approved", className: "border-transparent bg-sunken text-nav-ink" },
  rejected: { glyph: "✕", label: "Rejected", className: "border-night bg-panel text-night" },
};

type PayeeMemories = { payeeKey: string; payee: string; memories: MemoryView[] };

function groupByPayee(memories: MemoryView[]): PayeeMemories[] {
  const groups = new Map<string, PayeeMemories>();
  for (const memory of memories) {
    const group = groups.get(memory.payee_key) ?? { payeeKey: memory.payee_key, payee: memory.payee, memories: [] };
    group.memories.push(memory);
    groups.set(memory.payee_key, group);
  }
  return [...groups.values()];
}

export default function MemoriesPage() {
  const reportApiError = useReportError();
  const [memories, setMemories] = useState<MemoryView[] | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const reportError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      const message = reportApiError(error, fallbackMessage, fallbackMessage);
      if (message !== null) setPageError(message);
    },
    [reportApiError],
  );

  const loadMemories = useCallback(() => {
    api
      .memories()
      .then(setMemories)
      .catch((error: unknown) => reportError(error, "The agent memory could not be loaded."));
  }, [reportError]);

  useEffect(loadMemories, [loadMemories]);

  async function deleteMemory(memory: MemoryView) {
    setPendingDeleteId(null);
    setPageError(null);
    setMemories((current) => current?.filter((existing) => existing.memory_id !== memory.memory_id) ?? null);
    try {
      await api.deleteMemory(memory.payee_key, memory.memory_id);
    } catch (error) {
      reportError(error, "The memory could not be deleted.");
      loadMemories();
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className={SECTION_HEADING_CLASS}>Agent memory</h2>
        <p className={`${HINT_CLASS} mt-1 max-w-xl`}>
          Lessons the agent keeps from approvals and rejections you asked it to remember. It reads them as context for
          the same payee. They never override caps, budgets, the blocked list or the allowed payees.
        </p>
      </div>

      {pageError && (
        <p role="alert" className="text-sm text-danger">
          {pageError}
        </p>
      )}

      {memories === null && !pageError && (
        <div aria-hidden className={`${CARD_CLASS} space-y-3 p-5`}>
          {[0, 1, 2].map((row) => (
            <div key={row} className="h-10 animate-pulse rounded bg-sunken" />
          ))}
        </div>
      )}
      {memories?.length === 0 && (
        <p className={`${CARD_CLASS} p-5 text-sm text-muted`}>
          No memories yet. Tick “Remember this” when you approve or reject an invoice.
        </p>
      )}
      {memories &&
        groupByPayee(memories).map((group) => (
          <section key={group.payeeKey} className="space-y-2">
            <h3 className="text-sm font-medium text-ink">{group.payee}</h3>
            <ul className={`${CARD_CLASS} divide-y divide-line`}>
              {group.memories.map((memory) => (
                <MemoryRow
                  key={memory.memory_id}
                  memory={memory}
                  isConfirmingDelete={pendingDeleteId === memory.memory_id}
                  onAskDelete={() => setPendingDeleteId(memory.memory_id)}
                  onCancelDelete={() => setPendingDeleteId(null)}
                  onConfirmDelete={() => deleteMemory(memory)}
                />
              ))}
            </ul>
          </section>
        ))}
    </div>
  );
}

type MemoryRowProps = {
  memory: MemoryView;
  isConfirmingDelete: boolean;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
};

function MemoryRow({ memory, isConfirmingDelete, onAskDelete, onCancelDelete, onConfirmDelete }: MemoryRowProps) {
  const badge = HUMAN_ACTION_BADGES[memory.human_action];
  return (
    <li className="grid gap-2 px-5 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:gap-4">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-normal ${badge.className}`}
          >
            <span aria-hidden>{badge.glyph}</span>
            {badge.label}
          </span>
          <span className="text-xs text-muted">{formatDateTime(memory.updated_at)}</span>
        </div>
        <p className="text-sm text-ink">{memory.lesson}</p>
        <p className="text-sm text-muted">{memory.situation}</p>
        {memory.applies_when && <p className="text-xs text-muted">Applies when: {memory.applies_when}</p>}
        {memory.note_excerpt && (
          <blockquote className="border-l border-line pl-3 text-xs text-muted">“{memory.note_excerpt}”</blockquote>
        )}
        {memory.source_bill_id && (
          <Link href={`/bills?bill=${memory.source_bill_id}`} className="text-xs text-ink hover:underline">
            Open the source invoice →
          </Link>
        )}
      </div>
      <div className="flex items-start gap-3 justify-self-start">
        {isConfirmingDelete ? (
          <>
            <button type="button" onClick={onConfirmDelete} className={DANGER_TEXT_BUTTON_CLASS}>
              Delete memory
            </button>
            <button type="button" onClick={onCancelDelete} className={QUIET_BUTTON_CLASS}>
              Keep
            </button>
          </>
        ) : (
          <button type="button" onClick={onAskDelete} className={DANGER_TEXT_BUTTON_CLASS}>
            Delete
          </button>
        )}
      </div>
    </li>
  );
}
