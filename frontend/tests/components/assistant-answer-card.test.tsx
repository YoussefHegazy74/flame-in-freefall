import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AssistantAnswerCard } from "@/components/assistant/answer-card";
import { assistantAnswer, envelope } from "../fixtures";

function renderAnswer(overrides = {}, onOpenCitation = vi.fn()) {
  render(
    <AssistantAnswerCard
      envelope={envelope(assistantAnswer(overrides))}
      onOpenCitation={onOpenCitation}
    />,
  );
  return { onOpenCitation };
}

describe("AssistantAnswerCard", () => {
  it("shows evidence status, exact tool values, limitations, tools, and validation", () => {
    renderAnswer();

    expect(screen.getAllByText("Fully supported").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Numerical").length).toBeGreaterThan(0);
    expect(screen.getByText("high confidence")).toBeInTheDocument();
    expect(screen.getByText("validated")).toBeInTheDocument();
    expect(
      screen.getAllByText(/210\.40181331133797/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("peak_burner_temp_c summary")).toBeInTheDocument();
    expect(screen.getAllByText("Measured").length).toBeGreaterThan(0);
    expect(screen.getAllByText("°C").length).toBeGreaterThan(0);
    expect(screen.getByText("missing_not_zero")).toBeInTheDocument();
    expect(
      screen.getByText("49 peak_burner_temp_c values are missing and are not zero."),
    ).toBeInTheDocument();
    expect(screen.getByText("dataset_field_statistics")).toBeInTheDocument();
    expect(screen.getByText("1.23 ms")).toBeInTheDocument();
    expect(screen.getByText("2 validation checks")).toBeInTheDocument();
    expect(screen.getByText("untrusted")).toBeInTheDocument();
  });

  it("opens a citation through the shared citation drawer callback", async () => {
    const user = userEvent.setup();
    const { onOpenCitation } = renderAnswer();

    const citationButtons = screen.getAllByRole("button", {
      name: /Open citation record for PSI-159_Experimental table_CFI-G_Normal Flames\.csv/,
    });
    expect(citationButtons.length).toBeGreaterThan(0);
    await user.click(citationButtons[0]);
    expect(onOpenCitation).toHaveBeenCalledWith("cit_f_21df4ec92db1eca0");
  });

  it("shows fallback and validation failure as explicit states", () => {
    renderAnswer({
      fallback_mode: true,
      fallback_reason: "provider request timed out; the deterministic answer is shown",
      validation: {
        passed: false,
        citation_validation_passed: false,
        claim_validation_passed: false,
        checks: [],
        errors: ["claim validation failed"],
        warnings: [],
      },
      answer:
        "The application withheld the draft because validation failed. No unverified claim was released.",
      evidence_status: "insufficient_evidence",
      confidence: "low",
      supporting_data: [],
      claims: [],
      limitations: [],
    });

    expect(screen.getByText("Deterministic fallback is active")).toBeInTheDocument();
    expect(
      screen.getByText(/provider request timed out; the deterministic answer is shown/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Validation failed; the draft was withheld"),
    ).toBeInTheDocument();
    expect(screen.getByText("claim validation failed")).toBeInTheDocument();
    expect(screen.getByText("validation failed")).toBeInTheDocument();
    expect(screen.getAllByText("Insufficient evidence").length).toBeGreaterThan(0);
  });

  it("renders clarification options as follow-up actions", async () => {
    const user = userEvent.setup();
    const onFollowUp = vi.fn();
    render(
      <AssistantAnswerCard
        envelope={envelope(
          assistantAnswer({
            answer_type: "clarification_required",
            answer: "Which investigation or dataset does the question refer to?",
            evidence_status: "insufficient_evidence",
            confidence: "low",
            citations: [],
            supporting_data: [],
            claims: [],
            limitations: [],
            validation: {
              passed: true,
              citation_validation_passed: true,
              claim_validation_passed: true,
              checks: [],
              errors: [],
              warnings: [],
            },
            clarification: {
              question: "Which dataset should I use?",
              options: ["PSI-10", "PSI-159"],
              missing: ["dataset"],
            },
          }),
        )}
        onOpenCitation={vi.fn()}
        onFollowUp={onFollowUp}
      />,
    );

    const options = screen.getByText("Which dataset should I use?").closest("div");
    expect(options).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "PSI-10" }));
    expect(onFollowUp).toHaveBeenCalledWith("PSI-10");
    expect(within(options as HTMLElement).getByText(/Missing: dataset/)).toBeInTheDocument();
  });
});
