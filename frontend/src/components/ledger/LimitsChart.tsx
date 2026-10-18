import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatMoney, formatPercent } from "@/lib/format";
import type { LimitUsage } from "@/lib/types";
import {
  AXIS_TICK_STYLE,
  MARK_RADIUS_PX,
  TOOLTIP_CONTENT_STYLE,
  chartColors,
  useReducedMotion,
} from "./chartTheme";

const ROW_HEIGHT_PX = 36;
const AXIS_LABEL_WIDTH_PX = 170;
const NEAR_LIMIT_RATIO = 0.9;
const FULL_RATIO = 1;
const LIMIT_REACHED_LABEL = "Limit reached";
const FULL_PERCENT = 100;

type LimitRow = {
  label: string;
  spentPercent: number;
  remainingPercent: number;
  spentUsd: number;
  limitUsd: number;
  ratio: number;
  usageLabel: string;
};

export function LimitsChart({ limits }: { limits: LimitUsage[] }) {
  const colors = chartColors();
  const isReducedMotion = useReducedMotion();
  const rows = limits.filter((limit) => limit.limit_usd !== null).map(toLimitRow);
  if (rows.length === 0) {
    return <p className="text-sm text-muted">No limits are configured for this period.</p>;
  }
  return (
    <div style={{ height: rows.length * ROW_HEIGHT_PX + ROW_HEIGHT_PX }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 96, bottom: 0, left: 0 }} barCategoryGap={8}>
          <XAxis type="number" hide domain={[0, FULL_PERCENT]} />
          <YAxis
            type="category"
            dataKey="label"
            width={AXIS_LABEL_WIDTH_PX}
            tick={AXIS_TICK_STYLE}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_CONTENT_STYLE}
            cursor={{ fill: colors.track }}
            formatter={(_value, name, tooltipEntry) => {
              const row = tooltipEntry.payload as LimitRow;
              const shownUsd = name === "Spent" ? row.spentUsd : Math.max(0, row.limitUsd - row.spentUsd);
              return [`USD ${formatMoney(shownUsd, null)} of USD ${formatMoney(row.limitUsd, null)}`, name];
            }}
          />
          <Bar dataKey="spentPercent" name="Spent" stackId="usage" isAnimationActive={!isReducedMotion}>
            {rows.map((row) => (
              <Cell key={row.label} fill={row.ratio >= NEAR_LIMIT_RATIO ? colors.stopped : colors.escalated} />
            ))}
          </Bar>
          <Bar
            dataKey="remainingPercent"
            name="Remaining"
            stackId="usage"
            fill={colors.track}
            radius={[0, MARK_RADIUS_PX, MARK_RADIUS_PX, 0]}
            isAnimationActive={!isReducedMotion}
          >
            <LabelList dataKey="usageLabel" position="right" style={{ ...AXIS_TICK_STYLE, fill: colors.label }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function toLimitRow(limit: LimitUsage): LimitRow {
  const limitUsd = Number(limit.limit_usd);
  const spentUsd = Number(limit.spent_usd);
  const ratio = limitUsd > 0 ? spentUsd / limitUsd : FULL_RATIO;
  const spentPercent = Math.min(ratio, FULL_RATIO) * FULL_PERCENT;
  return {
    label: limit.payee_currency ? `${limit.label} · ${limit.payee_currency}` : limit.label,
    spentPercent,
    remainingPercent: FULL_PERCENT - spentPercent,
    spentUsd,
    limitUsd,
    ratio,
    usageLabel: ratio >= FULL_RATIO ? LIMIT_REACHED_LABEL : formatPercent(ratio),
  };
}
