"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, Download, FileSearch, FileText, ShieldQuestion, XCircle } from "lucide-react";
import type { Citation, CitationProvenance, ProvenanceRecord, SourceReference } from "@/lib/api/types";
import { useCitation } from "@/lib/api/hooks";
import { formatBytes, formatDate } from "@/lib/format";
import { safeExternalUrl } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { RecordDrawer } from "./record-drawer";
import { QualityBanner } from "./quality-banner";

function isProvenanceRecord(record: CitationProvenance): record is ProvenanceRecord {
  return typeof (record as ProvenanceRecord).file === "string";
}

function verificationTone(status: string): "emerald" | "amber" | "rose" | "neutral" {
  if (status === "verified") return "emerald";
  if (status === "unavailable") return "rose";
  if (status === "partial") return "amber";
  return "neutral";
}

function availabilityTone(status: string): "emerald" | "rose" | "neutral" {
  if (status === "available") return "emerald";
  if (status === "unavailable") return "rose";
  return "neutral";
}

function CitationProvenanceList({ records }: { records: CitationProvenance[] }) {
  if (records.length === 0) {
    return <p className="text-xs text-ink-400">No provenance records were returned for this citation.</p>;
  }
  return (
    <ul className="space-y-2">
      {records.map((record, index) => {
        if (isProvenanceRecord(record)) {
          const sourceUrl = safeExternalUrl(record.source_url);
          return (
            <li
              key={`${record.file}-${index}`}
              className="rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="cyan">{record.accession}</Badge>
                <span className="break-all font-mono text-[11px] text-ink-300">{record.file}</span>
              </div>
              <p className="mt-1 text-[10px] text-ink-500">
                {record.sheet ? `Sheet ${record.sheet} · ` : ""}
                Source rows {record.rows?.join(", ") || record.row_range?.join("–") || "not specified"} ·
                retrieved {formatDate(record.retrieved_at)}
              </p>
              {record.sha256 ? (
                <p className="mt-1 break-all font-mono text-[10px] text-ink-500">sha256: {record.sha256}</p>
              ) : null}
              {sourceUrl ? (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-[11px] text-cyan-300 hover:text-cyan-200 focus-ring"
                >
                  Open NASA source file
                </a>
              ) : null}
            </li>
          );
        }
        const reference = record as SourceReference;
        const sourceUrl = safeExternalUrl(reference.source_url);
        return (
          <li
            key={`${reference.path ?? reference.file_name ?? reference.kind}-${index}`}
            className="rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5"
          >
            <div className="flex flex-wrap items-center gap-2">
              {reference.accession ? <Badge tone="cyan">{reference.accession}</Badge> : null}
              <span className="break-all font-mono text-[11px] text-ink-300">
                {reference.file_name ?? reference.path ?? reference.kind}
              </span>
            </div>
            {reference.section ? (
              <p className="mt-1 text-[10px] text-ink-500">{reference.section}</p>
            ) : null}
            {reference.sha256 ? (
              <p className="mt-1 break-all font-mono text-[10px] text-ink-500">sha256: {reference.sha256}</p>
            ) : null}
            {sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-[11px] text-cyan-300 hover:text-cyan-200 focus-ring"
              >
                Open NASA source file
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function CitationDetail({ citation }: { citation: Citation }) {
  const sourceUrl = safeExternalUrl(citation.source.source_url);
  const downloadStatus = citation.retrieval.download_status ?? "not recorded";
  const checksumMatch = citation.retrieval.checksum_match;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={citation.kind === "row" ? "violet" : "cyan"}>{citation.kind} citation</Badge>
        <Badge tone="outline">{citation.accession}</Badge>
        <Badge tone={verificationTone(citation.verification.status)}>
          {citation.verification.status.replace(/_/g, " ")}
        </Badge>
        <Badge tone={availabilityTone(citation.availability.status)}>
          {citation.availability.status}
        </Badge>
        {citation.availability.downloadable ? (
          <Badge tone="emerald">downloadable</Badge>
        ) : (
          <Badge tone="rose">not downloadable</Badge>
        )}
      </div>

      <p className="break-all rounded-lg border border-navy-700/60 bg-navy-950/50 p-2.5 font-mono text-[10px] text-ink-400">
        {citation.citation_id}
      </p>

      <section aria-labelledby="citation-file">
        <h3 id="citation-file" className="flex items-center gap-2 text-xs font-semibold text-ink-100">
          <FileText className="size-3.5 text-cyan-300" aria-hidden="true" />
          Source file
        </h3>
        <dl className="mt-2 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-ink-500">File name</dt>
            <dd className="break-all font-mono text-ink-300">{citation.file.name}</dd>
          </div>
          <div>
            <dt className="text-ink-500">File kind</dt>
            <dd className="text-ink-300">{citation.file.kind.replace(/_/g, " ")}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Manifest dataset</dt>
            <dd className="font-mono text-ink-300">{citation.file.manifest_dataset ?? "not mapped"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Priority</dt>
            <dd className="text-ink-300">{citation.file.priority ?? "not set"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Added to manifest</dt>
            <dd className="text-ink-300">{citation.file.in_added ? "yes" : "no"}</dd>
          </div>
          {citation.file.purpose ? (
            <div className="sm:col-span-2">
              <dt className="text-ink-500">Purpose</dt>
              <dd className="leading-relaxed text-ink-300">{citation.file.purpose}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <section aria-labelledby="citation-locator">
        <h3 id="citation-locator" className="text-xs font-semibold text-ink-100">
          Locator
        </h3>
        <dl className="mt-2 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2">
          <div>
            <dt className="text-ink-500">Type</dt>
            <dd className="text-ink-300">{citation.locator.type}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Sheet</dt>
            <dd className="text-ink-300">{citation.locator.sheet ?? "not applicable"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Row</dt>
            <dd className="font-mono text-ink-300">{citation.locator.row ?? "not applicable"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Row range</dt>
            <dd className="font-mono text-ink-300">
              {citation.locator.row_range?.length
                ? citation.locator.row_range.join("–")
                : "not applicable"}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="citation-retrieval">
        <h3 id="citation-retrieval" className="text-xs font-semibold text-ink-100">
          Retrieval and checksum
        </h3>
        <dl className="mt-2 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2">
          <div>
            <dt className="text-ink-500">Download status</dt>
            <dd className="font-mono text-ink-300">{downloadStatus}</dd>
          </div>
          <div>
            <dt className="text-ink-500">HTTP status</dt>
            <dd className="font-mono text-ink-300">{citation.retrieval.http_status ?? "not recorded"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Retrieved</dt>
            <dd className="text-ink-300">{formatDate(citation.retrieval.retrieved_at)}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Bytes</dt>
            <dd className="font-mono text-ink-300">
              {formatBytes(citation.retrieval.bytes)}
              {citation.retrieval.expected_bytes !== null
                ? ` / expected ${formatBytes(citation.retrieval.expected_bytes)}`
                : ""}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-ink-500">SHA-256 (actual)</dt>
            <dd className="break-all font-mono text-[10px] text-ink-400">
              {citation.retrieval.checksum_actual ?? "checksum_not_available"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-ink-500">SHA-256 (expected)</dt>
            <dd className="break-all font-mono text-[10px] text-ink-400">
              {citation.retrieval.checksum_expected ?? "checksum_not_recorded"}
            </dd>
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <dt className="text-ink-500">Checksum match</dt>
            <dd className="flex items-center gap-1 text-ink-300">
              {checksumMatch === true ? (
                <>
                  <CheckCircle2 className="size-3.5 text-emerald-300" aria-hidden="true" />
                  verified match
                </>
              ) : checksumMatch === false ? (
                <>
                  <XCircle className="size-3.5 text-rose-300" aria-hidden="true" />
                  mismatch
                </>
              ) : (
                <>
                  <ShieldQuestion className="size-3.5 text-ink-500" aria-hidden="true" />
                  not available
                </>
              )}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="citation-verification">
        <h3 id="citation-verification" className="text-xs font-semibold text-ink-100">
          Verification checks
        </h3>
        {citation.verification.checks.length === 0 ? (
          <p className="mt-2 text-xs text-ink-400">No verification checks were returned.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {citation.verification.checks.map((check) => (
              <li key={check} className="flex items-start gap-2 rounded-lg border border-navy-700/60 bg-navy-950/35 p-2 text-[11px] text-ink-300">
                <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-emerald-300" aria-hidden="true" />
                <span className="font-mono">{check}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {citation.row_verification ? (
        <section aria-labelledby="citation-row-verification">
          <h3 id="citation-row-verification" className="text-xs font-semibold text-ink-100">
            Row verification
          </h3>
          <dl className="mt-2 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2">
            <div>
              <dt className="text-ink-500">Row verified</dt>
              <dd className="text-ink-300">{citation.row_verification.row_verified ? "yes" : "no"}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-ink-500">Canonical tables</dt>
              <dd className="font-mono text-ink-300">
                {citation.row_verification.row_tables.join(", ") || "none"}
              </dd>
            </div>
          </dl>
          {citation.row_verification.warnings.length > 0 ? (
            <ul className="mt-2 space-y-1.5">
              {citation.row_verification.warnings.map((warning) => (
                <li key={warning} className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-2 text-[11px] text-amber-100">
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <section aria-labelledby="citation-availability">
        <h3 id="citation-availability" className="flex items-center gap-2 text-xs font-semibold text-ink-100">
          {citation.availability.downloadable ? (
            <Download className="size-3.5 text-emerald-300" aria-hidden="true" />
          ) : (
            <AlertTriangle className="size-3.5 text-rose-300" aria-hidden="true" />
          )}
          Availability
        </h3>
        <p className="mt-2 text-[11px] leading-relaxed text-ink-300">
          {citation.availability.reason ??
            (citation.availability.downloadable
              ? "The source file is available and its checksum is verified."
              : "No download reason was returned. Do not infer availability.")}
        </p>
        {citation.availability.downloadable && sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1.5 text-[11px] font-medium text-emerald-200 hover:bg-emerald-400/15 focus-ring"
          >
            <Download className="size-3.5" aria-hidden="true" />
            Download NASA source file
          </a>
        ) : (
          <p className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/5 p-2 text-[11px] text-rose-100">
            This citation has no downloadable file. No substitute URL is provided.
          </p>
        )}
      </section>

      <section aria-labelledby="citation-provenance">
        <h3 id="citation-provenance" className="flex items-center gap-2 text-xs font-semibold text-ink-100">
          <FileSearch className="size-3.5 text-cyan-300" aria-hidden="true" />
          Provenance
        </h3>
        <div className="mt-2">
          <CitationProvenanceList records={citation.provenance} />
        </div>
      </section>

      <div className="flex flex-wrap gap-3 border-t border-navy-700/60 pt-3">
        {citation.dataset_ids.map((datasetId) => (
          <Link
            key={datasetId}
            href={`/datasets/${encodeURIComponent(datasetId)}`}
            className="text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
          >
            Open dataset {datasetId}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function CitationDrawer({
  citationId,
  onClose,
}: {
  citationId: string | null;
  onClose: () => void;
}) {
  const citation = useCitation(citationId ?? "", Boolean(citationId));

  return (
    <RecordDrawer
      open={Boolean(citationId)}
      title="Citation record"
      subtitle={
        citationId ? (
          <span className="break-all font-mono text-[10px]">{citationId}</span>
        ) : null
      }
      onClose={onClose}
    >
      {citation.isPending ? (
        <LoadingState label="Loading citation record…" rows={4} />
      ) : citation.isError ? (
        <ErrorState
          error={citation.error}
          title="The citation record could not be loaded"
          onRetry={() => citation.refetch()}
        />
      ) : citation.data ? (
        <div className="space-y-4">
          <CitationDetail citation={citation.data.data} />
          <QualityBanner quality={citation.data.quality} title="Citation response quality" />
        </div>
      ) : null}
    </RecordDrawer>
  );
}

export function CitationButton({
  citationId,
  onClick,
  label = "Cite this source",
  className,
}: {
  citationId: string | null | undefined;
  onClick: (citationId: string) => void;
  label?: string;
  className?: string;
}) {
  if (!citationId) return null;
  return (
    <button
      type="button"
      onClick={() => onClick(citationId)}
      className={
        className ??
        "inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
      }
    >
      <FileText className="size-3" aria-hidden="true" />
      {label}
    </button>
  );
}
