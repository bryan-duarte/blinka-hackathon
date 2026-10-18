import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ruleLabel } from "@/lib/labels";
import type { ReasonCount } from "@/lib/types";
import { AXIS_TICK_STYLE, MARK_RADIUS_PX, TOOLTIP_CONTENT_STYLE, chartColors, useReducedMotion } from "./chartTheme";

const ROW_HEIGHT_PX = 32;
const AXIS_LABEL_WIDTH_PX = 190;

export function TopReasonsChart({ reasons }: { reasons: ReasonCount[] }) {
  const colors = chartColors();
  const isReducedMotion = useReducedMotion();
  if (reasons.length === 0) {
    return <p className="text-sm text-muted">No rule has stopped or escalated a bill in this window.</p>;
  }
  const rows = reasons.map((reason) => ({ label: `${reason.rule_id} · ${ruleLabel(reason.rule_id)}`, count: reason.count }));
  return (
    <div style={{ height: rows.length * ROW_HEIGHT_PX + ROW_HEIGHT_PX }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }} barCategoryGap={8}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={AXIS_LABEL_WIDTH_PX}
            tick={AXIS_TICK_STYLE}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={TOOLTIP_CONTENT_STYLE} cursor={{ fill: colors.track }} />
          <Bar
            dataKey="count"
            name="Decisions"
            fill={colors.neutral}
            radius={[0, MARK_RADIUS_PX, MARK_RADIUS_PX, 0]}
            label={{ position: "right", ...AXIS_TICK_STYLE, fill: colors.label }}
            isAnimationActive={!isReducedMotion}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
