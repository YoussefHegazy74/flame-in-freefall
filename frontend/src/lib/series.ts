import type { SeriesChannel } from "@/lib/api/types";

export const MAX_CHANNELS = 8;

export function parseChannelList(value: string | null | undefined): string[] {
  if (!value) return [];
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ).slice(0, MAX_CHANNELS);
}

/**
 * Choose a small, defensible default: up to two channels from the first unit
 * group that has a stated unit and an `ok` flag. No conversion or ranking of
 * physical importance is implied.
 */
export function recommendedChannels(channels: SeriesChannel[], max = 2): string[] {
  const usable = channels.filter(
    (channel) =>
      !channel.constant &&
      channel.unit !== "not stated" &&
      channel.quality_flags.includes("ok") &&
      !channel.channel_name_canonical.includes("timestamp"),
  );
  const groups = new Map<string, SeriesChannel[]>();
  for (const channel of usable) {
    const list = groups.get(channel.unit) ?? [];
    list.push(channel);
    groups.set(channel.unit, list);
  }
  const firstGroup = Array.from(groups.values()).find((group) => group.length > 0);
  if (firstGroup) {
    return firstGroup.slice(0, max).map((channel) => channel.channel_name_canonical);
  }
  return channels
    .filter((channel) => !channel.constant)
    .slice(0, max)
    .map((channel) => channel.channel_name_canonical);
}

export function channelLabel(channel: SeriesChannel): string {
  return channel.channel_name_canonical;
}

export function isRawChannel(channel: SeriesChannel): boolean {
  return channel.quality_flags.includes("uncalibrated");
}
