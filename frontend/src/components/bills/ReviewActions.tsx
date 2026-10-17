import { useId, useState } from "react";
import { SECTION_HEADING_CLASS } from "@/components/settings/styles";
import { ApiError, HTTP_CONFLICT, api } from "@/lib/api";

type ReviewActionsProps = {
  billId: string;
  onResolved: () => void;
};

type ReviewAction = "approve" | "reject";

const NOTE_MIN_LENGTH = 3;
const NOTE_MAX_LENGTH = 500;
const ALREADY_RESOLVED_MESSAGE = "Esta factura ya fue resuelta por otra persona.";
const GENERIC_FAILURE_MESSAGE = "No se pudo registrar la decisión. Intenta de nuevo.";

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
    <div className="space-y-3 rounded-md border border-line bg-sunken p-4">
      <div className="space-y-1">
        <h3 className={SECTION_HEADING_CLASS}>Tu decisión</h3>
        <p className="text-sm text-muted">
          Aprobar acepta los puntos en revisión. Los topes, la lista negra y el presupuesto se vuelven a revisar
          antes de pagar, así que la factura puede quedar frenada.
        </p>
      </div>
      <div className="space-y-1">
        <label htmlFor={noteId} className="text-xs font-medium text-ink">
          Nota para el registro (obligatoria)
        </label>
        <textarea
          id={noteId}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          minLength={NOTE_MIN_LENGTH}
          maxLength={NOTE_MAX_LENGTH}
          rows={2}
          disabled={isBusy}
          placeholder="Ej.: confirmado con el proveedor por teléfono"
          className="block w-full resize-y rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:opacity-60"
        />
        <p className="text-right text-xs text-muted tabular-nums">
          {note.length}/{NOTE_MAX_LENGTH}
        </p>
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-danger">
          {actionError}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => resolve("approve")}
          disabled={!hasValidNote || isBusy}
          className="h-10 rounded-md bg-accent px-4 text-sm font-medium text-white transition-colors hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pendingAction === "approve" ? "Aprobando..." : "Aprobar pago"}
        </button>
        <button
          type="button"
          onClick={() => resolve("reject")}
          disabled={!hasValidNote || isBusy}
          className="h-10 rounded-md border border-danger/40 bg-panel px-4 text-sm font-medium text-danger transition-colors hover:bg-danger-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pendingAction === "reject" ? "Rechazando..." : "Rechazar"}
        </button>
      </div>
    </div>
  );
}
