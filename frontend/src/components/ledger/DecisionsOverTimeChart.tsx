import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatShortDate } from "@/lib/format";
import type { LedgerTimelinePoint } from "@/lib/types";
import {
  AXIS_TICK_STYLE,
  MARK_GAP_PX,
  MARK_RADIUS_PX,
  TOOLTIP_CONTENT_STYLE,
  chartColors,
  useReducedMotion,
} from "./chartTheme";

const CHART_HEIGHT_PX = 240;
const SERIES = [
  { key: "paid", label: "Paid" },
  { key: "escalated", label: "Escalated" },
  { key: "stopped", label: "Stopped" },
] as const;

export function DecisionsOverTimeChart({ timeline }: { timeline: LedgerTimelinePoint[] }) {
  const colors = chartColors();
  const isReducedMotion = useReducedMotion();
  const lastSeries = SERIES[SERIES.length - 1].key;
  return (
    <div style={{ height: CHART_HEIGHT_PX }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={timeline} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={colors.grid} />
          <XAxis
            dataKey="bucket"
            tickFormatter={(bucket: string) => formatShortDate(bucket)}
            tick={AXIS_TICK_STYLE}
            axisLine={{ stroke: colors.grid }}
            tickLine={false}
            minTickGap={16}
          />
          <YAxis allowDecimals={false} tick={AXIS_TICK_STYLE} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={TOOLTIP_CONTENT_STYLE}
            cursor={{ fill: colors.track }}
            labelFormatter={(bucket) => `Week of ${formatShortDate(String(bucket))}`}
          />
          <Legend itemSorter={null} iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12, color: colors.axis }} />
          {SERIES.map((series) => (
            <Bar
              key={series.key}
              dataKey={series.key}
              name={series.label}
              stackId="decisions"
              fill={colors[series.key]}
              stroke={colors.surface}
              strokeWidth={MARK_GAP_PX}
              radius={series.key === lastSeries ? [MARK_RADIUS_PX, MARK_RADIUS_PX, 0, 0] : 0}
              isAnimationActive={!isReducedMotion}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
