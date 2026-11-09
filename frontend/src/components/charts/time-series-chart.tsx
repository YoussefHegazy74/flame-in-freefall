"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesChannel, SmokeSeries, TelemetrySeries } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import { ChartFrame } from "@/components/scientific/chart-frame";
import { Disclosure } from "@/components/ui/disclosure";

const COLORS = [
  "#4fd8ec",
  "#f2a04a",
  "#43d39a",
  "#b3a4ff",
  "#edc15d",
  "#f27575",
  "#8ceaf6",
  "#f7d98b",
];

interface SeriesGroup {
  key: string;
  unit: string;
  raw: boolean;
  channels: SeriesChannel[];
}

function groupChannels(channels: SeriesChannel[]): SeriesGroup[] {
  const groups = new Map<string, SeriesGroup>();
  for (const channel of channels) {
    const raw = channel.quality_flags.includes("uncalibrated");
    const key = `${channel.unit}::${raw ? "raw" : "standard"}`;
    const existing = groups.get(key);
    if (existing) {
      existing.channels.push(channel);
    } else {
      groups.set(key, { key, unit: channel.unit, raw, channels: [channel] });
    }
  }
  return Array.from(groups.values());
}

function seriesType(series: TelemetrySeries | SmokeSeries): {
  timeKey: string;
  timeUnit: string;
  label: string;
} {
  if (series.time_unit === "ms") {
    return { timeKey: "time_ms", timeUnit: "ms", label: "milliseconds" };
  }
  return { timeKey: "time_s", timeUnit: "s", label: "seconds" };
}

function formatTime(value: number, unit: string): string {
  if (unit === "ms" && Math.abs(value) >= 1000) {
    return `${formatNumber(value / 1000, { maximumSignificantDigits: 4 })} s`;
  }
  return `${formatNumber(value, { maximumSignificantDigits: 6 })} ${unit}`;
}

