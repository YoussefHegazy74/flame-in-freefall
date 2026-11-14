"use client";

import { useState, type FormEvent } from "react";
import {
  Bot,
  CircleHelp,
  Info,
  MessageSquareText,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useAssistantQuery, useAssistantStatus, useAssistantSuggestions } from "@/lib/api/hooks";
import type {
  AssistantAnswer,
  AssistantSuggestion,
  Envelope,
} from "@/lib/api/types";
import {
  ANSWER_TYPE_LABELS,
  assistantModeLabel,
  humanizeIdentifier,
} from "@/lib/assistant";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, InlineAlert, LoadingState } from "@/components/ui/states";
import { AssistantAnswerCard } from "@/components/assistant/answer-card";
import { CitationDrawer } from "@/components/scientific/citation-drawer";

interface ConversationTurn {
  id: string;
  question: string;
  status: "pending" | "complete" | "error";
  envelope?: Envelope<AssistantAnswer>;
  error?: unknown;
}

function newId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function SuggestionButton({
  suggestion,
  onSelect,
  disabled,
}: {
  suggestion: AssistantSuggestion;
  onSelect: (question: string) => void;
  disabled: boolean;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(suggestion.question)}
        disabled={disabled}
        className="group h-full w-full rounded-xl border border-navy-700/70 bg-navy-900/50 p-3 text-left transition-colors hover:border-cyan-400/30 hover:bg-navy-800/60 focus-ring disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="flex flex-wrap items-center gap-1.5">
          <Badge tone="cyan">{humanizeIdentifier(suggestion.category)}</Badge>
          <Badge tone="outline">
            {ANSWER_TYPE_LABELS[suggestion.answer_type_hint]}
          </Badge>
        </span>
        <span className="mt-2 block text-xs leading-relaxed text-ink-200 group-hover:text-ink-50">
          {suggestion.question}
        </span>
      </button>
    </li>
  );
}

