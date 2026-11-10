"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Database,
  FileText,
  ListChecks,
  Quote,
  ShieldCheck,
  ShieldQuestion,
  Wrench,
  XCircle,
} from "lucide-react";
import type {
  AssistantAnswer,
  AssistantCitationReference,
  AssistantClaim,
  AssistantSupportingData,
  Envelope,
} from "@/lib/api/types";
import {
  ANSWER_TYPE_LABELS,
  CONFIDENCE_TONES,
  EVIDENCE_STATUS_DESCRIPTIONS,
  EVIDENCE_STATUS_LABELS,
  EVIDENCE_STATUS_TONES,
  LIMITATION_TONES,
  TOOL_STATUS_TONES,
  displayAssistantValue,
  humanizeIdentifier,
  isRecord,
} from "@/lib/assistant";
import { formatDate, formatDateTime } from "@/lib/format";
import { valueKindLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "@/components/ui/disclosure";

interface AssistantAnswerCardProps {
  envelope: Envelope<AssistantAnswer>;
  onOpenCitation: (citationId: string) => void;
  onFollowUp?: (question: string) => void;
  followUpDisabled?: boolean;
}

function CitationButtons({
  ids,
  citationsById,
  onOpenCitation,
}: {
  ids: string[];
  citationsById: Map<string, AssistantCitationReference>;
  onOpenCitation: (citationId: string) => void;
}) {
  const unique = Array.from(new Set(ids));
  if (unique.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {unique.map((citationId) => {
        const citation = citationsById.get(citationId);
        return (
          <button
            key={citationId}
            type="button"
            onClick={() => onOpenCitation(citationId)}
            className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-cyan-400/25 bg-cyan-400/5 px-2 py-0.5 text-[10px] font-medium text-cyan-200 hover:bg-cyan-400/10 focus-ring"
            title={citation?.file_name ?? citationId}
            aria-label={
              citation
                ? `Open citation record for ${citation.file_name}`
                : `Open citation record ${citationId}`
            }
          >
            <FileText className="size-3 shrink-0" aria-hidden="true" />
            <span className="font-mono">{citationId}</span>
          </button>
        );
      })}
    </div>
  );
}

function ValueTree({
  values,
  depth = 0,
}: {
  values: Record<string, unknown>;
  depth?: number;
}) {
  const entries = Object.entries(values);
  if (entries.length === 0) {
    return (
      <p className="text-[11px] text-ink-500">
        No structured values were returned for this item.
      </p>
    );
  }
  return (
    <dl className={depth === 0 ? "space-y-2" : "mt-1 space-y-1.5 border-l border-navy-700/60 pl-3"}>
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt className="font-mono text-[10px] text-ink-500">{humanizeIdentifier(key)}</dt>
          <dd className="mt-0.5 break-words text-[11px] text-ink-200">
            {isRecord(value) ? (
              <ValueTree values={value} depth={depth + 1} />
            ) : Array.isArray(value) ? (
              <span className="font-mono">
                {value.length === 0
                  ? "[]"
                  : value.map((item) => displayAssistantValue(item)).join(", ")}
              </span>
            ) : (
              <span className="font-mono">{displayAssistantValue(value)}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function SupportingDataItem({
  item,
  citationsById,
  onOpenCitation,
}: {
  item: AssistantSupportingData;
  citationsById: Map<string, AssistantCitationReference>;
  onOpenCitation: (citationId: string) => void;
}) {
  return (
    <li className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-ink-100">{item.label}</span>
        <Badge tone="violet">{valueKindLabel(item.value_kind)}</Badge>
        {item.unit ? <Badge tone="outline">{item.unit}</Badge> : null}
        {item.accession ? <Badge tone="cyan">{item.accession}</Badge> : null}
        {item.dataset_id ? <Badge tone="neutral">{item.dataset_id}</Badge> : null}
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-300">{item.summary}</p>
      <div className="mt-2">
        <ValueTree values={item.values} />
      </div>
      <div className="mt-2">
        <CitationButtons
          ids={item.citation_ids}
          citationsById={citationsById}
          onOpenCitation={onOpenCitation}
        />
      </div>
    </li>
  );
}

function ClaimItem({
  claim,
  citationsById,
  onOpenCitation,
}: {
  claim: AssistantClaim;
  citationsById: Map<string, AssistantCitationReference>;
  onOpenCitation: (citationId: string) => void;
}) {
  return (
    <li className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="outline">{humanizeIdentifier(claim.claim_type)}</Badge>
        {claim.value_kind ? (
          <Badge tone="violet">{valueKindLabel(claim.value_kind)}</Badge>
        ) : null}
        <Badge tone={claim.supported ? "emerald" : "rose"}>
          {claim.supported ? "supported" : "unsupported"}
        </Badge>
        {claim.accession ? <Badge tone="cyan">{claim.accession}</Badge> : null}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-200">{claim.text}</p>
      {claim.value !== null ? (
        <p className="mt-1 font-mono text-[11px] text-ink-100">
          {displayAssistantValue(claim.value)}
          {claim.unit ? ` ${claim.unit}` : ""}
        </p>
      ) : null}
      {claim.validation_notes.length > 0 ? (
        <ul className="mt-2 space-y-1 text-[10px] text-ink-400">
          {claim.validation_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-2">
        <CitationButtons
          ids={claim.citation_ids}
          citationsById={citationsById}
          onOpenCitation={onOpenCitation}
        />
      </div>
    </li>
  );
}

function CitationRecordItem({
  citation,
  onOpenCitation,
}: {
  citation: AssistantCitationReference;
  onOpenCitation: (citationId: string) => void;
}) {
  return (
    <li className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={citation.citation_type === "row" ? "violet" : "cyan"}>
          {citation.citation_type}
        </Badge>
        <Badge tone={citation.verification_status === "verified" ? "emerald" : "amber"}>
          {humanizeIdentifier(citation.verification_status)}
        </Badge>
        <Badge tone={citation.availability === "available" ? "emerald" : "rose"}>
          {humanizeIdentifier(citation.availability)}
        </Badge>
        {citation.downloadable ? null : <Badge tone="rose">not downloadable</Badge>}
      </div>
      <button
        type="button"
        onClick={() => onOpenCitation(citation.citation_id)}
        className="mt-2 block w-full break-all text-left font-mono text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
        aria-label={`Open citation record for ${citation.file_name}`}
      >
        {citation.citation_id}
      </button>
      <p className="mt-1 break-all text-[11px] text-ink-300">{citation.file_name}</p>
      <p className="mt-1 text-[10px] text-ink-500">
        {citation.accession}
        {citation.sheet ? ` · sheet ${citation.sheet}` : ""}
        {citation.row !== null ? ` · row ${citation.row}` : ""}
        {citation.dataset_ids.length > 0
          ? ` · ${citation.dataset_ids.join(", ")}`
          : ""}
      </p>
      {citation.sha256 ? (
        <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
          sha256: {citation.sha256}
        </p>
      ) : null}
    </li>
  );
}

export function AssistantAnswerCard({
  envelope,
  onOpenCitation,
  onFollowUp,
  followUpDisabled = false,
}: AssistantAnswerCardProps) {
  const answer = envelope.data;
  const citationsById = new Map(
    answer.citations.map((citation) => [citation.citation_id, citation]),
  );
  const answerHeadingId = `assistant-answer-${answer.request_id}`;
  const hasSupportingData = answer.supporting_data.length > 0;
  const hasClaims = answer.claims.length > 0;

  return (
    <article
      aria-labelledby={answerHeadingId}
      className="space-y-4"
      data-evidence-status={answer.evidence_status}
    >
      <header className="surface p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={EVIDENCE_STATUS_TONES[answer.evidence_status]}>
            {EVIDENCE_STATUS_LABELS[answer.evidence_status]}
          </Badge>
          <Badge tone="cyan">{ANSWER_TYPE_LABELS[answer.answer_type]}</Badge>
          <Badge tone={CONFIDENCE_TONES[answer.confidence]}>
            {answer.confidence} confidence
          </Badge>
          <Badge tone="outline">{answer.provider}</Badge>
          {answer.fallback_mode ? <Badge tone="amber">fallback</Badge> : null}
          <Badge tone={answer.validation.passed ? "emerald" : "rose"}>
            {answer.validation.passed ? "validated" : "validation failed"}
          </Badge>
        </div>
        <h2 id={answerHeadingId} className="mt-3 text-base font-semibold text-ink-50">
          {answer.answer_type === "clarification_required"
            ? "The assistant needs one detail"
            : "Grounded answer"}
        </h2>
        <p className="mt-1 max-w-3xl text-[11px] leading-relaxed text-ink-400">
          {EVIDENCE_STATUS_DESCRIPTIONS[answer.evidence_status]}
        </p>
      </header>

      {answer.fallback_mode ? (
        <div className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3.5 text-xs text-amber-100">
          <p className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            Deterministic fallback is active
          </p>
          <p className="mt-1 leading-relaxed text-ink-300">
            {answer.fallback_reason ??
              "The optional provider was unavailable or its output was rejected. The validated deterministic draft is shown unchanged."}
          </p>
        </div>
      ) : null}

      {answer.validation.passed ? null : (
        <div className="rounded-xl border border-rose-400/25 bg-rose-400/5 p-3.5 text-xs text-rose-100">
          <p className="flex items-center gap-2 font-semibold">
            <XCircle className="size-4 shrink-0" aria-hidden="true" />
            Validation failed; the draft was withheld
          </p>
          <p className="mt-1 leading-relaxed text-ink-300">
            The application did not release an unverified numerical claim or
            citation. The text below is a safe failure response, not a repaired
            scientific answer.
          </p>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-prose`}>
            <h3 id={`${answerHeadingId}-prose`} className="text-xs font-semibold text-ink-100">
              Answer
            </h3>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-100">
              {answer.answer}
            </p>
            <dl className="mt-4 grid gap-x-5 gap-y-2 border-t border-navy-700/60 pt-3 text-[11px] sm:grid-cols-2">
              <div>
                <dt className="text-ink-500">Confidence basis</dt>
                <dd className="mt-0.5 leading-relaxed text-ink-300">
                  {answer.confidence_basis}
                </dd>
              </div>
              <div>
                <dt className="text-ink-500">Generated</dt>
                <dd className="mt-0.5 text-ink-300">{formatDateTime(answer.generated_at)}</dd>
              </div>
            </dl>

            {answer.provider_usage ? (
              <div className="mt-3 rounded-lg border border-navy-700/60 bg-navy-950/40 p-3 text-[11px] text-ink-400">
                <p className="font-semibold text-ink-300">Provider usage</p>
                <p className="mt-1 leading-relaxed">
                  {answer.provider_usage.total_tokens === null
                    ? "Token usage was not reported."
                    : `${answer.provider_usage.total_tokens} tokens (${answer.provider_usage.prompt_tokens ?? 0} prompt + ${answer.provider_usage.completion_tokens ?? 0} completion).`}
                  {answer.provider_usage.estimated_cost_usd === null
                    ? answer.provider_usage.pricing_configured
                      ? " Cost was not reported."
                      : " Cost pricing is not configured."
                    : ` Estimated cost: $${answer.provider_usage.estimated_cost_usd.toFixed(6)} USD.`}
                </p>
              </div>
            ) : null}

            {answer.clarification ? (
              <div className="mt-4 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3.5">
                <p className="flex items-center gap-2 text-xs font-semibold text-cyan-100">
                  <CircleHelp className="size-4" aria-hidden="true" />
                  {answer.clarification.question}
                </p>
                {answer.clarification.options.length > 0 && onFollowUp ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {answer.clarification.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        disabled={followUpDisabled}
                        onClick={() => onFollowUp(option)}
                        className="rounded-lg border border-cyan-400/25 bg-cyan-400/10 px-2.5 py-1.5 text-[11px] font-medium text-cyan-100 hover:bg-cyan-400/15 focus-ring disabled:cursor-not-allowed disabled:text-ink-500"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                ) : null}
                {answer.clarification.missing.length > 0 ? (
                  <p className="mt-2 text-[10px] text-ink-400">
                    Missing: {answer.clarification.missing.join(", ")}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-data`}>
            <h3
              id={`${answerHeadingId}-data`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <Database className="size-3.5 text-cyan-300" aria-hidden="true" />
              Supporting data
            </h3>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Values below come from deterministic allowlisted tools. Units and
              value kinds are preserved; a missing value is never zero.
            </p>
            {hasSupportingData ? (
              <ul className="mt-3 space-y-2.5">
                {answer.supporting_data.map((item) => (
                  <SupportingDataItem
                    key={item.data_id}
                    item={item}
                    citationsById={citationsById}
                    onOpenCitation={onOpenCitation}
                  />
                ))}
              </ul>
            ) : (
              <p className="mt-3 rounded-lg border border-navy-700/60 bg-navy-950/35 p-3 text-[11px] text-ink-400">
                No deterministic supporting data was returned for this answer.
              </p>
            )}
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-claims`}>
            <h3
              id={`${answerHeadingId}-claims`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <ListChecks className="size-3.5 text-cyan-300" aria-hidden="true" />
              Claims
            </h3>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Each claim is linked to a tool call and citation. An unsupported
              claim would fail validation instead of being released as fact.
            </p>
            {hasClaims ? (
              <ul className="mt-3 space-y-2.5">
                {answer.claims.map((claim) => (
                  <ClaimItem
                    key={claim.claim_id}
                    claim={claim}
                    citationsById={citationsById}
                    onOpenCitation={onOpenCitation}
                  />
                ))}
              </ul>
            ) : (
              <p className="mt-3 rounded-lg border border-navy-700/60 bg-navy-950/35 p-3 text-[11px] text-ink-400">
                No atomic claims were attached to this answer.
              </p>
            )}
          </section>
        </div>

        <aside aria-label="Evidence panel" className="space-y-4">
          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-summary`}>
            <h3
              id={`${answerHeadingId}-summary`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <ShieldCheck className="size-3.5 text-emerald-300" aria-hidden="true" />
              Evidence summary
            </h3>
            <dl className="mt-3 space-y-2 text-[11px]">
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Evidence status</dt>
                <dd className="text-right text-ink-200">
                  {EVIDENCE_STATUS_LABELS[answer.evidence_status]}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Answer type</dt>
                <dd className="text-right text-ink-200">
                  {ANSWER_TYPE_LABELS[answer.answer_type]}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Confidence</dt>
                <dd className="text-right text-ink-200">{answer.confidence}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Citations</dt>
                <dd className="text-right text-ink-200">{answer.citations.length}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Tools used</dt>
                <dd className="text-right text-ink-200">{answer.tools_used.length}</dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Dataset version</dt>
                <dd className="break-all text-right font-mono text-[10px] text-ink-200">
                  {answer.dataset_version ?? "not reported"}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Request</dt>
                <dd className="break-all text-right font-mono text-[10px] text-ink-200">
                  {answer.request_id}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-3">
                <dt className="text-ink-500">Contract</dt>
                <dd className="text-right font-mono text-[10px] text-ink-200">
                  {answer.contract_version}
                </dd>
              </div>
            </dl>
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-citations`}>
            <h3
              id={`${answerHeadingId}-citations`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <FileText className="size-3.5 text-cyan-300" aria-hidden="true" />
              Citations
            </h3>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
              Open a citation to resolve its Phase 4 file record, locator, and
              checksum. No citation is generated by a model.
            </p>
            {answer.citations.length > 0 ? (
              <ul className="mt-3 space-y-2.5">
                {answer.citations.map((citation) => (
                  <CitationRecordItem
                    key={citation.citation_id}
                    citation={citation}
                    onOpenCitation={onOpenCitation}
                  />
                ))}
              </ul>
            ) : (
              <p className="mt-3 rounded-lg border border-navy-700/60 bg-navy-950/35 p-3 text-[11px] text-ink-400">
                No citations were attached. A factual or numerical claim without
                a citation cannot be considered supported.
              </p>
            )}
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-limitations`}>
            <h3
              id={`${answerHeadingId}-limitations`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <ShieldQuestion className="size-3.5 text-amber-300" aria-hidden="true" />
              Limitations
            </h3>
            {answer.limitations.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {answer.limitations.map((limitation) => (
                  <li
                    key={`${limitation.code}-${limitation.message}`}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone={LIMITATION_TONES[limitation.severity]}>
                        {limitation.severity}
                      </Badge>
                      <span className="font-mono text-[10px] text-ink-400">
                        {limitation.code}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[11px] leading-relaxed text-ink-300">
                      {limitation.message}
                    </p>
                    <div className="mt-2">
                      <CitationButtons
                        ids={limitation.citation_ids}
                        citationsById={citationsById}
                        onOpenCitation={onOpenCitation}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-[11px] text-ink-400">
                No additional limitations were attached to this answer.
              </p>
            )}
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-validation`}>
            <h3
              id={`${answerHeadingId}-validation`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <CheckCircle2 className="size-3.5 text-emerald-300" aria-hidden="true" />
              Validation
            </h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone={answer.validation.passed ? "emerald" : "rose"}>
                {answer.validation.passed ? "passed" : "failed"}
              </Badge>
              <Badge tone={answer.validation.citation_validation_passed ? "emerald" : "rose"}>
                citations {answer.validation.citation_validation_passed ? "ok" : "failed"}
              </Badge>
              <Badge tone={answer.validation.claim_validation_passed ? "emerald" : "rose"}>
                claims {answer.validation.claim_validation_passed ? "ok" : "failed"}
              </Badge>
            </div>
            {answer.validation.errors.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {answer.validation.errors.map((error) => (
                  <li
                    key={error}
                    className="rounded-lg border border-rose-400/20 bg-rose-400/5 p-2 text-[10px] text-rose-100"
                  >
                    {error}
                  </li>
                ))}
              </ul>
            ) : null}
            {answer.validation.warnings.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {answer.validation.warnings.map((warning) => (
                  <li
                    key={warning}
                    className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-2 text-[10px] text-amber-100"
                  >
                    {warning}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="mt-3">
              <Disclosure
                summary={`${answer.validation.checks.length} validation checks`}
                className="bg-navy-950/35"
              >
                {answer.validation.checks.length === 0 ? (
                  <p className="text-[11px] text-ink-400">No checks were recorded.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {answer.validation.checks.map((check) => (
                      <li key={check.name} className="flex items-start gap-2 text-[10px] text-ink-300">
                        {check.passed ? (
                          <CheckCircle2
                            className="mt-0.5 size-3 shrink-0 text-emerald-300"
                            aria-hidden="true"
                          />
                        ) : (
                          <XCircle
                            className="mt-0.5 size-3 shrink-0 text-rose-300"
                            aria-hidden="true"
                          />
                        )}
                        <span>
                          <span className="font-mono">{check.name}</span>
                          {check.detail ? ` — ${check.detail}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Disclosure>
            </div>
          </section>

          <section className="surface p-5" aria-labelledby={`${answerHeadingId}-tools`}>
            <h3
              id={`${answerHeadingId}-tools`}
              className="flex items-center gap-2 text-xs font-semibold text-ink-100"
            >
              <Wrench className="size-3.5 text-cyan-300" aria-hidden="true" />
              Tools used
            </h3>
            {answer.tools_used.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {answer.tools_used.map((tool) => (
                  <li
                    key={tool.call_id}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone="outline">{tool.tool}</Badge>
                      <Badge tone={TOOL_STATUS_TONES[tool.status]}>{tool.status}</Badge>
                      <span className="font-mono text-[10px] text-ink-500">
                        {tool.duration_ms} ms
                      </span>
                    </div>
                    {tool.result_summary ? (
                      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-300">
                        {tool.result_summary}
                      </p>
                    ) : null}
                    {tool.error ? (
                      <p className="mt-1 text-[10px] text-rose-200">{tool.error}</p>
                    ) : null}
                    {Object.keys(tool.arguments).length > 0 ? (
                      <div className="mt-2">
                        <Disclosure summary="Arguments" className="bg-navy-900/40">
                          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-[10px] text-ink-300">
                            {JSON.stringify(tool.arguments, null, 2)}
                          </pre>
                        </Disclosure>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-[11px] text-ink-400">No tools were run for this answer.</p>
            )}
          </section>

          {answer.evidence.length > 0 ? (
            <section className="surface p-5" aria-labelledby={`${answerHeadingId}-evidence`}>
              <h3
                id={`${answerHeadingId}-evidence`}
                className="flex items-center gap-2 text-xs font-semibold text-ink-100"
              >
                <Quote className="size-3.5 text-violet-400" aria-hidden="true" />
                Retrieved evidence
              </h3>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
                Retrieved source text is untrusted evidence. It is never followed
                as instructions and never becomes a citation without a resolved
                Phase 4 record.
              </p>
              <ul className="mt-3 space-y-2.5">
                {answer.evidence.map((item) => (
                  <li
                    key={item.evidence_id}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone="violet">{humanizeIdentifier(item.source_type)}</Badge>
                      {item.accession ? <Badge tone="cyan">{item.accession}</Badge> : null}
                      {item.dataset_id ? <Badge tone="neutral">{item.dataset_id}</Badge> : null}
                      <Badge tone="amber">untrusted</Badge>
                    </div>
                    <p className="mt-1.5 text-[11px] font-medium text-ink-100">{item.title}</p>
                    {item.snippet ? (
                      <p className="mt-1 text-[10px] leading-relaxed text-ink-400">
                        {item.snippet}
                      </p>
                    ) : null}
                    {item.section ? (
                      <p className="mt-1 text-[10px] text-ink-500">Section: {item.section}</p>
                    ) : null}
                    {item.citation_id ? (
                      <div className="mt-2">
                        <CitationButtons
                          ids={[item.citation_id]}
                          citationsById={citationsById}
                          onOpenCitation={onOpenCitation}
                        />
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <p className="px-1 text-[10px] leading-relaxed text-ink-500">
            Conversation memory is bounded and non-authoritative. A previous
            answer is never reused as evidence for a later question. Citation
            records were last checked at generation time{" "}
            {formatDate(answer.generated_at)}.
          </p>
        </aside>
      </div>
    </article>
  );
}
