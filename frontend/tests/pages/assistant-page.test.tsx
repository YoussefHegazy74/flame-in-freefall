import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { assistantAnswer, assistantStatus, assistantSuggestion, envelope } from "../fixtures";

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
  useAssistantStatus: vi.fn(),
  useAssistantSuggestions: vi.fn(),
  useAssistantQuery: vi.fn(),
  useCitation: vi.fn(),
}));

vi.mock("@/lib/api/hooks", () => ({
  useAssistantStatus: hooks.useAssistantStatus,
  useAssistantSuggestions: hooks.useAssistantSuggestions,
  useAssistantQuery: hooks.useAssistantQuery,
  useCitation: hooks.useCitation,
}));

import AssistantPage from "@/app/assistant/page";

function mockStatus(overrides = {}) {
  hooks.useAssistantStatus.mockReturnValue({
    data: envelope(assistantStatus(overrides)),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

function mockSuggestions() {
  hooks.useAssistantSuggestions.mockReturnValue({
    data: envelope({
      suggestions: [
        assistantSuggestion(),
        assistantSuggestion({
          question_id: "dq-008",
          category: "experimental_understanding",
          question: "What does the PSI-159 dataset contain?",
          answer_type_hint: "factual",
        }),
      ],
      count: 2,
    }),
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
}

function mockQuery(mutate = vi.fn()) {
  hooks.useAssistantQuery.mockReturnValue({
    mutate,
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  });
  return mutate;
}

describe("AssistantPage", () => {
  beforeEach(() => {
    hooks.useAssistantStatus.mockReset();
    hooks.useAssistantSuggestions.mockReset();
    hooks.useAssistantQuery.mockReset();
    hooks.useCitation.mockReset();
    hooks.useCitation.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isFetching: true,
      error: null,
      refetch: vi.fn(),
    });
    mockStatus();
    mockSuggestions();
    mockQuery();
  });

  it("renders configuration, scientific transparency, suggestions, and an accessible question form", () => {
    render(<AssistantPage />);

    expect(
      screen.getByRole("heading", { name: "Research assistant" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Citation-grounded")).toBeInTheDocument();
    expect(screen.getAllByText("Deterministic").length).toBeGreaterThan(0);
    expect(screen.getByText("Scientific transparency")).toBeInTheDocument();
    expect(screen.getByText("Numbers are tool results")).toBeInTheDocument();
    expect(
      screen.getByText(/Not produced by this assistant: fire-risk scores/),
    ).toBeInTheDocument();
    expect(screen.getByText("Suggested questions")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /How many valid PSI-10 gas-flame records are available\?/,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Your question about the curated NASA PSI data"),
    ).toBeInTheDocument();
    expect(screen.getByText("0 / 1000 characters")).toBeInTheDocument();
    expect(
      screen.getByText(/Conversation context is limited and non-authoritative/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No questions yet" }),
    ).toBeInTheDocument();
  });

  it("submits a typed question and renders the answer with its evidence panel", async () => {
    const user = userEvent.setup();
    const mutate = mockQuery(
      vi.fn((_payload, options) => {
        options?.onSuccess?.(envelope(assistantAnswer()));
      }),
    );
    render(<AssistantPage />);

    const textarea = screen.getByLabelText(
      "Your question about the curated NASA PSI data",
    );
    await user.type(textarea, "What is the average measured peak_burner_temp_c in PSI-159?");
    await user.click(screen.getByRole("button", { name: "Ask assistant" }));

    expect(mutate).toHaveBeenCalledOnce();
    const [payload, options] = mutate.mock.calls[0];
    expect(payload).toMatchObject({
      question: "What is the average measured peak_burner_temp_c in PSI-159?",
      include_retrieval: true,
      conversation_id: expect.stringMatching(/^conv_/),
    });
    expect(options.onSuccess).toBeTypeOf("function");

    expect((await screen.findAllByText("Fully supported")).length).toBeGreaterThan(0);
    expect(screen.getByText("Grounded answer")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Evidence panel" })).toBeInTheDocument();
    expect(screen.getAllByText("Citations").length).toBeGreaterThan(0);
    expect(screen.getByText("Supporting data")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "No questions yet" })).not.toBeInTheDocument();
  });

  it("submits a suggested question and opens the shared citation drawer", async () => {
    const user = userEvent.setup();
    mockQuery(
      vi.fn((_payload, options) => {
        options?.onSuccess?.(envelope(assistantAnswer()));
      }),
    );
    render(<AssistantPage />);

    await user.click(
      screen.getByRole("button", {
        name: /How many valid PSI-10 gas-flame records are available\?/,
      }),
    );

    expect((await screen.findAllByText("Fully supported")).length).toBeGreaterThan(0);
    const citationButtons = screen.getAllByRole("button", {
      name: /Open citation record for PSI-159_Experimental table_CFI-G_Normal Flames\.csv/,
    });
    await user.click(citationButtons[0]);

    expect(hooks.useCitation).toHaveBeenCalledWith("cit_f_21df4ec92db1eca0", true);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Citation record")).toBeInTheDocument();
  });

  it("reports provider fallback without pretending the provider answered", () => {
    mockStatus({
      mode: "fallback",
      provider: "deterministic",
      fallback_mode: true,
      fallback_reason: "provider configuration is incomplete; deterministic mode is active",
    });
    render(<AssistantPage />);

    expect(
      screen.getByText("Deterministic fallback is active"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "provider configuration is incomplete; deterministic mode is active",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Deterministic fallback").length).toBeGreaterThan(0);
  });

  it("disables question submission when the assistant is disabled", () => {
    mockStatus({
      enabled: false,
      notes: ["Assistant query handling is disabled by configuration."],
    });
    render(<AssistantPage />);

    expect(
      screen.getByText("The assistant is disabled on this deployment"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Your question about the curated NASA PSI data"),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Ask assistant" })).toBeDisabled();
    expect(
      screen.getByText(/Question submission is disabled while the assistant is disabled/),
    ).toBeInTheDocument();
  });

  it("keeps the page usable when suggestions fail", () => {
    hooks.useAssistantSuggestions.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      error: new Error("suggestions unavailable"),
      refetch: vi.fn(),
    });
    render(<AssistantPage />);

    expect(screen.getByText("Suggested questions are unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/You can still type a question/),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Your question about the curated NASA PSI data"),
    ).toBeEnabled();
  });

  it("shows a retry state for a failed question", async () => {
    const user = userEvent.setup();
    const mutate = mockQuery(
      vi.fn((_payload, options) => {
        options?.onError?.(
          new ApiError({
            kind: "network",
            message: "backend unavailable",
            code: "network_error",
          }),
        );
      }),
    );
    render(<AssistantPage />);

    await user.type(
      screen.getByLabelText("Your question about the curated NASA PSI data"),
      "What is in PSI-159?",
    );
    await user.click(screen.getByRole("button", { name: "Ask assistant" }));

    expect(
      await screen.findByText("The assistant could not complete this question"),
    ).toBeInTheDocument();
    expect(screen.getByText("backend unavailable")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry request" }));
    await waitFor(() => expect(mutate).toHaveBeenCalledTimes(2));
  });
});
