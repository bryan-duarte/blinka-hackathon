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
    <section className="space-y-2">
      <h3 className={EYEBROW_CLASS}>Evidencia</h3>
      <ul className="divide-y divide-line border-y border-line">
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
      setOpenError("No se pudo abrir el archivo.");
    } finally {
      setIsOpening(false);
    }
  }

  return (
    <li className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0 space-y-0.5">
        <button
          type="button"
          onClick={openEvidence}
          disabled={isOpening}
          className="max-w-full truncate rounded text-left text-sm font-normal text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
        >
          {isOpening ? "Abriendo..." : `${file.filename} ›`}
        </button>
        <p className="text-xs text-muted tabular-nums">
          {EVIDENCE_ROLE_LABELS[file.role]} · {formatBytes(file.size_bytes)}
        </p>
        {openError && (
          <p role="alert" className="text-xs text-danger">
            {openError}
          </p>
        )}
      </div>
      <EvidenceBadge scanStatus={file.scan_status} />
    </li>
  );
}
