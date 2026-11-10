"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  FileQuestion,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { usePublication } from "@/lib/api/hooks";
import { formatDate, humanizeKey } from "@/lib/format";
import { safeExternalUrl } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { SourceReferenceList } from "@/components/scientific/provenance";
import { QualityBanner } from "@/components/scientific/quality-banner";

const FIELD_ORDER = ["title", "authors", "doi", "year", "venue", "status"];

export default function PublicationDetailPage() {
  const params = useParams<{ publicationId: string }>();
  const publicationId = decodeURIComponent(params.publicationId ?? "");
  const publication = usePublication(publicationId);

  if (publication.isPending) {
    return <LoadingState label={`Loading publication ${publicationId}…`} rows={5} />;
  }

  if (publication.isError) {
    return (
      <ErrorState
        error={publication.error}
        title={`Publication ${publicationId} could not be loaded`}
        onRetry={() => publication.refetch()}
      >
        <Link href="/publications" className={buttonStyles({ size: "sm", className: "mt-3" })}>
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to publications
        </Link>
      </ErrorState>
    );
  }

  const record = publication.data.data;
  const quality = publication.data.quality;
  const doiUrl = safeExternalUrl(record.doi_url);
  const verified = record.verification.verified_fields;
  const unavailable = record.verification.unavailable_fields;
  const conflicts = record.verification.conflicts;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Publication record"
        title={record.title}
        description={
          <>
            Registry record <span className="mono text-ink-200">{record.publication_id}</span>.
            Bibliographic values below are the verified source values. Missing year and venue are
            reported as unavailable rather than reconstructed.
          </>
        }
        actions={
          <Link href="/publications" className={buttonStyles()}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Publications
          </Link>
        }
        meta={
          <>
            <Badge tone={record.doi ? "emerald" : "amber"}>
              {record.doi ? "DOI present" : "No DOI"}
            </Badge>
            <Badge tone="cyan">{record.verification.status.replace(/_/g, " ")}</Badge>
            <Badge tone="outline">{record.status}</Badge>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <section className="surface p-5" aria-labelledby="publication-bibliography">
          <h2
            id="publication-bibliography"
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
            Bibliographic record
          </h2>
          <dl className="mt-4 space-y-3 text-xs">
            <div>
              <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Title</dt>
              <dd className="mt-1 leading-relaxed text-ink-100">{record.title}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Authors</dt>
              <dd className="mt-1 leading-relaxed text-ink-200">
                {record.authors.length > 0
                  ? record.authors.join(", ")
                  : record.authors_raw || "not available"}
              </dd>
              <dd className="mt-1 break-words text-[10px] text-ink-500">
                Parsed as <span className="font-mono">{record.author_parse}</span> from{" "}
                <span className="font-mono">{record.authors_raw || "no raw string"}</span>
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">DOI</dt>
              <dd className="mt-1">
                {record.doi ? (
                  doiUrl ? (
                    <a
                      href={doiUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 break-all font-mono text-cyan-300 hover:text-cyan-200 focus-ring"
                    >
                      {record.doi}
                      <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  ) : (
                    <span className="break-all font-mono text-ink-300">{record.doi}</span>
                  )
                ) : (
                  <span className="text-ink-400">not available in the source registry</span>
                )}
              </dd>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Year</dt>
                <dd className="mt-1 text-ink-300">
                  {record.year ?? "unavailable in the source registry"}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Venue</dt>
                <dd className="mt-1 text-ink-300">
                  {record.venue ?? "unavailable in the source registry"}
                </dd>
              </div>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Status</dt>
              <dd className="mt-1 font-mono text-ink-300">{record.status}</dd>
            </div>
          </dl>

          <div className="mt-5 border-t border-navy-700/60 pt-4">
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
              Related investigations
            </p>
            {record.related_investigations.length === 0 ? (
              <p className="mt-1.5 text-[11px] text-ink-400">
                No related investigation is recorded for this publication.
              </p>
            ) : (
              <ul className="mt-2 space-y-2">
                {record.related_investigations.map((investigation) => (
                  <li
                    key={investigation.accession}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/investigations/${encodeURIComponent(investigation.accession)}`}
                        className="font-mono text-[11px] text-cyan-300 hover:text-cyan-200 focus-ring"
                      >
                        {investigation.accession}
                      </Link>
                      {investigation.acronym ? (
                        <Badge tone="violet">{investigation.acronym}</Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-ink-300">
                      {investigation.title}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="surface p-5" aria-labelledby="publication-verification">
          <h2
            id="publication-verification"
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <ShieldCheck className="size-4 text-emerald-300" aria-hidden="true" />
            Verification
          </h2>
          <dl className="mt-3 space-y-2.5 text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Status</dt>
              <dd className="font-mono text-ink-200">{record.verification.status}</dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Source</dt>
              <dd className="break-all font-mono text-[10px] text-ink-300">
                {record.verification.source}
              </dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Snapshot date</dt>
              <dd className="text-ink-200">{formatDate(record.verification.snapshot_date)}</dd>
            </div>
          </dl>

          <div className="mt-4 rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-100">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              Verified fields
            </p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {verified.map((field) => (
                <li
                  key={field}
                  className="rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 font-mono text-[10px] text-emerald-200"
                >
                  {field}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-100">
              <FileQuestion className="size-3.5" aria-hidden="true" />
              Unavailable fields
            </p>
            {unavailable.length === 0 ? (
              <p className="mt-1.5 text-[11px] text-ink-300">None recorded.</p>
            ) : (
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {unavailable.map((field) => (
                  <li
                    key={field}
                    className="rounded border border-amber-400/20 bg-amber-400/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-200"
                  >
                    {field}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[10px] leading-relaxed text-ink-400">
              Unavailable fields are not filled from external sources. A blank year or venue is a
              documented gap, not an inferred value.
            </p>
          </div>

          {conflicts.title_variants.length > 0 || conflicts.authors_raw_variants.length > 0 ? (
            <div className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/5 p-3">
              <p className="flex items-center gap-1.5 text-[11px] font-semibold text-rose-100">
                <ShieldAlert className="size-3.5" aria-hidden="true" />
                Conflicting source variants
              </p>
              <ul className="mt-1.5 space-y-1 text-[11px] leading-relaxed text-ink-300">
                {conflicts.title_variants.map((variant) => (
                  <li key={`title-${variant}`}>Title: {variant}</li>
                ))}
                {conflicts.authors_raw_variants.map((variant) => (
                  <li key={`authors-${variant}`}>Authors: {variant}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-4">
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Field status</p>
            <ul className="mt-1.5 space-y-1">
              {FIELD_ORDER.filter((field) => record.field_status[field]).map((field) => (
                <li key={field} className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                  <span className="text-ink-400">{humanizeKey(field)}</span>
                  <span className="font-mono text-[10px] text-ink-300">
                    {record.field_status[field]}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="surface p-5" aria-labelledby="publication-sources">
        <h2
          id="publication-sources"
          className="flex items-center gap-2 text-sm font-semibold text-ink-100"
        >
          <FileQuestion className="size-4 text-cyan-300" aria-hidden="true" />
          Source references
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          This record is derived only from the listed source registry entries. No bibliographic
          field is filled from an external database.
        </p>
        <div className="mt-3">
          <SourceReferenceList references={record.source_references} />
        </div>
      </section>

      <QualityBanner quality={quality} title="Publication response quality" />
    </div>
  );
}
