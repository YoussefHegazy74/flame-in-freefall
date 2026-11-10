"use client";

import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PairedSeries } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import { ChartFrame } from "@/components/scientific/chart-frame";

const COLORS = ["#4fd8ec", "#f2a04a", "#43d39a", "#b3a4ff", "#edc15d", "#f27575"];

interface ChartRow {
  x: number;
  y: number;
  pair_id?: string;
  series: string;
}

export function PairedScatterChart({
  series,
  leftLabel,
  rightLabel,
  accessibleDescription,
}: {
  series: PairedSeries[];
  leftLabel: string;
  rightLabel: string;
  accessibleDescription: string;
}) {
  const rows: ChartRow[] = series.flatMap((item) =>
    item.points.map((point) => ({
      x: point.x,
      y: point.y,
      pair_id: point.pair_id,
      series: item.label,
    })),
  );
  const xUnit = series[0]?.x_unit ?? "unit not stated";
  const yUnit = series[0]?.y_unit ?? "unit not stated";
  const total = rows.length;

  return (
    <ChartFrame
      title={`${leftLabel} vs ${rightLabel}`}
      description={
        <>
          Backend-verified paired observations only. Units are preserved from the alignment
          response; this chart performs no interpolation, normalization, or unit conversion.
        </>
      }
      unit={yUnit}
      timeUnit={xUnit}
      source={
        <>
          {series.map((item) => item.label).join("; ") || "Paired series"} · {formatNumber(total)}{" "}
          points · {series[0]?.series_id ?? "no series id"}
        </>
      }
      accessibleDescription={accessibleDescription}
      warnings={[
        "A point represents a record-level pair returned by the backend, not a row-number match.",
      ]}
    >
      <div className="h-80 w-full" data-testid="paired-scatter-chart">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 28, left: 8 }}>
            <CartesianGrid stroke="#1d3348" strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="x"
              name={leftLabel}
              unit={` ${xUnit}`}
              tick={{ fill: "#8aa0b4", fontSize: 10 }}
              stroke="#3a5670"
              label={{
                value: `${leftLabel} (${xUnit})`,
                position: "insideBottom",
                offset: -16,
                fill: "#8aa0b4",
                fontSize: 10,
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={rightLabel}
              unit={` ${yUnit}`}
              tick={{ fill: "#8aa0b4", fontSize: 10 }}
              stroke="#3a5670"
              width={64}
              label={{
                value: `${rightLabel} (${yUnit})`,
                angle: -90,
                position: "insideLeft",
                fill: "#8aa0b4",
                fontSize: 10,
              }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{
                background: "#0a1624",
                border: "1px solid #2a4359",
                borderRadius: 8,
                fontSize: 11,
                color: "#dbe7f1",
              }}
              formatter={(value, name) => [formatNumber(Number(value)), String(name)]}
              labelFormatter={() => ""}
            />
            {series.length > 1 ? (
              <Legend wrapperStyle={{ fontSize: 10, color: "#8aa0b4" }} />
            ) : null}
            {series.map((item, index) => (
              <Scatter
                key={item.series_id}
                name={item.label}
                data={item.points.map((point) => ({
                  x: point.x,
                  y: point.y,
                  pair_id: point.pair_id,
                }))}
                fill={COLORS[index % COLORS.length]}
                line={false}
                shape="circle"
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}