export default function AssistantPage() {
  const status = useAssistantStatus();
  const suggestions = useAssistantSuggestions();
  const ask = useAssistantQuery();
  const [conversationId] = useState(() => newId("conv"));
  const [draft, setDraft] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [citationId, setCitationId] = useState<string | null>(null);

  const assistantDisabled = status.data?.data.enabled === false;
  const pending = ask.isPending || turns.some((turn) => turn.status === "pending");

  const submitQuestion = (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question) {
      setFormError("Enter a question before asking the assistant.");
      return;
    }
    if (question.length > 1000) {
      setFormError("Questions are limited to 1,000 characters.");
      return;
    }
    if (pending) {
      return;
    }
    setFormError(null);
    const turnId = newId("turn");
    setTurns((current) => [
      ...current,
      { id: turnId, question, status: "pending" },
    ]);
    setDraft("");
    ask.mutate(
      {
        question,
        conversation_id: conversationId,
        include_retrieval: true,
      },
      {
        onSuccess: (envelope) => {
          setTurns((current) =>
            current.map((turn) =>
              turn.id === turnId
                ? { ...turn, status: "complete", envelope }
                : turn,
            ),
          );
        },
        onError: (error) => {
          setTurns((current) =>
            current.map((turn) =>
              turn.id === turnId ? { ...turn, status: "error", error } : turn,
            ),
          );
        },
      },
    );
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuestion(draft);
  };

  const statusData = status.data?.data;
  const toolCount = statusData?.tools_available.length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="FLAREX · Grounded research assistant"
        title="Research assistant"
        description={
          <>
            Ask about the curated NASA PSI combustion data. Numerical values come
            from deterministic backend tools, and every released citation resolves
            through the verified citation registry. The assistant is not a source of
            truth and does not replace the explorers.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">
              <Sparkles className="size-3" aria-hidden="true" />
              Citation-grounded
            </Badge>
            <Badge tone="neutral">
              Contract {statusData?.contract_version ?? "1.0.0"}
            </Badge>
            {statusData ? (
              <Badge tone={statusData.fallback_mode ? "amber" : "emerald"}>
                {assistantModeLabel(statusData.mode, statusData.enabled)}
              </Badge>
            ) : (
              <Badge tone="outline">Checking assistant configuration</Badge>
            )}
            {statusData?.retrieval_enabled ? (
              <Badge tone="violet">Verified-document retrieval</Badge>
            ) : null}
          </>
        }
      />

      {status.isError ? (
        <InlineAlert tone="warning" title="Assistant status could not be loaded">
          <p>
            You can still ask a question. The backend remains authoritative and
            will return a safe deterministic response or an explicit error. No
            capability is assumed from this page.
          </p>
          <button
            type="button"
            onClick={() => status.refetch()}
            className={buttonStyles({ size: "sm", className: "mt-2" })}
          >
            Retry status
          </button>
        </InlineAlert>
      ) : null}

      {assistantDisabled ? (
        <InlineAlert tone="warning" title="The assistant is disabled on this deployment">
          <p>
            No question will be sent to a model and no tool will run. The catalog,
            datasets, and experiment explorers remain available without the
            assistant.
          </p>
        </InlineAlert>
      ) : null}

      {statusData?.fallback_mode ? (
        <InlineAlert tone="warning" title="Deterministic fallback is active">
          <p>
            {statusData.fallback_reason ??
              "The optional provider is unavailable. Answers still use the deterministic planner, tools, and validation."}
          </p>
        </InlineAlert>
      ) : null}

      {statusData?.mode === "provider" ? (
        <InlineAlert tone="info" title="A provider may rephrase validated drafts only">
          <p>
            The provider cannot choose tools, generate SQL, create citations, or add
            numbers. Every answer is still composed and validated deterministically
            before the provider sees it.
          </p>
        </InlineAlert>
      ) : null}

      <section className="surface p-5" aria-labelledby="assistant-scientific-transparency">
        <h2
          id="assistant-scientific-transparency"
          className="flex items-center gap-2 text-sm font-semibold text-ink-100"
        >
          <ShieldCheck className="size-4 text-emerald-300" aria-hidden="true" />
          Scientific transparency
        </h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <div className="surface-inset p-3">
            <p className="text-xs font-medium text-ink-100">Numbers are tool results</p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Counts, averages, ranges, filters, telemetry values, and comparison
              decisions come from allowlisted deterministic tools. A language model
              never invents a numerical value.
            </p>
          </div>
          <div className="surface-inset p-3">
            <p className="text-xs font-medium text-ink-100">Evidence keeps its labels</p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Measured, computed, derived, raw, and categorical values stay
              distinct. Missing values are never zero, and ambiguous units are never
              converted without an approved rule.
            </p>
          </div>
          <div className="surface-inset p-3">
            <p className="text-xs font-medium text-ink-100">Retrieved text is not instruction</p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Verified documentation is quoted as untrusted evidence. It cannot
              select tools, alter the system prompt, or create a citation. Paired
              values appear only when the alignment registry confirms them.
            </p>
          </div>
        </div>
        <p className="mt-3 rounded-lg border border-amber-400/20 bg-warning-soft p-2.5 text-[11px] leading-relaxed text-amber-100">
          Not produced by this assistant: fire-risk scores, material rankings,
          spacecraft fire-safety guarantees, causal claims from correlation, or
          fabricated measurements, publications, authors, DOIs, and URLs.
        </p>
      </section>

      <section className="surface p-5" aria-labelledby="assistant-status-heading">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2
            id="assistant-status-heading"
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <Bot className="size-4 text-cyan-300" aria-hidden="true" />
            Assistant configuration
          </h2>
          {status.isPending ? <Badge tone="neutral">Loading status…</Badge> : null}
          {statusData ? (
            <Badge tone={statusData.fallback_mode ? "amber" : "emerald"}>
              {assistantModeLabel(statusData.mode, statusData.enabled)}
            </Badge>
          ) : null}
        </div>
        {statusData ? (
          <dl className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2 xl:grid-cols-4">
            <div className="surface-inset p-2.5">
              <dt className="text-ink-500">Provider</dt>
              <dd className="mt-0.5 break-words text-ink-200">
                {statusData.provider}
                {statusData.model ? ` · ${statusData.model}` : ""}
              </dd>
            </div>
            <div className="surface-inset p-2.5">
              <dt className="text-ink-500">Retrieval</dt>
              <dd className="mt-0.5 text-ink-200">
                {statusData.retrieval_enabled
                  ? "Verified-document index enabled"
                  : "Disabled"}
              </dd>
            </div>
            <div className="surface-inset p-2.5">
              <dt className="text-ink-500">Allowlisted tools</dt>
              <dd className="mt-0.5 text-ink-200">{toolCount}</dd>
            </div>
            <div className="surface-inset p-2.5">
              <dt className="text-ink-500">Contract version</dt>
              <dd className="mt-0.5 font-mono text-ink-200">
                {statusData.contract_version}
              </dd>
            </div>
          </dl>
        ) : (
          <p className="mt-2 text-[11px] text-ink-400">
            Assistant configuration is reported by the backend. No capability is
            assumed while it loads.
          </p>
        )}
        {statusData?.notes.length ? (
          <ul className="mt-3 space-y-1 text-[10px] leading-relaxed text-ink-500">
            {statusData.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="surface p-5" aria-labelledby="assistant-suggestions-heading">
        <h2
          id="assistant-suggestions-heading"
          className="flex items-center gap-2 text-sm font-semibold text-ink-100"
        >
          <MessageSquareText className="size-4 text-cyan-300" aria-hidden="true" />
          Suggested questions
        </h2>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
          These are curated questions from the versioned golden set. They are
          prompts, not evidence. Each answer is re-resolved through the deterministic
          tools and citation registry.
        </p>
        {suggestions.isPending ? (
          <div className="mt-3">
            <LoadingState label="Loading suggested questions…" rows={1} />
          </div>
        ) : suggestions.isError ? (
          <InlineAlert tone="info" title="Suggested questions are unavailable">
            <p>
              You can still type a question. The assistant does not require these
              suggestions to work.
            </p>
          </InlineAlert>
        ) : (
          <ul className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(suggestions.data?.data.suggestions ?? []).map((suggestion) => (
              <SuggestionButton
                key={suggestion.question_id}
                suggestion={suggestion}
                onSelect={submitQuestion}
                disabled={pending || assistantDisabled}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="surface p-5" aria-labelledby="assistant-ask-heading">
        <h2
          id="assistant-ask-heading"
          className="flex items-center gap-2 text-sm font-semibold text-ink-100"
        >
          <CircleHelp className="size-4 text-cyan-300" aria-hidden="true" />
          Ask the assistant
        </h2>
        <form className="mt-3" onSubmit={submit} aria-label="Ask the research assistant">
          <label htmlFor="assistant-question" className="text-xs font-medium text-ink-200">
            Your question about the curated NASA PSI data
          </label>
          <p id="assistant-question-hint" className="mt-0.5 text-[11px] text-ink-500">
            Be specific about a PSI accession, dataset, field, comparison, or
            citation. Questions are limited to 1,000 characters.
          </p>
          <textarea
            id="assistant-question"
            name="question"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              if (formError) setFormError(null);
            }}
            maxLength={1000}
            rows={3}
            aria-describedby="assistant-question-hint assistant-question-count"
            aria-invalid={formError ? true : undefined}
            disabled={assistantDisabled}
            className="mt-2 w-full resize-y rounded-xl border border-navy-700 bg-navy-900/80 p-3 text-sm leading-relaxed text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring disabled:cursor-not-allowed disabled:text-ink-500"
            placeholder="e.g. How many valid PSI-10 gas-flame records are available?"
          />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <p
              id="assistant-question-count"
              className="font-mono text-[10px] text-ink-500"
              aria-live="polite"
            >
              {draft.length} / 1000 characters
            </p>
            <button
              type="submit"
              className={buttonStyles({ variant: "primary", size: "sm" })}
              disabled={assistantDisabled || pending || draft.trim().length === 0}
            >
              <Send className="size-3.5" aria-hidden="true" />
              {pending ? "Validating answer…" : "Ask assistant"}
            </button>
          </div>
          {formError ? (
            <p role="alert" className="mt-2 rounded-lg border border-rose-400/25 bg-danger-soft p-2 text-[11px] text-rose-100">
              {formError}
            </p>
          ) : null}
          {assistantDisabled ? (
            <p className="mt-2 text-[11px] text-amber-200">
              Question submission is disabled while the assistant is disabled by
              configuration.
            </p>
          ) : (
            <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-ink-500">
              <Info className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
              Conversation context is limited and non-authoritative. A prior answer is
              never reused as evidence for a new question.
            </p>
          )}
        </form>
      </section>

      <section aria-labelledby="assistant-conversation-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2
            id="assistant-conversation-heading"
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <MessageSquareText className="size-4 text-cyan-300" aria-hidden="true" />
            Conversation
          </h2>
          {turns.length > 0 ? (
            <Badge tone="outline">
              {turns.length} question{turns.length === 1 ? "" : "s"}
            </Badge>
          ) : null}
        </div>

        {turns.length === 0 ? (
          <EmptyState
            title="No questions yet"
            description={
              <>
                Ask a question above or choose one of the suggested questions. The
                evidence panel will show every citation, limitation, validation check,
                and deterministic tool result attached to the answer.
              </>
            }
            icon={<Sparkles className="size-6" aria-hidden="true" />}
          />
        ) : (
          <div
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            aria-busy={pending}
            className="space-y-6"
          >
            {turns.map((turn, index) => (
              <section
                key={turn.id}
                aria-labelledby={`${turn.id}-question`}
                className="space-y-3"
              >
                <div className="surface-inset p-3.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
                    Question {index + 1}
                  </p>
                  <h3
                    id={`${turn.id}-question`}
                    className="mt-1 text-sm font-medium leading-relaxed text-ink-100"
                  >
                    {turn.question}
                  </h3>
                </div>

                {turn.status === "pending" ? (
                  <LoadingState
                    label="Running deterministic tools, resolving citations, and validating claims…"
                    rows={3}
                  />
                ) : turn.status === "error" ? (
                  <ErrorState
                    error={turn.error}
                    title="The assistant could not complete this question"
                    onRetry={() => submitQuestion(turn.question)}
                  />
                ) : turn.envelope ? (
                  <AssistantAnswerCard
                    envelope={turn.envelope}
                    onOpenCitation={setCitationId}
                    onFollowUp={submitQuestion}
                    followUpDisabled={pending || assistantDisabled}
                  />
                ) : null}
              </section>
            ))}
          </div>
        )}
      </section>

      <InlineAlert tone="info" title="How to read the answer">
        <p>
          <span className="font-semibold text-ink-100">Fully supported</span> means
          every factual or numerical item links to a deterministic tool result and a
          resolved citation. <span className="font-semibold text-ink-100">Partially supported</span>{" "}
          means some content is labeled retrieved context, not measurement.{" "}
          <span className="font-semibold text-ink-100">Insufficient</span> or{" "}
          <span className="font-semibold text-ink-100">unavailable</span> means no
          value was invented. The evidence panel is part of the answer, not decoration.
        </p>
      </InlineAlert>

      <CitationDrawer citationId={citationId} onClose={() => setCitationId(null)} />
    </div>
  );
}
