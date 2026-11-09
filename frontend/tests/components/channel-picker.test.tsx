import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChannelPicker } from "@/components/scientific/channel-picker";
import { seriesChannel } from "../fixtures";

const channels = [
  seriesChannel({
    channel_name_raw: "PCM_AIR_TEMP",
    channel_name_canonical: "pcm_air_temp_c",
    unit: "degC",
    quality_flags: ["ok"],
  }),
  seriesChannel({
    channel_name_raw: "PCM_PRESSURE",
    channel_name_canonical: "pcm_pressure_kpa",
    unit: "degC",
    quality_flags: ["ok"],
  }),
  seriesChannel({
    channel_name_raw: "DUSTTRAK_V",
    channel_name_canonical: "dusttrak_voltage",
    unit: "V",
    quality_flags: ["uncalibrated"],
  }),
];

describe("ChannelPicker", () => {
  it("groups channels by unit and raw/calibrated status", () => {
    render(<ChannelPicker channels={channels} selected={[]} onChange={() => {}} />);

    expect(screen.getByText("degC")).toBeInTheDocument();
    expect(screen.getByText("V")).toBeInTheDocument();
    expect(screen.getByText("standard")).toBeInTheDocument();
    expect(screen.getByText("raw / uncalibrated")).toBeInTheDocument();
    expect(screen.getByText("0 / 8 selected")).toBeInTheDocument();
  });

  it("adds and removes a channel without converting or renaming it", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<ChannelPicker channels={channels} selected={[]} onChange={onChange} />);

    await user.click(screen.getByRole("checkbox", { name: /pcm_air_temp_c/i }));
    expect(onChange).toHaveBeenCalledWith(["pcm_air_temp_c"]);
  });

  it("filters to raw channels without changing the channel identity", async () => {
    const user = userEvent.setup();

    render(<ChannelPicker channels={channels} selected={[]} onChange={() => {}} />);

    await user.click(screen.getByRole("checkbox", { name: "Raw only" }));
    expect(screen.getByText("dusttrak_voltage")).toBeInTheDocument();
    expect(screen.queryByText("pcm_air_temp_c")).not.toBeInTheDocument();
  });

  it("blocks adding more than the maximum number of channels", () => {
    render(
      <ChannelPicker
        channels={channels}
        selected={["a", "b"]}
        onChange={() => {}}
        max={2}
      />,
    );

    expect(screen.getByText("2 / 2 selected")).toBeInTheDocument();
    expect(
      screen.getByText(/Channel limit reached. Clear a selection before adding another channel./),
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /pcm_air_temp_c/i })).toBeDisabled();
  });
});
