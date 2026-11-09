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
}));

vi.mock("@/lib/api/hooks", () => ({
  useGasFlameTests: hooks.useGasFlameTests,
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

describe("GasFlamePage", () => {
  beforeEach(() => {
    nav.params = new URLSearchParams();
    nav.replace.mockReset();
    hooks.useGasFlameTests.mockReset();
    mockRows();
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
});
