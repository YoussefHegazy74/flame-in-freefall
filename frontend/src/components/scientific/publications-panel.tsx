"use client";

import Link from "next/link";
import { ArrowUpRight, BookOpen, ExternalLink, FileQuestion, ShieldCheck } from "lucide-react";
import type { Publication } from "@/lib/api/types";
import { usePublications } from "@/lib/api/hooks";
import { formatCount } from "@/lib/format";
import { safeExternalUrl } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

export function PublicationCard({
  publication,
  showAbstract = false,
}: {
  publication: Publication;
  showAbstract?: boolean;
}) {
  const doiUrl = safeExternalUrl(publication.doi_url);
  const hasConflicts =
    publication.verification.conflicts.title_variants.length > 0 ||
    publication.verification.conflicts.authors_raw_variants.length > 0;

  return (
    <article className="surface-flat p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold leading-snug text-ink-100">
            <Link
              href={`/publications/${encodeURIComponent(publication.publication_id)}`}
              className="hover:text-cyan-200 focus-ring"
            >
              {publication.title}
            </Link>
          </h3>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
            {publication.authors.length > 0
              ? publication.authors.join(", ")
              : publication.authors_raw || "Authors not available"}
          </p>
        </div>
        <Badge tone={publication.doi ? "emerald" : "amber"}>
          {publication.doi ? "DOI verified" : "No DOI"}
        </Badge>
      </div>

      <dl className="mt-3 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2">
        <div>
          <dt className="text-ink-500">DOI</dt>
          <dd className="break-all">
            {publication.doi ? (
              doiUrl ? (
                <a
                  href={doiUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-cyan-300 hover:text-cyan-200 focus-ring"
                >
                  {publication.doi}
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              ) : (
                <span className="font-mono text-ink-300">{publication.doi}</span>
              )
            ) : (
              <span className="text-ink-400">not available in the source registry</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-ink-500">Year and venue</dt>
          <dd className="text-ink-400">
            {publication.year ?? "year unavailable"} ·{" "}
            {publication.venue ?? "venue unavailable"}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-ink-500">Related investigations</dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {publication.related_investigations.length === 0 ? (
              <span className="text-ink-400">none recorded</span>
            ) : (
              publication.related_investigations.map((investigation) => (
                <Link
                  key={investigation.accession}
                  href={`/investigations/${encodeURIComponent(investigation.accession)}`}
                  className="rounded border border-navy-600 bg-navy-800/70 px-1.5 py-0.5 font-mono text-[10px] text-cyan-200 hover:border-cyan-400/50 focus-ring"
                  title={investigation.title}
                >
                  {investigation.acronym || investigation.accession}
                </Link>
              ))
            )}
          </dd>
        </div>
      </dl>

      {hasConflicts ? (
        <div className="mt-3 rounded-lg border border-amber-400/20 bg-warning-soft p-2.5 text-[11px] leading-relaxed text-amber-100">
          The registry contains conflicting metadata variants. They are preserved below rather than
          silently resolved.
          {publication.verification.conflicts.title_variants.length > 0 ? (
            <ul className="mt-1 list-disc pl-4">
              {publication.verification.conflicts.title_variants.map((variant) => (
                <li key={variant}>{variant}</li>
              ))}
            </ul>
          ) : null}
          {publication.verification.conflicts.authors_raw_variants.length > 0 ? (
            <ul className="mt-1 list-disc pl-4">
              {publication.verification.conflicts.authors_raw_variants.map((variant) => (
                <li key={variant}>{variant}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {showAbstract ? (
        <div className="mt-3 grid gap-3 text-[11px] sm:grid-cols-2">
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <p className="flex items-center gap-1.5 text-ink-300">
              <ShieldCheck className="size-3.5 text-emerald-300" aria-hidden="true" />
              Verification
            </p>
            <p className="mt-1 font-mono text-[10px] text-ink-400">
              {publication.verification.status} · snapshot{" "}
              {publication.verification.snapshot_date}
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
              Verified fields: {publication.verification.verified_fields.join(", ") || "none"}
            </p>
          </div>
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <p className="flex items-center gap-1.5 text-ink-300">
              <FileQuestion className="size-3.5 text-amber-300" aria-hidden="true" />
              Unavailable fields
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
              {publication.verification.unavailable_fields.length > 0
                ? publication.verification.unavailable_fields.join(", ")
                : "none"}
            </p>
            <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
              Missing bibliographic data is returned as unavailable. It is never fabricated.
            </p>
          </div>
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-navy-700/60 pt-2.5">
        <Link
          href={`/publications/${encodeURIComponent(publication.publication_id)}`}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
        >
          Publication record
          <ArrowUpRight className="size-3" aria-hidden="true" />
        </Link>
        <span className="break-all font-mono text-[10px] text-ink-500">
          {publication.publication_id}
        </span>
      </div>
    </article>
  );
}

function PublicationPanelState({
  query,
  emptyTitle,
  emptyDescription,
}: {
  query: ReturnType<typeof usePublications>;
  emptyTitle: string;
  emptyDescription: string;
}) {
  if (query.isPending) {
    return <LoadingState label="Loading publications…" rows={2} />;
  }
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        title="Publications could not be loaded"
        onRetry={() => query.refetch()}
      />
    );
  }
  const publications = query.data?.data.publications ?? [];
  if (publications.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        icon={<BookOpen className="size-6" aria-hidden="true" />}
      />
    );
  }
  return (
    <ul className="space-y-3">
      {publications.map((publication) => (
        <li key={publication.publication_id}>
          <PublicationCard publication={publication} />
        </li>
      ))}
    </ul>
  );
}

export function DatasetPublicationsPanel({ datasetId }: { datasetId: string }) {
  const publications = usePublications({ dataset_id: datasetId, limit: 6 });
  const summary = publications.data?.data.summary;
  const total = publications.data?.data.page.total ?? 0;

  return (
    <section className="surface p-5" aria-labelledby={`dataset-publications-${datasetId}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id={`dataset-publications-${datasetId}`}
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
            Related publications
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Publications registered for this dataset&apos;s investigation. Title, authors, DOI, and
            status come from the NASA PSI registry. Year and venue are not present in the source and
            are returned as unavailable.
          </p>
        </div>
        {summary ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="cyan">{formatCount(total)} publications</Badge>
            <Badge tone="emerald">{formatCount(summary.with_doi)} with DOI</Badge>
            {summary.without_doi > 0 ? (
              <Badge tone="amber">{formatCount(summary.without_doi)} without DOI</Badge>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        <PublicationPanelState
          query={publications}
          emptyTitle="No publication is registered for this dataset"
          emptyDescription="An empty list means the source registry has no publication record linked to this investigation. It does not mean the investigation has no associated literature."
        />
      </div>

      {total > 6 ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-navy-700/60 pt-3">
          <Link
            href={`/publications?dataset_id=${encodeURIComponent(datasetId)}`}
            className={buttonStyles({ size: "sm" })}
          >
            View all {formatCount(total)} publications
            <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      ) : null}
    </section>
  );
}

export function InvestigationPublicationsPanel({ accession }: { accession: string }) {
  const publications = usePublications({ accession, limit: 6 });
  const total = publications.data?.data.page.total ?? 0;

  return (
    <section className="surface p-5" aria-labelledby={`investigation-publications-${accession}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id={`investigation-publications-${accession}`}
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
            Publications
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Registry-linked publications for {accession}. Bibliographic gaps are shown explicitly
            and are not inferred from external sources.
          </p>
        </div>
        {total > 0 ? <Badge tone="cyan">{formatCount(total)} records</Badge> : null}
      </div>

      <div className="mt-4">
        <PublicationPanelState
          query={publications}
          emptyTitle="No publication is registered for this investigation"
          emptyDescription="The source registry returned no linked publication records. This is not evidence that no literature exists."
        />
      </div>

      {total > 6 ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-navy-700/60 pt-3">
          <Link
            href={`/publications?accession=${encodeURIComponent(accession)}`}
            className={buttonStyles({ size: "sm" })}
          >
            View all {formatCount(total)} publications
            <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      ) : null}
    </section>
  );
}
