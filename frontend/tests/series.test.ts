import { describe, expect, it } from "vitest";
import {
  MAX_CHANNELS,
  parseChannelList,
  recommendedChannels,
} from "@/lib/series";
import { seriesChannel } from "./fixtures";

describe("parseChannelList", () => {
  it("trims, removes duplicates, and caps the list", () => {
    const names = Array.from({ length: 12 }, (_, index) => `channel_${index}`);
    const parsed = parseChannelList(` ${names.join(" , ")} ,channel_0`);
    expect(parsed).toHaveLength(MAX_CHANNELS);
    expect(parsed[0]).toBe("channel_0");
    expect(new Set(parsed).size).toBe(MAX_CHANNELS);
  });

  it("returns an empty list for missing or blank input", () => {
    expect(parseChannelList(undefined)).toEqual([]);
    expect(parseChannelList("")).toEqual([]);
    expect(parseChannelList(" , , ")).toEqual([]);
  });
});

describe("recommendedChannels", () => {
  it("selects up to two channels from the first usable unit group", () => {
    const channels = [
      seriesChannel({
        channel_name_canonical: "timestamp",
        unit: "s",
        quality_flags: ["ok"],
      }),
      seriesChannel({
        channel_name_canonical: "constant_temp",
        unit: "degC",
        quality_flags: ["ok"],
        constant: true,
      }),
      seriesChannel({
        channel_name_canonical: "air_temp",
        unit: "degC",
        quality_flags: ["ok"],
      }),
      seriesChannel({
        channel_name_canonical: "air_pressure",
        unit: "degC",
        quality_flags: ["ok"],
      }),
      seriesChannel({
        channel_name_canonical: "air_temp_3",
        unit: "degC",
        quality_flags: ["ok"],
      }),
      seriesChannel({
        channel_name_canonical: "pressure",
        unit: "kPa",
        quality_flags: ["ok"],
      }),
    ];

    expect(recommendedChannels(channels)).toEqual(["air_temp", "air_pressure"]);
  });

  it("does not select uncalibrated or unitless channels when usable channels exist", () => {
    const channels = [
      seriesChannel({
        channel_name_canonical: "raw_signal",
        unit: "V",
        quality_flags: ["uncalibrated"],
      }),
      seriesChannel({
        channel_name_canonical: "unitless",
        unit: "not stated",
        quality_flags: ["ok"],
      }),
      seriesChannel({
        channel_name_canonical: "temperature",
        unit: "degC",
        quality_flags: ["ok"],
      }),
    ];

    expect(recommendedChannels(channels)).toEqual(["temperature"]);
  });
});
