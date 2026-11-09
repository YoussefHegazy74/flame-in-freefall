import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  comparisonDecision,
  comparisonMeasurement,
  envelope,
} from "../fixtures";

const nav = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
  pathname: "/compare",
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
  useMeasurements: vi.fn(),
  useComparability: vi.fn(),
  useComparison: vi.fn(),
}));

vi.mock("@/lib/api/hooks", () => ({
  useMeasurements: hooks.useMeasurements,
  useComparability: hooks.useComparability,
  useComparison: hooks.useComparison,
}));

import ComparePage from "@/app/compare/page";

const left = comparisonMeasurement();
const right = comparisonMeasurement({
  measurement_id: "psi-159-gas-flame.oxygen_mole_fraction",
  dataset_id: "psi-159-gas-flame",
  accession: "PSI-159",
});

const summary = {
  registry_version: "1.0.0",
  dataset_version: "dataset-version-test",
  default_policy: {
    status: "not_comparable" as const,
    justification: "No explicit rule means no approved comparison.",
    engine_behavior: "Return not_comparable and never infer a comparison.",
  },
  state_definitions: {
    comparable: { definition: "All conditions verified.", engine_behavior: "Return comparable." },
    conditionally_comparable: {
      definition: "A rule exists with unverified conditions.",
      engine_behavior: "Return conditionally_comparable.",
    },
    not_comparable: {
      definition: "No approved basis.",
      engine_behavior: "Return not_comparable.",
    },
    blocked: { definition: "A hard conflict exists.", engine_behavior: "Return blocked." },
    insufficient_metadata: {
      definition: "Metadata cannot decide.",
      engine_behavior: "Return insufficient_metadata.",
    },
  },
  measurement_status_counts: {
    comparable: 0,
    conditionally_comparable: 10,
    not_comparable: 49,
    blocked: 20,
    insufficient_metadata: 14,
  },
  rule_status_counts: {
    conditionally_comparable: 2,
    not_comparable: 58,
  },
  measurement_count: 93,
  rule_count: 60,
  concepts: [],
  measurements: [left, right],
  rules: [
    {
      rule_id: "gas-flame-oxygen",
      left_measurement_id: left.measurement_id,
      right_measurement_id: right.measurement_id,
      status: "conditionally_comparable" as const,
      required_conditions: [
        { key: "same_oxygen_basis", description: "Same oxygen basis." },
      ],
      policies: {},
      scientific_justification: "Both datasets report oxygen mole fraction.",
      notes: "",
      source_references: [],
    },
    {
      rule_id: "bass25-26-flow-restrictor",
      left_measurement_id: "psi-25-material.flow_restrictor",
      right_measurement_id: "psi-26-material.flow_restrictor",
      status: "conditionally_comparable" as const,
      required_conditions: [],
      policies: {},
      scientific_justification: "Requires normalized flow-restrictor codes.",
      notes: "",
      source_references: [],
    },
  ],
};

function mockHooks(decision = comparisonDecision()) {
  hooks.useMeasurements.mockReturnValue({
    data: envelope([left, right]),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
  hooks.useComparability.mockReturnValue({
    data: envelope(summary),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
  hooks.useComparison.mockReturnValue({
    data: envelope(decision),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

describe("ComparePage", () => {
  beforeEach(() => {
    nav.params = new URLSearchParams(
      `left=${encodeURIComponent(left.measurement_id)}&right=${encodeURIComponent(right.measurement_id)}`,
    );
    nav.replace.mockReset();
    hooks.useComparison.mockReset();
    mockHooks();
  });

  it("renders the backend decision, conditions, warnings, and no fabricated chart", () => {
    render(<ComparePage />);

    expect(
      screen.getByRole("heading", { name: "Backend-approved measurement comparisons" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Conditionally comparable").length).toBeGreaterThan(0);
    expect(screen.getAllByText("same_oxygen_basis").length).toBeGreaterThan(0);
    expect(screen.getByText("Ramped rows remain flagged.")).toBeInTheDocument();
    expect(screen.getByText("No shared comparison chart is rendered.")).toBeInTheDocument();
    expect(screen.getByText(/60 explicit rules/)).toBeInTheDocument();
  });

  it("sends changed conditions to the backend only when re-evaluation is requested", async () => {
    const user = userEvent.setup();
    render(<ComparePage />);

    await user.click(screen.getByRole("checkbox", { name: /same_oxygen_basis/i }));

    expect(screen.getByText(/1 of 2 conditions marked verified/)).toBeInTheDocument();
    expect(screen.getByText("Conditions changed but not applied")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: /Re-evaluate with current conditions/i }),
    );

    expect(nav.replace).toHaveBeenCalledOnce();
    const url = new URL(nav.replace.mock.calls[0][0] as string, "http://localhost");
    expect(url.searchParams.get("left")).toBe(left.measurement_id);
    expect(url.searchParams.get("right")).toBe(right.measurement_id);
    expect(url.searchParams.get("cond_same_oxygen_basis")).toBe("true");
    expect(url.searchParams.get("cond_flame_configuration_documented")).toBe("false");
  });

  it("refuses to request a comparison when the same measurement is selected twice", () => {
    nav.params = new URLSearchParams(
      `left=${encodeURIComponent(left.measurement_id)}&right=${encodeURIComponent(left.measurement_id)}`,
    );
    render(<ComparePage />);

    expect(
      screen.getByText(/The same measurement is selected on both sides/),
    ).toBeInTheDocument();
    expect(hooks.useComparison).not.toHaveBeenCalled();
    expect(screen.queryByText("No shared comparison chart is rendered.")).not.toBeInTheDocument();
  });

  it("renders insufficient metadata without offering a condition override", () => {
    mockHooks(
      comparisonDecision({
        status: "insufficient_metadata",
        required_conditions: [],
        warnings: [],
        reasons: [
          {
            code: "insufficient_metadata",
            message: "The available metadata cannot decide the comparison.",
          },
        ],
        scientific_justification: "The available metadata cannot decide the comparison.",
      }),
    );
    render(<ComparePage />);

    expect(screen.getAllByText("Insufficient metadata").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("The available metadata cannot decide the comparison.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: /Re-evaluate with current conditions/i }),
    ).not.toBeInTheDocument();
  });

  it("filters the documented-rule browser from the URL without changing the decision", () => {
    nav.params = new URLSearchParams(
      `left=${encodeURIComponent(left.measurement_id)}&right=${encodeURIComponent(right.measurement_id)}&rule_q=oxygen`,
    );
    render(<ComparePage />);

    expect(screen.getByText("gas-flame-oxygen")).toBeInTheDocument();
    expect(screen.queryByText("bass25-26-flow-restrictor")).not.toBeInTheDocument();
    expect(screen.getByText(/This filter browses the full rule list returned by the API/)).toBeInTheDocument();
  });
});
