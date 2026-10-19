export const INPUT_CLASS =
  "h-10 w-full rounded border border-selection bg-panel px-4 text-sm text-ink transition-colors focus-visible:border-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ink disabled:opacity-60";

export const LABEL_CLASS = "text-sm font-medium text-ink";

export const HINT_CLASS = "text-xs text-muted";

export const PRIMARY_BUTTON_CLASS =
  "inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-ink bg-ink px-5 text-[15px] font-medium whitespace-nowrap text-white transition-opacity hover:opacity-86 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-not-allowed disabled:opacity-60";

export const SECONDARY_BUTTON_CLASS =
  "inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-ink bg-transparent px-5 text-[15px] font-medium whitespace-nowrap text-ink transition-colors hover:bg-ink hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent disabled:hover:text-ink";

export const QUIET_BUTTON_CLASS =
  "rounded px-1 text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50";

export const DANGER_TEXT_BUTTON_CLASS =
  "rounded px-1 text-sm text-danger hover:underline focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50";

export const CARD_CLASS = "rounded-lg border border-line bg-panel";

export const EYEBROW_CLASS = "text-sm font-bold text-muted [font-variant-caps:all-small-caps]";

export const SECTION_HEADING_CLASS = "text-xl leading-[1.4] font-medium tracking-[-0.02em] text-ink";

export const PAGE_HEADING_CLASS = "font-serif text-[26px] leading-[1.13] text-ink";

const FILTER_TAB_BASE =
  "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm font-normal whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

export function filterTabClass(isActive: boolean): string {
  return `${FILTER_TAB_BASE} ${isActive ? "border-ink bg-ink text-white" : "border-line bg-panel text-ink hover:border-ink"}`;
}

/*
  Monochrome status tones, told apart by fill rather than hue:
  settled is solid ink, needs-action is an ink outline, stopped is an ash
  wash, neutral is a hairline in muted text.
*/
export const STATUS_TONE = {
  settled: "border-ink bg-ink text-white",
  action: "border-ink bg-panel text-ink font-medium",
  stopped: "border-transparent bg-ash text-ink",
  neutral: "border-line bg-panel text-muted",
} as const;

export const STATUS_BADGE_CLASS =
  "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs whitespace-nowrap";
