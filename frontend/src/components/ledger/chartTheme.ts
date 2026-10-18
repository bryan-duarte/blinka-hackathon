import { useSyncExternalStore } from "react";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

const TOKEN_FALLBACKS = {
  paid: ["--color-muted", "#73737c"],
  escalated: ["--color-iris", "#635bff"],
  stopped: ["--color-night", "#010110"],
  neutral: ["--color-nav-ink", "#010110"],
  track: ["--color-sunken", "#f7f7f7"],
  grid: ["--color-ash", "#d9d9d9"],
  axis: ["--color-muted", "#73737c"],
  label: ["--color-ink", "#010110"],
  surface: ["--color-panel", "#ffffff"],
} as const;

export type ChartColorName = keyof typeof TOKEN_FALLBACKS;
export type ChartColors = Record<ChartColorName, string>;

export function chartColors(): ChartColors {
  const rootStyle = typeof window === "undefined" ? null : getComputedStyle(document.documentElement);
  return Object.fromEntries(
    Object.entries(TOKEN_FALLBACKS).map(([name, [token, fallback]]) => [
      name,
      rootStyle?.getPropertyValue(token).trim() || fallback,
    ]),
  ) as ChartColors;
}

export const AXIS_TICK_STYLE = {
  fontSize: 12,
  fontWeight: 300,
  fill: TOKEN_FALLBACKS.axis[1],
  fontVariantNumeric: "tabular-nums",
};

export const TOOLTIP_CONTENT_STYLE = {
  background: TOKEN_FALLBACKS.surface[1],
  border: `1px solid ${TOKEN_FALLBACKS.grid[1]}`,
  borderRadius: 4,
  boxShadow: "none",
  fontSize: 12,
  fontWeight: 300,
  color: TOKEN_FALLBACKS.label[1],
};

export const MARK_GAP_PX = 2;
export const MARK_RADIUS_PX = 4;

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeToMotionPreference, prefersReducedMotion, () => false);
}

function subscribeToMotionPreference(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function prefersReducedMotion(): boolean {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}
