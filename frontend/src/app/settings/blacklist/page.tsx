"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useReportError } from "@/components/settings/errors";
import {
  CARD_CLASS,
  DANGER_TEXT_BUTTON_CLASS,
  HINT_CLASS,
  INPUT_CLASS,
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  SECTION_HEADING_CLASS,
} from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { IDENTIFIER_KINDS, IDENTIFIER_KIND_LABELS } from "@/lib/labels";
import type { BlacklistEntryView, IdentifierKind } from "@/lib/types";

const REASON_MIN_LENGTH = 3;

export default function BlacklistPage() {
  const reportApiError = useReportError();
  const [entries, setEntries] = useState<BlacklistEntryView[] | null>(null);
  const [kind, setKind] = useState<IdentifierKind>("bank_account");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const canSubmit = value.trim() !== "" && reason.trim().length >= REASON_MIN_LENGTH && !isSaving;

  const reportError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      const message = reportApiError(error, fallbackMessage, fallbackMessage);
      if (message !== null) setPageError(message);
    },
    [reportApiError],
  );

  useEffect(() => {
    api
      .blacklist()
      .then(setEntries)
      .catch((error: unknown) => reportError(error, "The blacklist could not be loaded."));
  }, [reportError]);

  async function addEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setPageError(null);
    try {
      const entry = await api.addBlacklist({ kind, value: value.trim(), reason: reason.trim() });
      setEntries((current) => [
        entry,
        ...(current ?? []).filter((existing) => existing.entry_id !== entry.entry_id),
      ]);
      setValue("");
      setReason("");
    } catch (error) {
      reportError(error, "The entry could not be added to the blacklist.");
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteEntry(entryId: string) {
    setPageError(null);
    try {
      await api.deleteBlacklist(entryId);
      setEntries((current) => current?.filter((entry) => entry.entry_id !== entryId) ?? null);
    } catch (error) {
      reportError(error, "The entry could not be removed from the blacklist.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className={SECTION_HEADING_CLASS}>Blacklist</h2>
        <p className={`${HINT_CLASS} mt-1 max-w-xl`}>
          Any invoice that uses one of these details is held, even if the payee is registered and allowed.
        </p>
      </div>

      <form onSubmit={addEntry} className={`${CARD_CLASS} grid gap-4 p-5 md:grid-cols-[12rem_1fr_1fr_auto] md:items-end`}>
        <div className="space-y-1.5">
          <label htmlFor="blacklist-kind" className={LABEL_CLASS}>
            Type
          </label>
          <select
            id="blacklist-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as IdentifierKind)}
            className={INPUT_CLASS}
          >
            {IDENTIFIER_KINDS.map((identifierKind) => (
              <option key={identifierKind} value={identifierKind}>
                {IDENTIFIER_KIND_LABELS[identifierKind]}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="blacklist-value" className={LABEL_CLASS}>
            Value
          </label>
          <input
            id="blacklist-value"
            value={value}
            placeholder="US-CHASE-55554444"
            onChange={(event) => setValue(event.target.value)}
            className={INPUT_CLASS}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="blacklist-reason" className={LABEL_CLASS}>
            Reason
          </label>
          <input
            id="blacklist-reason"
            value={reason}
            placeholder="Account reported for fraud"
            onChange={(event) => setReason(event.target.value)}
            className={INPUT_CLASS}
          />
        </div>
        <button type="submit" disabled={!canSubmit} className={PRIMARY_BUTTON_CLASS}>
          {isSaving ? "Adding..." : "Add"}
        </button>
      </form>

      {pageError && (
        <p role="alert" className="text-sm text-danger">
          {pageError}
        </p>
      )}

      {entries === null && !pageError && (
        <div aria-hidden className={`${CARD_CLASS} space-y-3 p-5`}>
          {[0, 1, 2].map((row) => (
            <div key={row} className="h-10 animate-pulse rounded bg-sunken" />
          ))}
        </div>
      )}
      {entries?.length === 0 && (
        <p className={`${CARD_CLASS} p-5 text-sm text-muted`}>The blacklist is empty.</p>
      )}
      {entries && entries.length > 0 && (
        <ul className={`${CARD_CLASS} divide-y divide-line`}>
          {entries.map((entry) => (
            <li
              key={entry.entry_id}
              className="grid gap-1 px-5 py-3 md:grid-cols-[12rem_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center md:gap-4"
            >
              <p className="text-xs text-muted md:text-sm">{IDENTIFIER_KIND_LABELS[entry.kind]}</p>
              <p className="truncate text-sm text-ink tabular-nums">{entry.normalized_value}</p>
              <p className="text-sm text-muted">
                {entry.reason}
                <span className="block text-xs">{formatDateTime(entry.created_at)}</span>
              </p>
              <button
                type="button"
                onClick={() => deleteEntry(entry.entry_id)}
                className={`${DANGER_TEXT_BUTTON_CLASS} justify-self-start`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
