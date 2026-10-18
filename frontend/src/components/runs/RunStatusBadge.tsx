import { RUN_STATUS_LABELS } from "@/lib/labels";
import type { RunStatus } from "@/lib/types";

const RUN_STATUS_CLASSES: Record<RunStatus, string> = {
  pending: "border-line bg-panel text-muted",
  running: "border-transparent bg-accent-wash text-accent",
  completed: "border-transparent bg-sunken text-nav-ink",
  failed: "border-night bg-panel text-night",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-normal ${RUN_STATUS_CLASSES[status]}`}
    >
      {RUN_STATUS_LABELS[status]}
    </span>
  );
}
