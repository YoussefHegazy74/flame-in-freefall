"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Database,
  ExternalLink,
  FileSearch,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useDataset } from "@/lib/api/hooks";
import { API_BASE_URL } from "@/lib/api/client";
import type { ServingUse } from "@/lib/api/types";
import { formatCount } from "@/lib/format";
import { familyLabel, labelForUse } from "@/lib/labels";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { MeasurementTable } from "@/components/scientific/measurement-table";
import { ServingStateBadge } from "@/components/scientific/state-badge";
import { SourceReferenceList } from "@/components/scientific/provenance";
import { ProvenanceLink } from "@/components/scientific/record-fields";

const USES: ServingUse[] = ["exploration", "quantitative_comparison", "time_series", "provenance"];

export default function DatasetDetailPage() {
  const params = useParams<{ datasetId: string }>();
  const datasetId = decodeURIComponent(params.datasetId ?? "");
  const dataset = useDataset(datasetId);

  if (dataset.isPending) {
    return <LoadingState label={`Loading dataset ${datasetId}…`} rows={5} />;
  }

  if (dataset.isError) {
    return (
      <ErrorState
        error={dataset.error}
        title={`Dataset ${datasetId} could not be loaded`}
        onRetry={() => dataset.refetch()}
      >
        <Link href="/datasets" className={buttonStyles({ size: "sm", className: "mt-3" })}>
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to datasets
        </Link>
      </ErrorState>
    );
  }

  const record = dataset.data.data;
  const nasaFiles = record.source_references.filter((reference) => reference.kind === "nasa_psi_file");

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={`${record.accession} · ${familyLabel(record.experiment_family)}`}
        title={record.display_name}
        description={
          <>
            Curated dataset <span className="mono text-ink-200">{record.dataset_id}</span>. Serving
            states, measurement units, and restrictions below are returned by the backend and are
            not recalculated in the browser.
          </>
        }
        actions={
          <>
            <Link href="/datasets" className={buttonStyles()}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Datasets
            </Link>
            <Link
              href={`/quality?dataset=${encodeURIComponent(record.dataset_id)}`}
              className={buttonStyles()}
            >
              <ShieldCheck className="size-4" aria-hidden="true" />
              Dataset quality
            </Link>
          </>
        }
        meta={
          <>
            <ServingStateBadge state={record.base_state} />
            <Badge tone="cyan">{formatCount(record.measurement_count)} measurements</Badge>
            <Badge tone="neutral">Download: {record.download_status.replace(/_/g, " ")}</Badge>
            <Badge tone="neutral">Files: {record.measurement_file_status.replace(/_/g, " ")}</Badge>
            <Badge tone="outline">{record.access_scope.replace(/_/g, " ")}</Badge>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.35fr]">
        <section className="surface p-5" aria-labelledby="dataset-scope">
          <h2 id="dataset-scope" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <Database className="size-4 text-cyan-300" aria-hidden="true" />
            Scope and canonical tables
          </h2>
          <dl className="mt-3 space-y-2.5 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Experiment family</dt>
              <dd className="text-ink-200">{familyLabel(record.experiment_family)}</dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Access scope</dt>
              <dd className="mono text-[11px] text-ink-200">{record.access_scope}</dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Download status</dt>
              <dd className="mono text-[11px] text-ink-200">{record.download_status}</dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-ink-400">Measurement file status</dt>
              <dd className="mono text-[11px] text-ink-200">{record.measurement_file_status}</dd>
            </div>
          </dl>
          <div className="mt-4">
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Canonical tables</p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {record.canonical_tables.map((table) => (
                <li
                  key={table}
                  className="rounded border border-navy-600 bg-navy-800/70 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
                >
                  {table}
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-4 rounded-lg border border-cyan-400/15 bg-cyan-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
            The API serves named queries only. This page does not expose raw files, arbitrary SQL,
            or browser-side transformations.
          </div>
        </section>

        <section className="surface p-5" aria-labelledby="dataset-reasons">
          <h2 id="dataset-reasons" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <ShieldAlert className="size-4 text-amber-300" aria-hidden="true" />
            Why the registry assigns these states
          </h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
                Documented reasons
              </p>
              <ul className="mt-1.5 space-y-2">
                {record.reasons.length === 0 ? (
                  <li className="text-[11px] text-ink-400">No dataset-level reasons were returned.</li>
                ) : (
                  record.reasons.map((reason) => (
                    <li key={`${reason.code}-${reason.message}`} className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                      <span className="mono text-[10px] text-ink-500">{reason.code}</span>
                      <span className="mt-0.5 block text-[11px] leading-relaxed text-ink-300">
                        {reason.message}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
                Restrictions
              </p>
              <ul className="mt-1.5 space-y-2">
                {record.restrictions.length === 0 ? (
                  <li className="text-[11px] text-ink-400">No dataset-level restrictions were returned.</li>
                ) : (
                  record.restrictions.map((restriction) => (
                    <li key={restriction} className="flex items-start gap-1.5 rounded-lg border border-amber-400/15 bg-amber-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
                      <AlertTriangle className="mt-0.5 size-3 shrink-0 text-amber-300" aria-hidden="true" />
                      {restriction}
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        </section>
      </div>

      <section aria-labelledby="serving-decisions">
        <div className="mb-3">
          <h2 id="serving-decisions" className="text-sm font-semibold text-ink-100">
            Serving decisions by use
          </h2>
          <p className="mt-1 text-xs text-ink-400">
            The same dataset can be available for one use and blocked for another. Every reason and
            restriction is rendered below without collapsing it into a single badge.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {USES.map((use) => {
            const decision = record.serving[use];
            if (!decision) return null;
            return (
              <article key={use} className="surface p-4" aria-label={`${labelForUse(use)} serving decision`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-ink-100">{labelForUse(use)}</h3>
                  <ServingStateBadge state={decision.state} />
                </div>
                <p className="mt-1 font-mono text-[10px] text-ink-500">
                  use: {decision.use} · resource: {decision.resource_type}
                </p>
                <div className="mt-3 space-y-2">
                  {decision.reasons.map((reason) => (
                    <div key={`${reason.code}-${reason.message}`} className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                      <span className="mono text-[10px] text-ink-500">{reason.code}</span>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-ink-300">{reason.message}</p>
                    </div>
                  ))}
                  {decision.restrictions.length > 0 ? (
                    <ul className="space-y-1.5">
                      {decision.restrictions.map((restriction) => (
                        <li key={restriction} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-200">
                          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                          {restriction}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="dataset-measurements">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="dataset-measurements" className="text-sm font-semibold text-ink-100">
              Registered measurements
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              Units, unit status, value kinds, comparison states, and restrictions are shown exactly
              as registered.
            </p>
          </div>
          {record.measurements[0] ? (
            <Link
              href={`/compare?left=${encodeURIComponent(record.measurements[0].measurement_id)}`}
              className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
            >
              Open comparison studio
            </Link>
          ) : null}
        </div>
        {record.measurements.length === 0 ? (
          <div className="surface p-5 text-sm text-ink-300">
            No measurements are registered for this dataset. An empty list is not zero measurements
            and does not imply availability.
          </div>
        ) : (
          <MeasurementTable measurements={record.measurements} />
        )}
      </section>

      <section className="surface p-5" aria-labelledby="dataset-sources">
        <h2 id="dataset-sources" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <FileSearch className="size-4 text-cyan-300" aria-hidden="true" />
          Source references
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          Checksums identify the exact NASA source files used by the registry. Provenance lookup is
          available for each file and row.
        </p>
        <div className="mt-3">
          <SourceReferenceList references={record.source_references} />
        </div>
        {nasaFiles.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-3">
            {nasaFiles.slice(0, 3).map((reference) => (
              <ProvenanceLink
                key={`${reference.accession}-${reference.file_name}`}
                accession={reference.accession ?? record.accession}
                file={reference.file_name ?? ""}
                label="Resolve file provenance"
              />
            ))}
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-navy-700/60 pt-3">
          <a
            href={`${API_BASE_URL}/datasets/${encodeURIComponent(record.dataset_id)}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-ink-400 hover:text-cyan-300 focus-ring"
            title="Open the raw JSON response from the configured API base"
          >
            API record path
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
          <span className="text-[10px] text-ink-500">
            Full JSON is available from the FastAPI reference, not hardcoded in this page.
          </span>
        </div>
      </section>
    </div>
  );
}
