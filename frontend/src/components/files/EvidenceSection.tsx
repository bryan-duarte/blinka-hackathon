import { useState } from "react";
import { EYEBROW_CLASS } from "@/components/settings/styles";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { EVIDENCE_ROLE_LABELS } from "@/lib/labels";
import type { EvidenceFileView } from "@/lib/types";
import { EvidenceBadge } from "./EvidenceBadge";

export function EvidenceSection({ evidence }: { evidence: EvidenceFileView[] }) {
  if (evidence.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h3 className={EYEBROW_CLASS}>{evidence.length === 1 ? "Attachment" : `Attachments (${evidence.length})`}</h3>
      <ul className="flex flex-col gap-3">
        {evidence.map((file) => (
          <EvidenceRow key={file.file_id} file={file} />
        ))}
      </ul>
    </section>
  );
}

function EvidenceRow({ file }: { file: EvidenceFileView }) {
  const [isOpening, setIsOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  async function openEvidence() {
    setIsOpening(true);
    setOpenError(null);
    try {
      await api.openFile(file);
    } catch {
      setOpenError("The file could not be opened.");
    } finally {
      setIsOpening(false);
    }
  }

  return (
    <li className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={openEvidence}
        disabled={isOpening}
        aria-label={`Open ${file.filename}`}
        className="flex w-full items-center gap-3 rounded-lg border border-ink bg-panel p-3.5 text-left text-ink transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-wait disabled:opacity-60"
      >
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          className="size-6 shrink-0 fill-none stroke-current"
          strokeWidth={1.2}
          strokeLinejoin="round"
        >
          <path d="M4 1.5h5.5L12.5 4.5v10h-8.5z" />
          <path d="M9.5 1.5v3h3" />
        </svg>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{file.filename}</span>
          <span className="text-xs text-muted tabular-nums">
            {EVIDENCE_ROLE_LABELS[file.role]} · {formatBytes(file.size_bytes)} · {isOpening ? "Opening…" : "Open file"}
          </span>
        </span>
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          className="size-4 shrink-0 fill-none stroke-current"
          strokeWidth={1.5}
          strokeLinecap="round"
        >
          <path d="M6 3.5h6.5V10" />
          <path d="M12.5 3.5 4 12" />
        </svg>
      </button>
      <EvidenceBadge scanStatus={file.scan_status} />
      {openError && (
        <p role="alert" className="text-xs text-danger">
          {openError}
        </p>
      )}
    </li>
  );
}
