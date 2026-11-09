"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Cloud,
  Database,
  Droplets,
  FlaskConical,
  Flame,
  GitCompare,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { useDatasets, useInvestigations, useMeta } from "@/lib/api/hooks";
import type { ServingState } from "@/lib/api/types";
import { formatCount } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { MetricCard } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { DatasetCard } from "@/components/scientific/dataset-card";
import { InvestigationCard } from "@/components/scientific/investigation-card";
import { ServingStateBadge } from "@/components/scientific/state-badge";

const EXPLORERS = [
  {
    href: "/experiments/gas-flame",
    title: "Gas-flame tests",
    description: "PSI-10 and PSI-159 summary rows with oxygen, pressure, and computed-field labels.",
    icon: Flame,
    accent: "text-ember-300",
  },
  {
    href: "/telemetry",
    title: "SAFFIRE-III telemetry",
    description: "Five separate PSI-100 runs. Choose one run and its channels; runs are never concatenated.",
    icon: Activity,
    accent: "text-cyan-300",
  },
  {
    href: "/smoke",
    title: "SAME-R smoke",
    description: "PSI-101 HKP runs with elapsed-time channels and preserved sentinel gaps.",
    icon: Cloud,
    accent: "text-violet-400",
  },
  {
    href: "/experiments/materials",
    title: "Material matrices",
    description: "PSI-25 and PSI-26 as-run records. Free-text material labels are not normalized.",
    icon: FlaskConical,
    accent: "text-emerald-300",
  },
  {
    href: "/experiments/droplets",
    title: "Droplet tests",
    description: "PSI-69 FLEX summaries. Burning rate stays labeled as mm, not converted to mm/s.",
    icon: Droplets,
    accent: "text-amber-300",
  },
  {
    href: "/compare",
    title: "Comparison Studio",
    description: "Backend-approved comparisons only. Blocked pairs stay blocked; no shared chart is invented.",
    icon: GitCompare,
    accent: "text-cyan-300",
  },
];

const LIMITATIONS = [
  "PSI-98 has no served telemetry series. The API returns 404 for that run rather than fabricating a series.",
  "PSI-26 headers say percent while observed values are near 0.22. Values stay labeled o2_pct and are not relabeled as initial/final oxygen.",
  "PSI-69 “Burning rate; mm” is preserved as labeled. It is not converted to mm/s without source confirmation.",
  "PSI-159 TFP and Xf values remain unexpanded. No interpretation is invented in the interface.",
  "PSI-101 joins to the test log are unvalidated. Run metadata is shown as returned, without inferred test identity.",
  "No BASS flame-spread rate is published in the selected tables. None is calculated here.",
  "The PSI-100 runs are five separate exports. The interface never concatenates them into one timeline.",
];