export function TimeSeriesChart({
  series,
  accession,
  runId,
  sourceFile,
  sourceUrl,
  retrievedAt,
  timeRangeLabel,
}: {
  series: TelemetrySeries | SmokeSeries;
  accession: string;
  runId: string;
  sourceFile: string;
  sourceUrl?: string;
  retrievedAt?: string;
  timeRangeLabel?: string;
}) {
  const groups = useMemo(() => groupChannels(series.channels), [series.channels]);
  const type = seriesType(series);
  const points = series.points;

  if (groups.length === 0) {
    return (
      <div className="surface p-5 text-sm text-ink-300">
        No plottable channels were returned. No chart is drawn.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const titleUnit = group.unit === "not stated" ? "unit not stated" : group.unit;
        const warning =
          group.unit === "not stated"
            ? "The source does not state a unit for these channels. The axis is a raw signal axis, not a physical measurement."
            : group.raw
              ? "These channels are raw and uncalibrated. They are not calibrated physical measurements."
              : undefined;
        const description = `${group.channels.length} channel${group.channels.length === 1 ? "" : "s"} · ${points.length} returned points · ${group.raw ? "raw signal" : "standard signal"}`;
        const showLegend = group.channels.length > 1;
        return (
          <ChartFrame
            key={group.key}
            title={`${accession} time series — ${titleUnit}${group.raw ? " (raw)" : ""}`}
            description={description}
            unit={titleUnit}
            timeUnit={type.timeUnit}
            warnings={warning ? [warning] : []}
            source={
              <span>
                <span className="mono text-ink-300">{runId}</span>
                <br />
                Source file: <span className="mono">{sourceFile}</span>
                {retrievedAt ? <> · retrieved {retrievedAt}</> : null}
                {sourceUrl ? (
                  <>
                    {" "}
                    ·{" "}
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-cyan-300 hover:text-cyan-200 focus-ring"
                    >
                      NASA source
                    </a>
                  </>
                ) : null}
              </span>
            }
            footer={
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>Time axis: {type.label}</span>
                <span>Returned points: {formatNumber(points.length)}</span>
                <span>Sentinel rows excluded: {formatNumber(series.excluded_sentinel_rows)}</span>
                {timeRangeLabel ? <span>Requested range: {timeRangeLabel}</span> : null}
                <span>Missing values are gaps; no interpolation.</span>
              </div>
            }
            accessibleDescription={`${accession} time-series chart. Run ${runId}. Channels: ${group.channels
              .map((channel) => channel.channel_name_canonical)
              .join(", ")}. Y unit: ${titleUnit}. X unit: ${type.timeUnit}. ${points.length} points. Missing values are not zero.`}
          >
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: showLegend ? 34 : 10, right: 18, bottom: 30, left: 12 }}>
                  <CartesianGrid stroke="#162844" strokeDasharray="3 4" />
                  <XAxis
                    dataKey={type.timeKey}
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fill: "#8499b7", fontSize: 10 }}
                    tickFormatter={(value: number) => formatNumber(value, { maximumSignificantDigits: 4 })}
                    label={{
                      value: `Time (${type.timeUnit})`,
                      position: "insideBottom",
                      offset: -14,
                      fill: "#8499b7",
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    tick={{ fill: "#8499b7", fontSize: 10 }}
                    tickFormatter={(value: number) => formatNumber(value, { maximumSignificantDigits: 4 })}
                    width={64}
                    label={{
                      value: group.unit === "not stated" ? "signal (unit not stated)" : group.unit,
                      angle: -90,
                      position: "insideLeft",
                      fill: "#8499b7",
                      fontSize: 10,
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#081120",
                      border: "1px solid #22395c",
                      borderRadius: 10,
                      color: "#e7effb",
                      fontSize: 11,
                    }}
                    labelFormatter={(value) =>
                      `t = ${formatTime(Number(value), type.timeUnit)}`
                    }
                    formatter={(value, name) => [
                      value === null || value === undefined
                        ? "missing (gap)"
                        : formatNumber(Number(value), { maximumSignificantDigits: 6 }),
                      String(name),
                    ]}
                  />
                  {showLegend ? (
                    <Legend
                      verticalAlign="top"
                      align="right"
                      height={24}
                      wrapperStyle={{ fontSize: 10, color: "#a9bad3", paddingBottom: 8 }}
                      formatter={(value) => (
                        <span style={{ color: "#a9bad3" }}>{String(value)}</span>
                      )}
                    />
                  ) : null}
                  {group.channels.map((channel, index) => (
                    <Line
                      key={channel.channel_name_canonical}
                      type="linear"
                      dataKey={channel.channel_name_canonical}
                      name={channel.channel_name_canonical}
                      stroke={COLORS[index % COLORS.length]}
                      strokeWidth={1.5}
                      strokeDasharray={group.raw ? "4 3" : undefined}
                      dot={false}
                      activeDot={{ r: 3 }}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <Disclosure summary="View returned series values" className="mt-2">
              <p className="mb-2 text-[11px] text-ink-400">
                Showing {formatNumber(Math.min(100, points.length))} of{" "}
                {formatNumber(points.length)} returned points. Missing values are shown as a dash,
                never zero.
              </p>
              <div className="table-scroll max-h-72 overflow-y-auto rounded border border-navy-700/60">
                <table className="w-full min-w-[520px] text-left text-[10px]">
                  <caption className="sr-only">Returned time-series values</caption>
                  <thead className="sticky top-0 bg-navy-900">
                    <tr>
                      <th scope="col" className="px-2 py-1.5 font-mono text-ink-400">
                        {type.timeKey}
                      </th>
                      {group.channels.map((channel) => (
                        <th
                          key={channel.channel_name_canonical}
                          scope="col"
                          className="px-2 py-1.5 font-mono text-ink-400"
                        >
                          {channel.channel_name_canonical}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {points.slice(0, 100).map((point, index) => (
                      <tr key={index} className="border-t border-navy-800">
                        <td className="px-2 py-1 font-mono text-ink-300">
                          {formatNumber(Number(point[type.timeKey]), {
                            maximumSignificantDigits: 8,
                          })}
                        </td>
                        {group.channels.map((channel) => {
                          const value = point[channel.channel_name_canonical];
                          return (
                            <td
                              key={channel.channel_name_canonical}
                              className="px-2 py-1 font-mono text-ink-300"
                            >
                              {value === null || value === undefined
                                ? "—"
                                : formatNumber(value, { maximumSignificantDigits: 8 })}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Disclosure>
          </ChartFrame>
        );
      })}
    </div>
  );
}
