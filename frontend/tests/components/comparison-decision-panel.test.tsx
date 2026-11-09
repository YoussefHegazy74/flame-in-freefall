import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ComparisonDecisionPanel } from "@/components/scientific/comparison-decision-panel";
import { comparisonDecision } from "../fixtures";

describe("ComparisonDecisionPanel", () => {
  it("shows a conditional decision, conditions, and no fabricated chart", () => {
    render(
      <ComparisonDecisionPanel
        decision={comparisonDecision()}
        conditions={{ same_oxygen_basis: false, flame_configuration_documented: false }}
        onConditionChange={() => {}}
        onReevaluate={() => {}}
        isReevaluating={false}
      />,
    );

    expect(screen.getAllByText("Conditionally comparable").length).toBeGreaterThan(0);
    expect(screen.getByText("rule: gas-flame-oxygen")).toBeInTheDocument();
    expect(screen.getByText("same_oxygen_basis")).toBeInTheDocument();
    expect(screen.getByText("flame_configuration_documented")).toBeInTheDocument();
    expect(screen.getByText("Ramped rows remain flagged.")).toBeInTheDocument();
    expect(screen.getByText("No shared comparison chart is rendered.")).toBeInTheDocument();
    expect(
      screen.getByText(/The comparison is not approved in its current state/),
    ).toBeInTheDocument();
  });

  it("reports how many conditions are marked verified", () => {
    render(
      <ComparisonDecisionPanel
        decision={comparisonDecision()}
        conditions={{ same_oxygen_basis: true, flame_configuration_documented: false }}
        onConditionChange={() => {}}
        onReevaluate={() => {}}
        isReevaluating={false}
      />,
    );

    expect(screen.getByText(/1 of 2 conditions marked verified/)).toBeInTheDocument();
  });

  it("passes condition changes and re-evaluation to the parent", async () => {
    const user = userEvent.setup();
    const onConditionChange = vi.fn();
    const onReevaluate = vi.fn();

    render(
      <ComparisonDecisionPanel
        decision={comparisonDecision()}
        conditions={{ same_oxygen_basis: false, flame_configuration_documented: false }}
        onConditionChange={onConditionChange}
        onReevaluate={onReevaluate}
        isReevaluating={false}
      />,
    );

    await user.click(screen.getAllByRole("checkbox")[0]);
    expect(onConditionChange).toHaveBeenCalledWith("same_oxygen_basis", true);

    await user.click(
      screen.getByRole("button", { name: /Re-evaluate with current conditions/i }),
    );
    expect(onReevaluate).toHaveBeenCalledOnce();
  });

  it("does not show a success message for a blocked decision", () => {
    render(
      <ComparisonDecisionPanel
        decision={comparisonDecision({
          status: "blocked",
          required_conditions: [],
          warnings: [],
          scientific_justification: "Unit and value-kind conflict.",
        })}
        conditions={{}}
        onConditionChange={() => {}}
        onReevaluate={() => {}}
        isReevaluating={false}
      />,
    );

    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("No shared comparison chart is rendered.")).toBeInTheDocument();
    expect(screen.queryByText("Comparison approved by the backend.")).not.toBeInTheDocument();
  });
});
