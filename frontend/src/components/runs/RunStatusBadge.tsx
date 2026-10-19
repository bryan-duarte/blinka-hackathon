import { STATUS_BADGE_CLASS, STATUS_TONE } from "@/components/settings/styles";
import { RUN_STATUS_LABELS } from "@/lib/labels";
import type { RunStatus } from "@/lib/types";

const RUN_STATUS_CLASSES: Record<RunStatus, string> = {
  pending: STATUS_TONE.neutral,
  running: STATUS_TONE.action,
  completed: STATUS_TONE.settled,
  failed: STATUS_TONE.stopped,
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`${STATUS_BADGE_CLASS} ${RUN_STATUS_CLASSES[status]}`}>
      {status === "running" && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-ink" />}
      {RUN_STATUS_LABELS[status]}
    </span>
  );
}
