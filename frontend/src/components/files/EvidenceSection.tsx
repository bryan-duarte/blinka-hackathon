import { useState } from "react";
import { EYEBROW_CLASS, PRIMARY_BUTTON_CLASS, SECONDARY_BUTTON_CLASS } from "@/components/settings/styles";
import { api, canViewInBrowser } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { EVIDENCE_ROLE_LABELS } from "@/lib/labels";
import type { EvidenceFileView } from "@/lib/types";
import { EvidenceBadge } from "./EvidenceBadge";

const FILE_BUTTON_SIZE = "h-9 px-4 text-sm";

type FileAction = "view" | "download";

export function EvidenceSection({ evidence }: { evidence: EvidenceFileView[] }) {
  if (evidence.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h3 className={EYEBROW_CLASS}>{evidence.length === 1 ? "Original invoice file" : `Original files (${evidence.length})`}</h3>
      <ul className="flex flex-col gap-3">
        {evidence.map((file) => (
          <EvidenceRow key={file.file_id} file={file} />
        ))}
      </ul>
    </section>
  );
}

function fileTypeLabel(file: EvidenceFileView): string {
  const extension = file.filename.split(".").pop();
  return extension && extension !== file.filename ? extension.toUpperCase() : "File";
}

function EvidenceRow({ file }: { file: EvidenceFileView }) {
  const [pendingAction, setPendingAction] = useState<FileAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const isViewable = canViewInBrowser(file);
  const isQuarantined = file.scan_status === "threat";

  async function runAction(action: FileAction) {
    setPendingAction(action);
    setActionError(null);
    try {
      await (action === "view" ? api.openFile(file) : api.downloadFile(file));
    } catch {
      setActionError(action === "view" ? "The file could not be opened." : "The file could not be downloaded.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel p-3.5">
        <span
          aria-hidden
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sunken text-[10px] font-bold tracking-normal text-ink"
        >
          {fileTypeLabel(file)}
        </span>
        <span className="min-w-0 flex-[1_1_12rem]">
          <span className="block truncate font-medium" title={file.filename}>
            {file.filename}
          </span>
          <span className="text-xs text-muted tabular-nums">
            {EVIDENCE_ROLE_LABELS[file.role]} · {formatBytes(file.size_bytes)}
          </span>
        </span>
        {!isQuarantined && (
          <span className="flex shrink-0 gap-2">
            {isViewable && (
              <button
                type="button"
                onClick={() => runAction("view")}
                disabled={pendingAction !== null}
                aria-label={`View ${file.filename} in a new tab`}
                className={`${SECONDARY_BUTTON_CLASS} ${FILE_BUTTON_SIZE}`}
              >
                {pendingAction === "view" ? "Opening…" : "View"}
              </button>
            )}
            <button
              type="button"
              onClick={() => runAction("download")}
              disabled={pendingAction !== null}
              aria-label={`Download ${file.filename}`}
              className={`${PRIMARY_BUTTON_CLASS} ${FILE_BUTTON_SIZE}`}
            >
              <svg
                aria-hidden
                viewBox="0 0 16 16"
                className="size-4 fill-none stroke-current"
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10" />
              </svg>
              {pendingAction === "download" ? "Downloading…" : "Download"}
            </button>
          </span>
        )}
      </div>
      <EvidenceBadge scanStatus={file.scan_status} />
      {actionError && (
        <p role="alert" className="text-xs text-danger">
          {actionError}
        </p>
      )}
    </li>
  );
}
