import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { datasetQuality, envelope, limitation } from "../fixtures";

const nav = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
  pathname: "/quality",
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
  useDatasetsQuality: vi.fn(),
  useDatasetLimitations: vi.fn(),
}));

vi.mock("@/lib/api/hooks", () => ({
  useDatasetsQuality: hooks.useDatasetsQuality,
  useDatasetLimitations: hooks.useDatasetLimitations,
}));

import QualityPage from "@/app/quality/page";

const sharedIssue = {
  severity: "warning" as const,
  code: "unit_ambiguity",
  message: "Burning rate is preserved as labeled and not converted.",
  details: { column: "burning_rate_mm_as_labeled", count: 258 },
};

const psi10 = datasetQuality({
  dataset_id: "psi-10-gas-flame",
  accession: "PSI-10",
  display_name: "PSI-10 gas-flame tests",
  issues: [
    sharedIssue,
    {
      severity: "error",
      code: "missing_final_state",
      message: "Some gas-flame tests have a missing final state.",
    },
  ],
});

const psi26 = datasetQuality({
  dataset_id: "psi-26-material",
  accession: "PSI-26",
  display_name: "PSI-26 material tests",
  quality_status: "partial",
  issues: [sharedIssue],
});

function mockQuality() {
  hooks.useDatasetsQuality.mockReturnValue({
    data: envelope([psi10, psi26], {
      quality: {
        status: "partial",
        flags: ["unit_ambiguity", "missing_final_state"],
        warnings: ["Registry-wide warnings remain in force."],
      },
    }),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

function mockLimitations() {
  hooks.useDatasetLimitations.mockReturnValue({
    data: envelope({
      dataset_id: "psi-10-gas-flame",
      accession: "PSI-10",
      display_name: "PSI-10 gas-flame tests",
      limitations: [limitation()],
      summary: {
        total: 1,
        by_scope: { dataset: 1 },
        by_severity: { warning: 1 },
        by_status: { open: 1 },
      },
      page: { limit: 200, offset: 0, total: 1, has_more: false },
    }),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

describe("QualityPage", () => {
  beforeEach(() => {
    nav.params = new URLSearchParams();
    nav.replace.mockReset();
    mockQuality();
    mockLimitations();
  });

  it("renders the registry-wide warning, quality flags, and per-dataset states", () => {
    render(<QualityPage />);

    expect(screen.getByRole("heading", { name: "Quality center" })).toBeInTheDocument();
    expect(screen.getByText("Registry-wide warnings remain in force.")).toBeInTheDocument();
    expect(screen.getAllByText("unit_ambiguity").length).toBeGreaterThan(0);
    expect(screen.getAllByText("missing_final_state").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PSI-10 gas-flame tests").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PSI-26 material tests").length).toBeGreaterThan(0);
    expect(screen.getByText(/The report summary is registry-wide, not per dataset./)).toBeInTheDocument();
  });

  it("deduplicates repeated issues and labels every dataset that reports them", () => {
    render(<QualityPage />);

    expect(screen.getByText("reported by 2 datasets")).toBeInTheDocument();
    expect(screen.getByText("reported by 1 dataset")).toBeInTheDocument();
    expect(
      screen.getByText("Burning rate is preserved as labeled and not converted."),
    ).toBeInTheDocument();
  });

  it("preserves the un-collapsed issue list for a focused dataset", () => {
    nav.params = new URLSearchParams("dataset=psi-10-gas-flame");
    render(<QualityPage />);

    expect(
      screen.getByRole("heading", { name: /Focused dataset quality: PSI-10 gas-flame tests/ }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Some gas-flame tests have a missing final state.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(/This is the un-collapsed issue list returned for this dataset/),
    ).toBeInTheDocument();
  });

  it("synchronizes the issue search with the URL", async () => {
    const user = userEvent.setup();
    render(<QualityPage />);

    await user.type(
      screen.getByRole("searchbox", { name: /Search issue code, message, or dataset/i }),
      "oxygen",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(nav.replace).toHaveBeenCalledWith("/quality?q=oxygen", { scroll: false });
  });
});
