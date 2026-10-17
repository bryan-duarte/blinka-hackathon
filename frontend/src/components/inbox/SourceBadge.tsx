import { SOURCE_LABELS } from "@/lib/labels";
import type { BillSourceType } from "@/lib/types";

const SOURCE_ICON_PATHS: Record<BillSourceType, string[]> = {
  email: ["M2.5 4h11v8h-11z", "M2.5 4.5 8 9l5.5-4.5"],
  upload: ["M2.5 2.5h11v11h-11z", "M5 6l2 2-2 2", "M8.5 10.5H11"],
  chat: ["M2.5 3.5h11v7H7.5l-3 2.5v-2.5h-2z"],
  telegram: ["M13.5 2.5 2.5 7l4 1.5L8 13l2-3.5z", "M6.5 8.5l7-6"],
  whatsapp: [
    "M8 2.5a5.5 5.5 0 0 0-4.7 8.4l-.8 2.6 2.7-.8A5.5 5.5 0 1 0 8 2.5z",
    "M6.3 5.8c0 2.1 1.8 3.9 3.9 3.9l.6-1-1-.6-.5.5a2.6 2.6 0 0 1-1.4-1.4l.5-.5-.6-1z",
  ],
};

type SourceBadgeProps = {
  type: BillSourceType;
  showsLabel?: boolean;
};

export function SourceBadge({ type, showsLabel = false }: SourceBadgeProps) {
  const label = SOURCE_LABELS[type];
  return (
    <span className="inline-flex shrink-0 items-center gap-1 text-xs text-muted" title={label}>
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className="size-4 fill-none stroke-accent"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {SOURCE_ICON_PATHS[type].map((path) => (
          <path key={path} d={path} />
        ))}
      </svg>
      <span className={showsLabel ? undefined : "sr-only"}>{label}</span>
    </span>
  );
}