export default function OverviewPage() {
  const meta = useMeta();
  const datasets = useDatasets({ limit: 20 });
  const primary = useInvestigations({ role: "primary", limit: 8 });

  const metaData = meta.data?.data;
  const datasetList = datasets.data?.data ?? [];

  const stateCounts = new Map<string, number>();
  for (const dataset of metaData?.datasets ?? []) {
    stateCounts.set(dataset.base_state, (stateCounts.get(dataset.base_state) ?? 0) + 1);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Phase 3 · Scientific evidence explorer"
        title="NASA microgravity combustion, without invented certainty."
        description={
          <>
            A read-only interface over curated NASA Physical Sciences Informatics combustion
            experiments. The backend decides what may be served, compared, and charted. This
            interface renders those decisions, preserves warnings, and labels every measured and
            computed value.
          </>
        }
        actions={
          <>
            <Link href="/datasets" className={buttonStyles({ variant: "primary" })}>
              <Database className="size-4" aria-hidden="true" />
              Browse curated datasets
            </Link>
            <Link href="/about" className={buttonStyles()}>
              <BookOpen className="size-4" aria-hidden="true" />
              Methods & limitations
            </Link>
          </>
        }
        meta={
          metaData ? (
            <>
              <Badge tone="cyan">API {metaData.api_version}</Badge>
              <Badge tone="neutral">Registry snapshot {metaData.registry_snapshot}</Badge>
              <Badge tone="outline" className="font-mono" title={metaData.dataset_version}>
                dataset {metaData.dataset_version.slice(0, 12)}…
              </Badge>
              <Badge tone="emerald">Read-only</Badge>
            </>
          ) : null
        }
      />

      <section aria-label="Platform warning" className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-300" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-amber-100">
              This is an evidence explorer, not a measurement product.
            </p>
            <p className="mt-1 max-w-4xl text-xs leading-relaxed text-ink-300">
              Missing values are not zero. Computed fields are not measurements. Blocked
              comparisons are not shown as if they were valid. Interpretations are Team AFAQ&apos;s
              own; NASA does not endorse this platform.
            </p>
          </div>
        </div>
      </section>

      {meta.isError ? (
        <ErrorState
          error={meta.error}
          title="Platform metadata could not be loaded"
          onRetry={() => meta.refetch()}
        />
      ) : null}

      <section aria-labelledby="platform-counts">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="platform-counts" className="text-sm font-semibold text-ink-100">
              Canonical registry at a glance
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              Counts returned by <span className="mono">/meta</span>. The 8M canonical rows are not
              loaded into the browser; explorers page or bound each request.
            </p>
          </div>
          {meta.isPending ? <Badge tone="neutral">Loading counts…</Badge> : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            label="Canonical rows"
            value={metaData ? formatCount(metaData.canonical_rows) : "—"}
            hint="Across the validated registry"
            icon={<Layers className="size-4" aria-hidden="true" />}
          />
          <MetricCard
            label="PSI investigations"
            value={metaData ? formatCount(metaData.investigations_total) : "—"}
            hint="Catalogued investigations"
            icon={<Database className="size-4" aria-hidden="true" />}
            accent="violet"
          />
          <MetricCard
            label="Curated datasets"
            value={metaData ? formatCount(metaData.curated_dataset_count) : "—"}
            hint="With explicit serving states"
            icon={<ShieldCheck className="size-4" aria-hidden="true" />}
            accent="emerald"
          />
          <MetricCard
            label="Registered measurements"
            value={metaData ? formatCount(metaData.measurement_count) : "—"}
            hint="Units and value kinds declared"
            icon={<Activity className="size-4" aria-hidden="true" />}
            accent="cyan"
          />
          <MetricCard
            label="Comparison rules"
            value={metaData ? formatCount(metaData.comparison_rule_count) : "—"}
            hint="Evaluated by the backend"
            icon={<GitCompare className="size-4" aria-hidden="true" />}
            accent="ember"
          />
        </div>
      </section>

      {metaData ? (
        <section className="surface p-5" aria-labelledby="serving-summary">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="serving-summary" className="text-sm font-semibold text-ink-100">
                Serving states across the nine curated datasets
              </h2>
              <p className="mt-1 text-xs text-ink-400">
                Base state per dataset. Use-specific restrictions appear on each dataset record.
              </p>
            </div>
            <Link href="/quality" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
              Open quality center
            </Link>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {Array.from(stateCounts.entries()).map(([state, count]) => (
              <span key={state} className="inline-flex items-center gap-2 rounded-lg border border-navy-700/70 bg-navy-950/40 px-3 py-2">
                <ServingStateBadge state={state as ServingState} />
                <span className="font-mono text-xs text-ink-300">{count}</span>
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="datasets-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="datasets-heading" className="text-sm font-semibold text-ink-100">
              Curated datasets
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              Every card shows the backend&apos;s base state and use-specific states. None is
              presented as unrestricted.
            </p>
          </div>
          <Link href="/datasets" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            All datasets
          </Link>
        </div>
        {datasets.isPending ? (
          <LoadingState label="Loading curated datasets…" rows={3} />
        ) : datasets.isError ? (
          <ErrorState
            error={datasets.error}
            title="Datasets could not be loaded"
            onRetry={() => datasets.refetch()}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {datasetList.map((dataset) => (
              <DatasetCard key={dataset.dataset_id} dataset={dataset} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="explorers-heading">
        <div className="mb-3">
          <h2 id="explorers-heading" className="text-sm font-semibold text-ink-100">
            Choose an evidence surface
          </h2>
          <p className="mt-1 text-xs text-ink-400">
            Each explorer is bounded by the API. No browser-side unit conversion, aggregation,
            interpolation, or downsampling is performed.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {EXPLORERS.map((explorer) => {
            const Icon = explorer.icon;
            return (
              <Link
                key={explorer.href}
                href={explorer.href}
                className="surface group flex flex-col p-4 transition-colors hover:border-cyan-400/30"
              >
                <span className="flex items-center justify-between">
                  <Icon className={`size-5 ${explorer.accent}`} aria-hidden="true" />
                  <ArrowRight className="size-4 text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-cyan-300" aria-hidden="true" />
                </span>
                <span className="mt-3 text-sm font-semibold text-ink-100">{explorer.title}</span>
                <span className="mt-1 text-xs leading-relaxed text-ink-400">{explorer.description}</span>
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="primary-investigations">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="primary-investigations" className="text-sm font-semibold text-ink-100">
              Primary evidence investigations
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              Curated by <span className="mono">mvp_role=primary</span>. Supporting and context
              investigations remain visible in the catalog.
            </p>
          </div>
          <Link href="/investigations" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Full investigation catalog
          </Link>
        </div>
        {primary.isPending ? (
          <LoadingState label="Loading primary investigations…" rows={2} />
        ) : primary.isError ? (
          <ErrorState
            error={primary.error}
            title="Investigations could not be loaded"
            onRetry={() => primary.refetch()}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {(primary.data?.data ?? []).map((investigation) => (
              <InvestigationCard key={investigation.accession} investigation={investigation} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="known-limitations" className="surface p-5">
        <div className="flex items-start gap-3">
          <span className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-2 text-amber-300">
            <AlertTriangle className="size-5" aria-hidden="true" />
          </span>
          <div>
            <h2 id="known-limitations" className="text-sm font-semibold text-ink-100">
              Known limitations carried into the interface
            </h2>
            <p className="mt-1 text-xs text-ink-400">
              These are source and registry constraints, not display bugs. The full methods page
              explains how each is handled.
            </p>
            <ul className="mt-3 grid gap-2 text-xs leading-relaxed text-ink-300 md:grid-cols-2">
              {LIMITATIONS.map((limitation) => (
                <li key={limitation} className="flex items-start gap-2 rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden="true" />
                  {limitation}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="registry-versions">
        <h2 id="registry-versions" className="text-sm font-semibold text-ink-100">
          Reproducibility anchors
        </h2>
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-ink-500">Registry snapshot</dt>
            <dd className="mono mt-0.5 text-ink-200">{metaData?.registry_snapshot ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Registry version</dt>
            <dd className="mono mt-0.5 text-ink-200">{metaData?.registry_version ?? "—"}</dd>
          </div>
          <div className="lg:col-span-2">
            <dt className="text-ink-500">Dataset version</dt>
            <dd className="mono mt-0.5 break-all text-ink-200">{metaData?.dataset_version ?? "—"}</dd>
          </div>
        </dl>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-400">
          Response metadata also carries a request identifier and generation timestamp. The footer
          shows the same version anchors on every page.
        </p>
      </section>
    </div>
  );
}
