import { SCAN_LABELS } from "@/lib/labels";
import type { FileScanStatus } from "@/lib/types";

export function EvidenceBadge({ scanStatus }: { scanStatus: FileScanStatus }) {
  const label = SCAN_LABELS[scanStatus];
  if (scanStatus !== "clean") {
    return <span className="shrink-0 text-xs text-quiet">{label}</span>;
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-line bg-panel px-2 py-0.5 text-xs font-normal text-muted">
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className="size-3 fill-none stroke-accent"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M8 2 3 4v4c0 3 2.2 5 5 6 2.8-1 5-3 5-6V4z" />
        <path d="m5.8 8 1.6 1.6 2.9-3" />
      </svg>
      {label}
    </span>
  );
}
