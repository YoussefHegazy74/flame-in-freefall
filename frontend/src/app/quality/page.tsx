"use client";

import { Suspense, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Database,
  Info,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { useDatasetsQuality } from "@/lib/api/hooks";
import type { DatasetQuality, QualityIssue } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { formatCount, formatValue } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, SelectFilter } from "@/components/ui/filter";
import { TD_CLASS, TH_CLASS, TableShell } from "@/components/ui/table-shell";
import {
  QualityStatusBadge,
  ServingStateBadge,
} from "@/components/scientific/state-badge";
import { QualityBanner } from "@/components/scientific/quality-banner";
import { DatasetLimitationsPanel } from "@/components/scientific/dataset-limitations-panel";

const SEVERITIES = ["error", "warning", "info"];

function severityTone(severity: string): "rose" | "amber" | "cyan" | "neutral" {
  if (severity === "error") return "rose";
  if (severity === "warning") return "amber";
  if (severity === "info") return "cyan";
  return "neutral";
}

function severityRank(severity: string): number {
  if (severity === "error") return 0;
  if (severity === "warning") return 1;
  if (severity === "info") return 2;
  return 3;
}

function issueKey(issue: QualityIssue): string {
  return `${issue.severity}|${issue.code}|${issue.message}`;
}

function DetailValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span>—</span>;
  if (typeof value === "object") {
    return (
      <span className="break-all font-mono text-[10px]">
        {JSON.stringify(value)}
      </span>
    );
  }
  return <span>{formatValue(value as string | number | boolean)}</span>;
}

