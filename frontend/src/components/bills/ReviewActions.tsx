import { useId, useState } from "react";
import {
  LABEL_CLASS,
  PRIMARY_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
  SECTION_HEADING_CLASS,
} from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";

type ReviewActionsProps = {
  billId: string;
  onResolved: () => void;
};

type ReviewAction = "approve" | "reject";

const NOTE_MIN_LENGTH = 3;
const NOTE_MAX_LENGTH = 500;
const ALREADY_RESOLVED_MESSAGE = "Another person already resolved this invoice.";
const GENERIC_FAILURE_MESSAGE = "The decision could not be recorded. Try again.";

export function ReviewActions({ billId, onResolved }: ReviewActionsProps) {
  const noteId = useId();
  const [note, setNote] = useState("");
  const [pendingAction, setPendingAction] = useState<ReviewAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const trimmedNote = note.trim();
  const hasValidNote = trimmedNote.length >= NOTE_MIN_LENGTH;
  const isBusy = pendingAction !== null;

  async function resolve(action: ReviewAction) {
    setPendingAction(action);
    setActionError(null);
    try {
      if (action === "approve") {
        await api.approveBill(billId, trimmedNote);
      } else {
        await api.rejectBill(billId, trimmedNote);
      }
      onResolved();
    } catch (error) {
      const isAlreadyResolved = error instanceof ApiError && error.status === HTTP_CONFLICT;
      setActionError(isAlreadyResolved ? ALREADY_RESOLVED_MESSAGE : GENERIC_FAILURE_MESSAGE);
      if (isAlreadyResolved) onResolved();
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 border-t border-line pt-6">
      <div className="space-y-1">
        <h3 className={SECTION_HEADING_CLASS}>Your decision</h3>
        <p className="text-sm text-muted">
          Approving accepts the review points. Caps, the blacklist and the budget are checked again before
          paying, so the invoice can still be held.
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <label htmlFor={noteId} className={LABEL_CLASS}>
          Note for the record (required)
        </label>
        <textarea
          id={noteId}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          minLength={NOTE_MIN_LENGTH}
          maxLength={NOTE_MAX_LENGTH}
          rows={2}
          disabled={isBusy}
          placeholder="E.g. confirmed with the vendor by phone"
          className="block w-full resize-y rounded border border-line bg-panel px-4 py-2 text-sm leading-[1.4] text-ink placeholder:text-muted transition-colors focus-visible:border-accent focus-visible:outline-1 focus-visible:outline-accent disabled:opacity-60"
        />
        <p className="text-right text-xs text-muted tabular-nums">
          {note.length}/{NOTE_MAX_LENGTH}
        </p>
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-danger">
          <span aria-hidden>✕ </span>
          {actionError}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => resolve("approve")}
          disabled={!hasValidNote || isBusy}
          className={PRIMARY_BUTTON_CLASS}
        >
          {pendingAction === "approve" ? "Approving..." : "Approve payment"}
        </button>
        <button
          type="button"
          onClick={() => resolve("reject")}
          disabled={!hasValidNote || isBusy}
          className={SECONDARY_BUTTON_CLASS}
        >
          {pendingAction === "reject" ? "Rejecting..." : "Reject"}
        </button>
      </div>
    </div>
  );
}
