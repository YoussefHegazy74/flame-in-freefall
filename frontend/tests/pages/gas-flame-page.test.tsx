import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { envelope, gasFlameRow } from "../fixtures";

const nav = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
  pathname: "/experiments/gas-flame",
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => nav.params,
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => nav.pathname,
}));

vi.mock("next/link", async () => {
  const React = await import("react");
  return {
    default: ({
      href,
      children,
      ...props
    }: {
      href: string | { pathname?: string };
      children: React.ReactNode;
    }) =>
      React.createElement(
        "a",
        { href: typeof href === "string" ? href : href.pathname ?? "#", ...props },
        children,
      ),
  };
});

const hooks = vi.hoisted(() => ({
  useGasFlameTests: vi.fn(),
  useGasFlameFacets: vi.fn(),
  useCitation: vi.fn(),
}));

vi.mock("@/lib/api/hooks", () => ({
  useGasFlameTests: hooks.useGasFlameTests,
  useGasFlameFacets: hooks.useGasFlameFacets,
  useCitation: hooks.useCitation,
}));

import GasFlamePage from "@/app/experiments/gas-flame/page";

function mockRows() {
  hooks.useGasFlameTests.mockReturnValue({
    data: envelope([gasFlameRow()], {
      meta: {
        request_id: "req_test",
        generated_at: "2026-11-09T00:00:00Z",
        page: {
          limit: 25,
          offset: 0,
          total: 1,
          has_more: false,
          excluded_qualified_rows: 20,
        },
      },
    }),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

function mockFacets() {
  hooks.useGasFlameFacets.mockReturnValue({
    data: envelope({
      accessions: [
        { accession: "PSI-10", total_rows: 327, included_rows: 256, excluded_qualified_rows: 71 },
        { accession: "PSI-159", total_rows: 333, included_rows: 333, excluded_qualified_rows: 0 },
      ],
      flame_type: [
        { value: "Normal", count: 326, by_accession: { "PSI-10": 147, "PSI-159": 179 } },
        { value: "Inverse", count: 173, by_accession: { "PSI-10": 109, "PSI-159": 64 } },
      ],
      fuel: [
        { value: "C2H4", count: 127, by_accession: { "PSI-10": 127 } },
        { value: "ethane", count: 67, by_accession: { "PSI-159": 67 } },
      ],
      hot_ignition: [{ value: "Yes", count: 300, by_accession: { "PSI-10": 100, "PSI-159": 200 } }],
      extinction_mode: [{ value: "SE", count: 100, by_accession: { "PSI-10": 100 } }],
      tfp: [{ value: "No", count: 100, by_accession: { "PSI-10": 100 } }],
      pressure: {
        by_accession: [
          {
            accession: "PSI-10",
            field: "pressure_initial_atm",
            unit: "atm",
            count: 327,
            missing_count: 0,
            min: 0.5,
            max: 3,
            histogram: [{ min: 0.5, max: 1, count: 100 }],
          },
          {
            accession: "PSI-159",
            field: "pressure_approx_bar",
            unit: "bar",
            count: 333,
            missing_count: 0,
            min: 1,
            max: 5,
            histogram: [],
          },
        ],
        note: "Pressure units remain accession-specific.",
      },
      oxygen: {
        field: "oxygen_mole_fraction",
        unit: "mole fraction",
        by_accession: [
          {
            accession: "PSI-10",
            field: "oxygen_mole_fraction",
            unit: "mole fraction",
            count: 327,
            missing_count: 0,
            min: 0.1,
            max: 0.3,
            histogram: [],
          },
        ],
        note: "Oxygen values are mole fractions.",
      },
      oxygen_initial: { by_accession: [], note: "No initial oxygen values." },
      include_qualified: false,
      excluded_qualified_rows: 71,
      notes: ["Qualified rows are excluded by default."],
    }),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

describe("GasFlamePage", () => {
  beforeEach(() => {
    nav.params = new URLSearchParams();
    nav.replace.mockReset();
    hooks.useGasFlameTests.mockReset();
    hooks.useGasFlameFacets.mockReset();
    hooks.useCitation.mockReset();
    hooks.useCitation.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    mockRows();
    mockFacets();
  });

  it("disables pressure filters until an accession fixes the unit", () => {
    render(<GasFlamePage />);

    expect(screen.getByLabelText(/Pressure ≥/)).toBeDisabled();
    expect(screen.getByLabelText(/Pressure ≤/)).toBeDisabled();
    expect(screen.getByText(/Mixed pressure units: choose an accession/)).toBeInTheDocument();
  });

  it("enables pressure filters with the accession unit and clears them when the accession changes", async () => {
    const user = userEvent.setup();
    render(<GasFlamePage />);

    await user.selectOptions(screen.getByLabelText("Accession"), "PSI-10");
    const pressureMin = screen.getByLabelText(/Pressure ≥ \(atm\)/);
    expect(pressureMin).toBeEnabled();

    await user.type(pressureMin, "1.2");
    expect(pressureMin).toHaveValue(1.2);

    await user.selectOptions(screen.getByLabelText("Accession"), "PSI-159");
    expect(screen.getByLabelText(/Pressure ≥ \(bar\)/)).toHaveValue(null);
  });

  it("applies an accession-bound pressure filter to the URL", async () => {
    const user = userEvent.setup();
    render(<GasFlamePage />);

    await user.selectOptions(screen.getByLabelText("Accession"), "PSI-10");
    await user.type(screen.getByLabelText(/Pressure ≥ \(atm\)/), "1.2");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    expect(nav.replace).toHaveBeenCalledOnce();
    const url = new URL(nav.replace.mock.calls[0][0] as string, "http://localhost");
    expect(url.pathname).toBe("/experiments/gas-flame");
    expect(url.searchParams.get("accession")).toBe("PSI-10");
    expect(url.searchParams.get("pressure_min")).toBe("1.2");
  });

  it("renders rows with computed fields and missing values preserved", () => {
    render(<GasFlamePage />);

    expect(screen.getByText("T-01")).toBeInTheDocument();
    expect(screen.getByText(/20 qualified rows excluded/)).toBeInTheDocument();
    expect(screen.getAllByText("Computed").length).toBeGreaterThan(0);
    expect(screen.getByText("2,200")).toBeInTheDocument();
  });

  it("renders facet coverage from the API with accession-specific pressure units", () => {
    render(<GasFlamePage />);

    expect(
      screen.getByRole("heading", { name: "Facet coverage from the API" }),
    ).toBeInTheDocument();
    expect(screen.getByText("PSI-10: 147 · PSI-159: 179")).toBeInTheDocument();
    expect(screen.getAllByText(/pressure_initial_atm/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/pressure_approx_bar/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Qualified rows are excluded by default/)).toBeInTheDocument();
    expect(hooks.useGasFlameFacets).toHaveBeenCalled();
  });
});
