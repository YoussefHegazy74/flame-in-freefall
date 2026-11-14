"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Search } from "lucide-react";
import type { SeriesChannel } from "@/lib/api/types";
import { MAX_CHANNELS } from "@/lib/series";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface ChannelGroup {
  key: string;
  unit: string;
  raw: boolean;
  channels: SeriesChannel[];
}

function groupChannels(channels: SeriesChannel[]): ChannelGroup[] {
  const groups = new Map<string, ChannelGroup>();
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

export function ChannelPicker({
  channels,
  selected,
  onChange,
  max = MAX_CHANNELS,
  disabled = false,
}: {
  channels: SeriesChannel[];
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [rawOnly, setRawOnly] = useState(false);
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    return channels.filter((channel) => {
      if (rawOnly && !channel.quality_flags.includes("uncalibrated")) return false;
      if (!text) return true;
      return (
        channel.channel_name_canonical.toLowerCase().includes(text) ||
        channel.channel_name_raw.toLowerCase().includes(text)
      );
    });
  }, [channels, query, rawOnly]);
  const groups = useMemo(() => groupChannels(filtered), [filtered]);
  const selectedSet = new Set(selected);
  const atLimit = selected.length >= max;

  const toggle = (name: string) => {
    if (disabled) return;
    if (selectedSet.has(name)) {
      onChange(selected.filter((item) => item !== name));
    } else if (!atLimit) {
      onChange([...selected, name]);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
            aria-hidden="true"
          />
          <label htmlFor="channel-search" className="sr-only">
            Filter channel list
          </label>
          <input
            id="channel-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter channels by canonical or raw name…"
            className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 pl-8 pr-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
          />
        </div>
        <label className="flex items-center gap-1.5 rounded-lg border border-navy-700/70 bg-navy-950/50 px-2.5 py-2 text-[11px] text-ink-300">
          <input
            type="checkbox"
            checked={rawOnly}
            onChange={(event) => setRawOnly(event.target.checked)}
            className="size-3.5 rounded border-navy-500 bg-navy-900 text-cyan-400 focus:ring-cyan-400"
          />
          Raw only
        </label>
        <Badge tone={atLimit ? "amber" : "neutral"}>
          {selected.length} / {max} selected
        </Badge>
      </div>

      {atLimit ? (
        <p className="flex items-center gap-1.5 text-[10px] text-amber-200">
          <AlertTriangle className="size-3" aria-hidden="true" />
          Channel limit reached. Clear a selection before adding another channel.
        </p>
      ) : null}

      {groups.length === 0 ? (
        <p className="rounded-lg border border-navy-700/60 bg-navy-950/40 p-3 text-xs text-ink-400">
          No channel matches the filter text. This only filters the picker list; it does not alter
          returned data.
        </p>
      ) : (
        <div className="max-h-96 space-y-3 overflow-y-auto pr-1" tabIndex={0} aria-label="Channel list">
          {groups.map((group) => (
            <fieldset key={group.key} className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3">
              <legend className="flex flex-wrap items-center gap-2 px-1">
                <span className="font-mono text-[11px] text-cyan-200">{group.unit}</span>
                <Badge tone={group.raw ? "amber" : "neutral"}>
                  {group.raw ? "raw / uncalibrated" : "standard"}
                </Badge>
                <span className="text-[10px] text-ink-500">{group.channels.length} channels</span>
              </legend>
              <ul className="mt-2 grid gap-1.5">
                {group.channels.map((channel) => {
                  const checked = selectedSet.has(channel.channel_name_canonical);
                  const disabledByLimit = !checked && atLimit;
                  return (
                    <li key={channel.channel_name_canonical}>
                      <label
                        className={cn(
                          "flex cursor-pointer items-start gap-2 rounded-lg border p-2 transition-colors",
                          checked
                            ? "border-cyan-400/30 bg-accent-soft"
                            : "border-transparent hover:border-navy-600 hover:bg-navy-900/60",
                          (disabled || disabledByLimit) && "cursor-not-allowed opacity-60",
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled || disabledByLimit}
                          onChange={() => toggle(channel.channel_name_canonical)}
                          className="mt-0.5 size-3.5 rounded border-navy-500 bg-navy-900 text-cyan-400 focus:ring-cyan-400"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block break-all font-mono text-[11px] text-ink-200">
                            {channel.channel_name_canonical}
                          </span>
                          <span className="mt-0.5 block break-all font-mono text-[10px] text-ink-500">
                            {channel.channel_name_raw}
                          </span>
                          <span className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-ink-500">
                            {channel.point_count !== undefined ? (
                              <span>points: {formatNumber(channel.point_count)}</span>
                            ) : null}
                            {channel.missing_count !== undefined ? (
                              <span>missing: {formatNumber(channel.missing_count)}</span>
                            ) : null}
                            {channel.sentinel_count !== undefined ? (
                              <span>sentinels: {formatNumber(channel.sentinel_count)}</span>
                            ) : null}
                            {channel.min !== undefined && channel.min !== null ? (
                              <span>min: {formatNumber(channel.min)}</span>
                            ) : null}
                            {channel.max !== undefined && channel.max !== null ? (
                              <span>max: {formatNumber(channel.max)}</span>
                            ) : null}
                            {channel.constant ? <span className="text-amber-300">constant</span> : null}
                          </span>
                          {channel.quality_flags.length > 0 ? (
                            <span className="mt-1 flex flex-wrap gap-1">
                              {channel.quality_flags.map((flag) => (
                                <span
                                  key={flag}
                                  className="rounded border border-navy-600 bg-navy-800/70 px-1 py-0.5 font-mono text-[9px] text-ink-400"
                                >
                                  {flag}
                                </span>
                              ))}
                            </span>
                          ) : null}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          ))}
        </div>
      )}
    </div>
  );
}
