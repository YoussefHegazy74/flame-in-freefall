"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CalendarDays,
  Database,
  ExternalLink,
  FileText,
  Layers,
  ShieldAlert,
} from "lucide-react";
import { useInvestigation } from "@/lib/api/hooks";
import { formatBytes, formatCount, formatDate } from "@/lib/format";
import { roleLabel } from "@/lib/labels";
import { safeExternalUrl } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { DatasetCard } from "@/components/scientific/dataset-card";
import { InvestigationPublicationsPanel } from "@/components/scientific/publications-panel";

export default function InvestigationDetailPage() {
  const params = useParams<{ accession: string }>();
  const accession = decodeURIComponent(params.accession ?? "");
  const investigation = useInvestigation(accession);

  if (investigation.isPending) {
    return <LoadingState label={`Loading ${accession} from the investigation catalog…`} rows={5} />;
  }

  if (investigation.isError) {
    return (
      <ErrorState
        error={investigation.error}
        title={`Investigation ${accession} could not be loaded`}
        onRetry={() => investigation.refetch()}
      >
        <Link href="/investigations" className={buttonStyles({ size: "sm", className: "mt-3" })}>
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to catalog
        </Link>
      </ErrorState>
    );
  }

  const record = investigation.data.data;
  const doiUrl = record.doi ? safeExternalUrl(`https://doi.org/${record.doi}`) : undefined;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={`Investigation ${record.accession}`}
        title={record.title}
        description={
          <span>
            <span className="font-medium text-cyan-300">{record.acronym}</span> ·{" "}
            {record.sub_research_area}
          </span>
        }
        actions={
          <>
            <Link href="/investigations" className={buttonStyles()}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Catalog
            </Link>
            {doiUrl ? (
              <a href={doiUrl} target="_blank" rel="noreferrer" className={buttonStyles()}>
                <ExternalLink className="size-4" aria-hidden="true" />
                DOI record
              </a>
            ) : null}
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{roleLabel(record.mvp_role)}</Badge>
            <Badge tone={record.archive_status === "available" ? "emerald" : "amber"}>
              Archive: {record.archive_status}
            </Badge>
            <Badge tone={record.public ? "emerald" : "neutral"}>
              {record.public ? "Public" : "Not public"}
            </Badge>
            {record.restricted ? <Badge tone="rose">Restricted</Badge> : null}
            <Badge tone="outline">Registry version {record.version}</Badge>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <section className="surface p-5" aria-labelledby="rationale-heading">
          <h2 id="rationale-heading" className="text-sm font-semibold text-ink-100">
            Why this investigation is in the curated set
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-300">{record.rationale}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="surface-inset p-3">
              <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Research area</p>
              <p className="mt-1 text-xs text-ink-200">{record.research_area}</p>
              <p className="text-[11px] text-ink-400">{record.sub_research_area}</p>
            </div>
            <div className="surface-inset p-3">
              <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Project type</p>
              <p className="mt-1 text-xs text-ink-200">{record.project_type}</p>
            </div>
            <div className="surface-inset p-3">
              <p className="flex items-center gap-1 text-[10px] uppercase tracking-[0.08em] text-ink-500">
                <CalendarDays className="size-3" aria-hidden="true" />
                Investigation window
              </p>
              <p className="mt-1 text-xs text-ink-200">
                {formatDate(record.start_date)} → {formatDate(record.end_date)}
              </p>
            </div>
            <div className="surface-inset p-3">
              <p className="flex items-center gap-1 text-[10px] uppercase tracking-[0.08em] text-ink-500">
                <FileText className="size-3" aria-hidden="true" />
                Registered archive
              </p>
              <p className="mt-1 text-xs text-ink-200">
                {formatCount(record.file_count)} files · {formatBytes(record.registered_total_bytes)}
              </p>
              <p className="text-[11px] text-ink-400">
                {formatCount(record.removed_file_count)} removed
              </p>
            </div>
          </div>
        </section>

        <section className="surface p-5" aria-labelledby="table-facts">
          <h2 id="table-facts" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <Layers className="size-4 text-cyan-300" aria-hidden="true" />
            Experimental tables
          </h2>
          <dl className="mt-3 space-y-3 text-xs">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-ink-400">Experimental table count</dt>
              <dd className="font-mono text-ink-200">{formatCount(record.experimental_table_count)}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-ink-400">Experimental table bytes</dt>
              <dd className="font-mono text-ink-200">{formatBytes(record.experimental_table_bytes)}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-ink-400">Experimental-table-only count</dt>
              <dd className="font-mono text-ink-200">{formatCount(record.experimental_table_only_count)}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-ink-400">DOI</dt>
              <dd className="font-mono text-[11px] text-ink-200">{record.doi ?? "not stated"}</dd>
            </div>
          </dl>
          <p className="mt-4 rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5 text-[11px] leading-relaxed text-ink-400">
            Raw NASA archives are not served through this API. File counts describe the registry,
            not files available for download here.
          </p>
        </section>
      </div>

      <section className="surface p-5" aria-labelledby="limitations-heading">
        <div className="flex items-start gap-3">
          <span className="rounded-xl border border-amber-400/25 bg-warning-soft p-2 text-amber-300">
            <ShieldAlert className="size-5" aria-hidden="true" />
          </span>
          <div>
            <h2 id="limitations-heading" className="text-sm font-semibold text-ink-100">
              Documented limitations
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              These limitations are part of the curated record and remain visible wherever this
              investigation&apos;s data is used.
            </p>
            <ul className="mt-3 space-y-2">
              {record.limitations.map((limitation) => (
                <li
                  key={limitation}
                  className="rounded-lg border border-amber-400/15 bg-warning-soft p-2.5 text-xs leading-relaxed text-ink-300"
                >
                  {limitation}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <InvestigationPublicationsPanel accession={record.accession} />

      <section aria-labelledby="curated-datasets">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="curated-datasets" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
              <Database className="size-4 text-cyan-300" aria-hidden="true" />
              Curated datasets from this investigation
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              {record.curated_datasets.length} dataset
              {record.curated_datasets.length === 1 ? "" : "s"} with serving states from the
              registry.
            </p>
          </div>
          <Link href="/datasets" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            All datasets
          </Link>
        </div>
        {record.curated_datasets.length === 0 ? (
          <div className="surface p-5 text-sm text-ink-300">
            This investigation has no curated dataset in the MVP registry. Its record remains
            available for context only.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {record.curated_datasets.map((dataset) => (
              <DatasetCard key={dataset.dataset_id} dataset={dataset} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
