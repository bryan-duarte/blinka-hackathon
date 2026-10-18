import { useEffect, useRef } from "react";
import { SECONDARY_BUTTON_CLASS, SECTION_HEADING_CLASS } from "@/components/settings/styles";

const DANGER_BUTTON_CLASS =
  "inline-flex h-10 items-center justify-center rounded border border-night bg-night px-6 text-sm font-normal text-white transition-colors hover:bg-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60";

type ResetDemoDialogProps = {
  isOpen: boolean;
  isResetting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ResetDemoDialog({ isOpen, isResetting, onCancel, onConfirm }: ResetDemoDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={(event) => {
        event.preventDefault();
        if (!isResetting) onCancel();
      }}
      aria-labelledby="reset-demo-title"
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded border border-line bg-panel p-8 text-ink backdrop:bg-night/30"
    >
      <div className="flex flex-col gap-4">
        <h2 id="reset-demo-title" className={SECTION_HEADING_CLASS}>
          Reset the demo?
        </h2>
        <p className="text-sm leading-[1.4] text-nav-ink">
          This deletes every message, decision, payment and file for the demo account and restores
          the initial data. Connected mailboxes are kept.
        </p>
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" onClick={onCancel} disabled={isResetting} className={SECONDARY_BUTTON_CLASS}>
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={isResetting} className={DANGER_BUTTON_CLASS}>
            {isResetting ? "Resetting…" : "Reset demo"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