function IssueDetails({ details }: { details?: Record<string, unknown> }) {
  if (!details || Object.keys(details).length === 0) return null;
  return (
    <dl className="mt-2 grid gap-x-4 gap-y-1 text-[10px] sm:grid-cols-2">
      {Object.entries(details).map(([key, value]) => (
        <div key={key} className="min-w-0">
          <dt className="font-mono text-ink-500">{key}</dt>
          <dd className="text-ink-300">
            <DetailValue value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function QualityContent() {
  const { get, setParams, clearParams } = useUrlState();
  const quality = useDatasetsQuality();
  const datasetFilter = get("dataset") ?? "";
  const severityFilter = get("severity") ?? "";
  const query = get("q") ?? "";
  const [searchText, setSearchText] = useState(query);

  const records = useMemo(() => quality.data?.data ?? [], [quality.data]);
  const envelopeQuality = quality.data?.quality;
  const selectedDataset = records.find((record) => record.dataset_id === datasetFilter);

  const uniqueIssues = useMemo(() => {
    const map = new Map<
      string,
      {
        issue: QualityIssue;
        datasets: DatasetQuality[];
      }
    >();
    for (const record of records) {
      for (const issue of record.issues) {
        const key = issueKey(issue);
        const existing = map.get(key);
        if (existing) {
          existing.datasets.push(record);
        } else {
          map.set(key, { issue, datasets: [record] });
        }
      }
    }
    return Array.from(map.values()).sort(
      (a, b) =>
        severityRank(a.issue.severity) - severityRank(b.issue.severity) ||
        a.issue.code.localeCompare(b.issue.code),
    );
  }, [records]);

  const filteredIssues = useMemo(() => {
    const text = query.trim().toLowerCase();
    return uniqueIssues.filter(({ issue, datasets }) => {
      if (severityFilter && issue.severity !== severityFilter) return false;
      if (
        datasetFilter &&
        !datasets.some((record) => record.dataset_id === datasetFilter)
      ) {
        return false;
      }
      if (!text) return true;
      return (
        issue.code.toLowerCase().includes(text) ||
        issue.message.toLowerCase().includes(text) ||
        datasets.some((record) =>
          `${record.dataset_id} ${record.display_name}`.toLowerCase().includes(text),
        )
      );
    });
  }, [uniqueIssues, severityFilter, datasetFilter, query]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setParams({ q: searchText.trim() || null });
  };

  const counts = useMemo(() => {
    const result = { error: 0, warning: 0, info: 0 };
    for (const { issue } of uniqueIssues) {
      if (issue.severity in result) {
        result[issue.severity as keyof typeof result] += 1;
      }
    }
    return result;
  }, [uniqueIssues]);

  const summary = records[0]?.report_summary;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analysis · Data quality"
        title="Quality center"
        description={
          <>
            Registry-wide warnings, per-dataset serving states, and the complete issue catalogue
            returned by the API. Missing values are not zero, sentinels are not measurements, and
            no warning is suppressed to simplify the page.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(records.length)} datasets</Badge>
            <Badge tone="amber">{formatCount(uniqueIssues.length)} unique issues</Badge>
            <Badge tone="rose">{formatCount(counts.error)} errors</Badge>
            <Badge tone="neutral">Registry snapshot {quality.data?.meta.registry_snapshot ?? "—"}</Badge>
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3.5">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-amber-100">
              The report summary is registry-wide, not per dataset.
            </p>
            <p className="mt-1">
              The API returns the same <span className="mono">report_summary</span> object on every
              dataset quality record. It describes the validation report across the registry. The
              per-dataset <span className="mono">quality_status</span>, serving states, and issue
              list are dataset-level and are shown separately below.
            </p>
          </div>
        </div>
      </section>

      {quality.isPending ? (
        <LoadingState label="Loading registry quality records…" rows={5} />
      ) : quality.isError ? (
        <ErrorState
          error={quality.error}
          title="Dataset quality records could not be loaded"
          onRetry={() => quality.refetch()}
        />
      ) : records.length === 0 ? (
        <EmptyState
          title="No quality records were returned"
          description="An empty quality list is not evidence that the data are clean. The API returned no records."
          icon={<ShieldCheck className="size-6" aria-hidden="true" />}
        />
      ) : (
        <>
          {envelopeQuality ? (
            <QualityBanner
              quality={envelopeQuality}
              title="Registry-wide quality response"
            />
          ) : null}

          {summary ? (
            <section className="surface p-5" aria-labelledby="report-summary">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 id="report-summary" className="text-sm font-semibold text-ink-100">
                    Registry validation report summary
                  </h2>
                  <p className="mt-1 text-xs leading-relaxed text-ink-400">
                    Identical on all {records.length} dataset records. These are registry totals, not
                    the row count or issue count of the selected dataset.
                  </p>
                </div>
                <Badge tone="outline">registry-wide</Badge>
              </div>
              <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ["Tables", summary.tables],
                  ["Total rows", summary.total_rows],
                  ["Point rows", summary.point_rows],
                  ["Issues", summary.issues],
                  ["Errors", summary.errors],
                  ["Warnings", summary.warnings],
                ].map(([label, value]) => (
                  <div key={String(label)}>
                    <dt className="text-ink-500">{label}</dt>
                    <dd className="font-mono text-sm text-ink-200">
                      {formatCount(Number(value))}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          <section aria-labelledby="dataset-quality-table">
            <div className="mb-3">
              <h2 id="dataset-quality-table" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
                <Database className="size-4 text-cyan-300" aria-hidden="true" />
                Dataset quality and serving states
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-ink-400">
                Quality status describes validation. Serving states describe permitted uses. They are
                related but not interchangeable: a partial dataset can still be available for
                exploration while blocked for time series.
              </p>
            </div>
            <TableShell caption="Per-dataset quality status and serving states for exploration, quantitative comparison, time series, and provenance">
              <thead>
                <tr>
                  <th scope="col" className={TH_CLASS}>Dataset</th>
                  <th scope="col" className={TH_CLASS}>Quality</th>
                  <th scope="col" className={TH_CLASS}>Base state</th>
                  <th scope="col" className={TH_CLASS}>Exploration</th>
                  <th scope="col" className={TH_CLASS}>Quantitative comparison</th>
                  <th scope="col" className={TH_CLASS}>Time series</th>
                  <th scope="col" className={TH_CLASS}>Provenance</th>
                  <th scope="col" className={TH_CLASS}>Issues</th>
                  <th scope="col" className={TH_CLASS}><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr
                    key={record.dataset_id}
                    className={
                      record.dataset_id === datasetFilter
                        ? "bg-cyan-400/5"
                        : "hover:bg-navy-800/35"
                    }
                  >
                    <td className={TD_CLASS}>
                      <p className="font-medium text-ink-100">{record.display_name}</p>
                      <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">
                        {record.dataset_id}
                      </p>
                    </td>
                    <td className={TD_CLASS}>
                      <QualityStatusBadge status={record.quality_status} />
                    </td>
                    <td className={TD_CLASS}>
                      <ServingStateBadge state={record.base_state} />
                    </td>
                    <td className={TD_CLASS}>
                      <ServingStateBadge state={record.use_states.exploration} showIcon={false} />
                    </td>
                    <td className={TD_CLASS}>
                      <ServingStateBadge
                        state={record.use_states.quantitative_comparison}
                        showIcon={false}
                      />
                    </td>
                    <td className={TD_CLASS}>
                      <ServingStateBadge state={record.use_states.time_series} showIcon={false} />
                    </td>
                    <td className={TD_CLASS}>
                      <ServingStateBadge state={record.use_states.provenance} showIcon={false} />
                    </td>
                    <td className={`${TD_CLASS} font-mono text-ink-300`}>
                      {formatCount(record.issues.length)}
                    </td>
                    <td className={TD_CLASS}>
                      <div className="flex flex-col gap-1">
                        <Link
                          href={`/datasets/${encodeURIComponent(record.dataset_id)}`}
                          className="whitespace-nowrap text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                        >
                          Dataset
                        </Link>
                        <button
                          type="button"
                          onClick={() =>
                            setParams({
                              dataset:
                                record.dataset_id === datasetFilter
                                  ? null
                                  : record.dataset_id,
                            })
                          }
                          className="whitespace-nowrap text-left text-[11px] font-medium text-ink-400 hover:text-cyan-200 focus-ring"
                        >
                          {record.dataset_id === datasetFilter
                            ? "Clear focus"
                            : "Focus issues"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
          </section>

          <section aria-labelledby="issue-catalogue">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 id="issue-catalogue" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
                  <ShieldAlert className="size-4 text-amber-300" aria-hidden="true" />
                  Issue catalogue
                </h2>
                <p className="mt-1 text-xs leading-relaxed text-ink-400">
                  Duplicate issue records are collapsed once and annotated with every dataset that
                  reports them. The per-dataset panel below preserves the un-collapsed list when a
                  dataset is focused.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="rose">{formatCount(counts.error)} errors</Badge>
                <Badge tone="amber">{formatCount(counts.warning)} warnings</Badge>
                <Badge tone="cyan">{formatCount(counts.info)} info</Badge>
              </div>
            </div>

            <FilterBar
              label="Quality issue filters"
              actions={
                <FilterActions
                  onClear={() => {
                    setSearchText("");
                    clearParams();
                  }}
                  resultLabel={`${formatCount(filteredIssues.length)} of ${formatCount(uniqueIssues.length)} unique issues shown`}
                />
              }
            >
              <SelectFilter
                id="quality-dataset"
                label="Dataset scope"
                value={datasetFilter}
                onChange={(value) => setParams({ dataset: value || null })}
                options={records.map((record) => ({
                  value: record.dataset_id,
                  label: record.display_name,
                }))}
                placeholder="All datasets"
                hint="Filters issues to those reported by one dataset."
              />
              <SelectFilter
                id="quality-severity"
                label="Severity"
                value={severityFilter}
                onChange={(value) => setParams({ severity: value || null })}
                options={SEVERITIES.map((severity) => ({
                  value: severity,
                  label: severity,
                }))}
                placeholder="All severities"
              />
              <form onSubmit={submitSearch} className="sm:col-span-2" role="search">
                <label
                  htmlFor="quality-search"
                  className="mb-1 block text-[11px] font-medium text-ink-300"
                >
                  Search issue code, message, or dataset
                </label>
                <div className="flex gap-2">
                  <div className="relative min-w-0 flex-1">
                    <Search
                      className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
                      aria-hidden="true"
                    />
                    <input
                      id="quality-search"
                      type="search"
                      value={searchText}
                      onChange={(event) => setSearchText(event.target.value)}
                      placeholder="e.g. sentinel, oxygen, PSI-26"
                      className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 pl-8 pr-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
                    />
                  </div>
                  <button type="submit" className={buttonStyles({ variant: "primary", size: "sm" })}>
                    Search
                  </button>
                  {query ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchText("");
                        setParams({ q: null });
                      }}
                      className={buttonStyles({ variant: "ghost", size: "sm" })}
                      aria-label="Clear quality search"
                    >
                      <X className="size-3.5" aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              </form>
            </FilterBar>

            {filteredIssues.length === 0 ? (
              <div className="mt-3">
                <EmptyState
                  title="No issue matches these filters"
                  description="The full issue catalogue is unchanged. Clear the dataset, severity, or search filter to see all issues."
                  icon={<Search className="size-6" aria-hidden="true" />}
                  action={
                    <button
                      type="button"
                      className={buttonStyles()}
                      onClick={() => {
                        setSearchText("");
                        clearParams();
                      }}
                    >
                      Clear filters
                    </button>
                  }
                />
              </div>
            ) : (
              <ul className="mt-3 space-y-3">
                {filteredIssues.map(({ issue, datasets }) => (
                  <li
                    key={issueKey(issue)}
                    className="surface-flat p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={severityTone(issue.severity)}>{issue.severity}</Badge>
                      <span className="font-mono text-[11px] text-ink-200">{issue.code}</span>
                      <span className="text-[10px] text-ink-500">
                        reported by {datasets.length} dataset{datasets.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-ink-300">{issue.message}</p>
                    <IssueDetails details={issue.details} />
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {datasets.map((record) => (
                        <button
                          key={record.dataset_id}
                          type="button"
                          onClick={() => setParams({ dataset: record.dataset_id })}
                          className="rounded border border-navy-600 bg-navy-800/70 px-1.5 py-0.5 font-mono text-[10px] text-ink-400 hover:text-cyan-200 focus-ring"
                        >
                          {record.dataset_id}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {selectedDataset ? (
            <section className="surface p-5" aria-labelledby="focused-dataset">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 id="focused-dataset" className="text-sm font-semibold text-ink-100">
                    Focused dataset quality: {selectedDataset.display_name}
                  </h2>
                  <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
                    {selectedDataset.dataset_id} · {selectedDataset.accession}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <QualityStatusBadge status={selectedDataset.quality_status} />
                  <ServingStateBadge state={selectedDataset.base_state} />
                  <button
                    type="button"
                    onClick={() => setParams({ dataset: null })}
                    className={buttonStyles({ variant: "ghost", size: "sm" })}
                  >
                    Clear focus
                  </button>
                </div>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-ink-400">
                This is the un-collapsed issue list returned for this dataset. It may repeat
                registry-wide issues that also appear on other datasets.
              </p>
              <ul className="mt-3 space-y-2">
                {selectedDataset.issues.map((issue, index) => (
                  <li
                    key={`${issueKey(issue)}-${index}`}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={severityTone(issue.severity)}>{issue.severity}</Badge>
                      <span className="font-mono text-[11px] text-ink-200">{issue.code}</span>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-ink-300">{issue.message}</p>
                    <IssueDetails details={issue.details} />
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex flex-wrap gap-3">
                <Link
                  href={`/datasets/${encodeURIComponent(selectedDataset.dataset_id)}`}
                  className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                >
                  Open dataset record
                </Link>
                <Link
                  href={`/provenance?accession=${encodeURIComponent(selectedDataset.accession)}`}
                  className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                >
                  Resolve provenance
                </Link>
              </div>
            </section>
          ) : null}

          {selectedDataset ? (
            <DatasetLimitationsPanel
              datasetId={selectedDataset.dataset_id}
              compact
            />
          ) : null}

          <section className="surface p-5" aria-labelledby="quality-reading">
            <h2 id="quality-reading" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
              <Info className="size-4 text-cyan-300" aria-hidden="true" />
              How to read this page
            </h2>
            <div className="mt-3 grid gap-3 text-xs leading-relaxed text-ink-300 md:grid-cols-2">
              <p className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                A warning does not mean a value is wrong. It means a documented limitation applies
                and must remain visible when the value is used.
              </p>
              <p className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                A blocked serving state is a backend decision. This page never overrides it or
                suggests a workaround.
              </p>
              <p className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                Missing values and sentinels are preserved as missing. They are never converted to
                zero to make a chart or summary look complete.
              </p>
              <p className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                Issue counts describe records returned by the API. They are not a measure of data
                quality beyond the documented checks.
              </p>
            </div>
            <Disclosure summary="Show quality flags as returned" className="mt-3">
              <ul className="flex flex-wrap gap-1.5" aria-label="Registry quality flags">
                {(envelopeQuality?.flags ?? []).map((flag) => (
                  <li
                    key={flag}
                    className="rounded border border-navy-600 bg-navy-800/70 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
                  >
                    {flag}
                  </li>
                ))}
              </ul>
            </Disclosure>
          </section>
        </>
      )}
    </div>
  );
}

export default function QualityPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading quality center…" rows={5} />}>
      <QualityContent />
    </Suspense>
  );
}
