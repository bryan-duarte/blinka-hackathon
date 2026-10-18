import { SCAN_LABELS } from "@/lib/labels";
import type { FileScanStatus } from "@/lib/types";

const SCAN_DETAILS: Record<FileScanStatus, string> = {
  clean: "No threats found.",
  threat: "The file was quarantined and never read by the agent.",
  pending: "The agent reads it once the scan finishes.",
  failed: "The scan did not finish.",
  unsupported: "This file type is not scanned.",
  disabled: "The malware scan is turned off.",
};

const SCAN_NOTE_CLASSES: Record<FileScanStatus, string> = {
  clean: "bg-sunken text-ink",
  threat: "bg-ink text-white",
  pending: "border border-line text-ink",
  failed: "border border-ink text-ink",
  unsupported: "border border-line text-muted",
  disabled: "border border-line text-muted",
};

export function EvidenceBadge({ scanStatus }: { scanStatus: FileScanStatus }) {
  return (
    <p className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-[13px] ${SCAN_NOTE_CLASSES[scanStatus]}`}>
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className={`size-[18px] shrink-0 fill-none stroke-current ${scanStatus === "pending" ? "animate-pulse" : ""}`}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M8 1.75 3 3.75v4c0 3 2.2 5 5 6.25 2.8-1.25 5-3.25 5-6.25v-4z" />
        {scanStatus === "clean" && <path d="m5.8 8 1.6 1.6 2.9-3" />}
        {scanStatus === "threat" && <path d="M8 5.5v3M8 10.5h.01" />}
      </svg>
      <span>
        <span className="font-medium">{SCAN_LABELS[scanStatus]}.</span> {SCAN_DETAILS[scanStatus]}
      </span>
    </p>
  );
}
