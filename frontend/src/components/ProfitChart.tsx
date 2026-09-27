"use client";
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import type { SeriesPoint } from "@/types";

const fmt = (v: number) =>
  `$${Math.round(v).toLocaleString("en-US")}`;

/** Compact axis money: 1.2k / 340 — full precision lives in the tooltip. */
const axisFmt = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1000) return `${(v / 1000).toFixed(a >= 10000 ? 0 : 1)}k`;
  return String(Math.round(v));
};

export function ProfitChart({ data, height = 260 }: { data: SeriesPoint[]; height?: number }) {
  const shaped = data.map(d => ({
    label: d.label,
    earnings: Number(d.earnings_usd),
    spending: Number(d.spending_usd),
    profit: Number(d.profit_usd),
  }));

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        {/* a little left padding so the newest bucket isn't clipped at the edge */}
        <ComposedChart data={shaped} margin={{ top: 8, right: 6, left: 6, bottom: 0 }}>
          <defs>
            <linearGradient id="earn" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.38} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="spend" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.32} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          {/* reversed: the timeline reads right-to-left with the rest of the UI */}
          <XAxis
            dataKey="label"
            reversed
            tick={{ fontSize: 10 }}
            minTickGap={18}
            interval="preserveStartEnd"
            tickMargin={4}
          />
          <YAxis
            orientation="right"
            tick={{ fontSize: 10 }}
            width={44}
            tickFormatter={axisFmt}
          />
          <Tooltip
            contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12, direction: "rtl" }}
            formatter={(v: number, name: string) => [fmt(v), name]}
            labelStyle={{ fontWeight: 700 }}
          />
          <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
          <Area type="monotone" dataKey="earnings" name="الإيرادات" stroke="#10b981" fill="url(#earn)" strokeWidth={2} />
          <Area type="monotone" dataKey="spending" name="المصروفات" stroke="#ef4444" fill="url(#spend)" strokeWidth={2} />
          <Line type="monotone" dataKey="profit" name="الربح" stroke="#0f766e" strokeWidth={2.5} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
