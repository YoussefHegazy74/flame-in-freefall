import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QualityBanner, WarningList } from "@/components/scientific/quality-banner";
import { responseQuality } from "../fixtures";

describe("QualityBanner", () => {
  it("renders every quality flag and warning returned by the API", () => {
    render(<QualityBanner quality={responseQuality} title="Telemetry quality" />);

    expect(screen.getByLabelText("Telemetry quality")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
    expect(screen.getByText("use_available_with_warnings")).toBeInTheDocument();
    expect(screen.getByText("uncalibrated_channels")).toBeInTheDocument();
    expect(
      screen.getByText("Some channels are uncalibrated and remain labeled raw."),
    ).toBeInTheDocument();
  });

  it("does not claim the data are clean when no warnings are returned", () => {
    render(
      <QualityBanner
        quality={{ status: "verified", flags: [], warnings: [] }}
      />,
    );

    expect(
      screen.getByText(/No response-level warnings. Dataset and measurement restrictions still apply./),
    ).toBeInTheDocument();
  });
});

describe("WarningList", () => {
  it("renders an explicit empty state", () => {
    render(<WarningList warnings={[]} emptyLabel="No lookup warnings." />);
    expect(screen.getByText("No lookup warnings.")).toBeInTheDocument();
  });
});
