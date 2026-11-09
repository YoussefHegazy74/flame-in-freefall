"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  GitCompare,
  Info,
  Layers,
  Lock,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useMeta } from "@/lib/api/hooks";
import { API_DOCS_URL } from "@/lib/api/client";
import { formatCount } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";
import {
  ComparisonStateBadge,
  QualityStatusBadge,
  ServingStateBadge,
} from "@/components/scientific/state-badge";

const RULES = [
  {
    title: "No fabricated measurements",
    body: "Every numeric value is a source value returned by the API. Missing values are rendered as “—” and are never filled, interpolated, or replaced with zero.",
  },
  {
    title: "Measured, computed, raw, and categorical values stay distinct",
    body: "Computed fields such as Tad and Zst are labeled computed. Uncalibrated channels are labeled raw. Categorical labels are not aggregated as numbers.",
  },
  {
    title: "Units are never silently mixed",
    body: "PSI-10 pressure is in atm and PSI-159 pressure is in bar. PSI-25 and PSI-26 use different oxygen columns. Filters that would mix units require an explicit accession.",
  },
  {
    title: "Quality flags and warnings are preserved",
    body: "Response quality, dataset quality, row-level sentinel flags, and serving restrictions are rendered as returned. No warning is collapsed away to simplify a card.",
  },
  {
    title: "Comparability is a backend decision",
    body: "A matching column name, unit, or experiment family is not sufficient evidence. The default is not comparable; conditional rules require explicitly verified conditions.",
  },
  {
    title: "No unsupported causal or risk claims",
    body: "The interface describes measured and computed quantities. It does not infer causation, material risk, or mission outcomes from a comparison state or a chart.",
  },
];

const LIMITATIONS = [
  {
    accession: "PSI-98",
    title: "No served telemetry series",
    body: "The selected source is an experimental table only. The telemetry endpoint returns 404 rather than fabricating a time series.",
  },
  {
    accession: "PSI-26",
    title: "Oxygen header ambiguity",
    body: "The header says percent while observed values are near 0.22. Values stay labeled o2_pct and are not relabeled as initial or final oxygen or converted to percent.",
  },
  {
    accession: "PSI-69",
    title: "Burning-rate unit ambiguity",
    body: "The source header says “Burning rate; mm”. The value is preserved as labeled and is not converted to mm/s. No BASS or FLEX spread rate is inferred.",
  },
  {
    accession: "PSI-159",
    title: "Unexpanded TFP and Xf",
    body: "TFP and Xf values remain unexpanded. The interface does not invent a definition or treat them as a derived quantity.",
  },
  {
    accession: "PSI-101",
    title: "Unvalidated test-log join",
    body: "Material names and aging conditions require a validated join to the test logs. Run metadata is shown as returned; no test identity is inferred.",
  },
  {
    accession: "PSI-100",
    title: "Separate telemetry runs",
    body: "Five exports or workbook sheets are separate runs with different durations and channels. The interface never concatenates them into one timeline.",
  },
  {
    accession: "PSI-10 / PSI-159",
    title: "Ramped and qualified rows",
    body: "Rows carrying RAMP, RAMPED, or LOW O2 qualifiers are excluded by default. When included, they remain flagged and are not treated as fixed set points.",
  },
  {
    accession: "PSI-25 / PSI-26",
    title: "Free-text material labels",
    body: "Material names are not normalized or joined to a validated registry. Matching words are not a validated material identity.",
  },
];

export default function AboutPage() {
  const meta = useMeta();
  const metaData = meta.data?.data;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Reference · Methods"
        title="Methods, limitations, and attribution"
        description={
          <>
            This platform is a read-only evidence explorer over curated NASA Physical Sciences
            Informatics combustion experiments. The backend decides what may be served, compared,
            and charted. This page documents those decisions, the scientific rules the interface
            enforces, and the limitations that remain.
          </>
        }
        actions={
          <>
            <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className={buttonStyles()}>
              <Terminal className="size-4" aria-hidden="true" />
              API reference
            </a>
            <a
              href="https://psi.nasa.gov/"
              target="_blank"
              rel="noreferrer"
              className={buttonStyles()}
            >
              <ExternalLink className="size-4" aria-hidden="true" />
              NASA PSI
            </a>
          </>
        }
        meta={
          <>
            <Badge tone="cyan">Phase 3</Badge>
            <Badge tone="neutral">Read-only</Badge>
            <Badge tone="emerald">Registry {metaData?.registry_version ?? "—"}</Badge>
            <Badge tone="outline">Snapshot {metaData?.registry_snapshot ?? "—"}</Badge>
          </>
        }
      />

      <section className="surface p-5" aria-labelledby="scope">
        <h2 id="scope" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
          Scope
        </h2>
        <div className="mt-3 space-y-3 text-sm leading-relaxed text-ink-300">
          <p>
            Flame in Freefall is an independent evidence explorer built by Team AFAQ. It surfaces a
            curated subset of NASA PSI investigations concerned with microgravity combustion:
            gas-flame tests, material flammability matrices, droplet tests, SAFFIRE-III telemetry,
            SAME-R smoke runs, and a legacy smoke event log.
          </p>
          <p>
            The platform does not redistribute raw NASA archives and does not expose arbitrary SQL.
            It serves named, bounded queries with explicit units, value kinds, quality flags,
            serving states, and provenance. The canonical registry is the source of truth; the
            browser renders it without reimplementing comparability or serving logic.
          </p>
          <p>
            The 8M-row canonical registry is not loaded into the browser. List endpoints are
            paginated, and time-series endpoints require a bounded range and a maximum point count.
          </p>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "Canonical rows",
              value: metaData ? formatCount(metaData.canonical_rows) : "—",
              icon: Layers,
            },
            {
              label: "Investigations",
              value: metaData ? formatCount(metaData.investigations_total) : "—",
              icon: Database,
            },
            {
              label: "Curated datasets",
              value: metaData ? formatCount(metaData.curated_dataset_count) : "—",
              icon: ShieldCheck,
            },
            {
              label: "Registered measurements",
              value: metaData ? formatCount(metaData.measurement_count) : "—",
              icon: Activity,
            },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-3.5">
                <Icon className="size-4 text-cyan-300" aria-hidden="true" />
                <p className="mt-2 text-[10px] uppercase tracking-[0.08em] text-ink-500">
                  {item.label}
                </p>
                <p className="mt-0.5 font-mono text-lg text-ink-100">{item.value}</p>
              </div>
            );
          })}
        </div>
        {meta.isError ? (
          <div className="mt-3">
            <ErrorState
              error={meta.error}
              title="Live registry metadata could not be loaded"
              onRetry={() => meta.refetch()}
            />
          </div>
        ) : null}
      </section>

      <section aria-labelledby="scientific-rules">
        <div className="mb-3">
          <h2 id="scientific-rules" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <CheckCircle2 className="size-4 text-emerald-300" aria-hidden="true" />
            Scientific rules enforced by the interface
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-400">
            These are constraints on presentation, not claims that the source data are complete or
            correct.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {RULES.map((rule) => (
            <article key={rule.title} className="surface p-4">
              <h3 className="text-xs font-semibold text-ink-100">{rule.title}</h3>
              <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">{rule.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="serving-model">
        <h2 id="serving-model" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <Lock className="size-4 text-amber-300" aria-hidden="true" />
          Serving states and quality states
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          Serving states are per use. A dataset can be available for exploration while restricted
          for quantitative comparison or blocked for time series. Quality status describes the
          validation outcome and is not interchangeable with a serving state.
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-4">
            <h3 className="text-xs font-semibold text-ink-100">Serving states</h3>
            <ul className="mt-2 space-y-2 text-[11px] leading-relaxed text-ink-400">
              <li className="flex items-start gap-2">
                <ServingStateBadge state="available" />
                <span>The resource may be served for the selected use.</span>
              </li>
              <li className="flex items-start gap-2">
                <ServingStateBadge state="available_with_warnings" />
                <span>Available only with the documented warnings, which remain visible.</span>
              </li>
              <li className="flex items-start gap-2">
                <ServingStateBadge state="restricted" />
                <span>The use is limited by an explicit registry restriction.</span>
              </li>
              <li className="flex items-start gap-2">
                <ServingStateBadge state="blocked" />
                <span>The backend refuses the use; the interface does not offer a workaround.</span>
              </li>
              <li className="flex items-start gap-2">
                <ServingStateBadge state="metadata_only" />
                <span>Only metadata is available for this use.</span>
              </li>
            </ul>
          </div>
          <div className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-4">
            <h3 className="text-xs font-semibold text-ink-100">Quality statuses</h3>
            <ul className="mt-2 space-y-2 text-[11px] leading-relaxed text-ink-400">
              <li className="flex items-start gap-2">
                <QualityStatusBadge status="verified" />
                <span>Validation found no blocking issue for the documented checks.</span>
              </li>
              <li className="flex items-start gap-2">
                <QualityStatusBadge status="partial" />
                <span>Some checks pass and documented warnings remain.</span>
              </li>
              <li className="flex items-start gap-2">
                <QualityStatusBadge status="blocked" />
                <span>A blocking integrity issue prevents normal use.</span>
              </li>
              <li className="flex items-start gap-2">
                <QualityStatusBadge status="experimental_table_only" />
                <span>Only an experimental summary table is available; no telemetry series.</span>
              </li>
              <li className="flex items-start gap-2">
                <QualityStatusBadge status="not_available" />
                <span>The requested data are not available.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="comparison-policy">
        <h2 id="comparison-policy" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <GitCompare className="size-4 text-cyan-300" aria-hidden="true" />
          Comparison policy
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          The comparison engine is conservative. It starts from explicit rules, checks physical
          quantity, unit, value kind, calibration, availability, and required conditions, and never
          upgrades a comparison because two labels look similar.
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <ComparisonStateBadge status="comparable" />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              Every required condition is verified and the hard checks pass.
            </p>
          </div>
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <ComparisonStateBadge status="conditionally_comparable" />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              A rule exists, but one or more documented conditions remain unverified.
            </p>
          </div>
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <ComparisonStateBadge status="not_comparable" />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              No valid basis, no explicit rule, or a supplied condition failed.
            </p>
          </div>
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            <ComparisonStateBadge status="blocked" />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              A hard unit, value-kind, calibration, availability, or quantity conflict.
            </p>
          </div>
          <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5 md:col-span-2">
            <ComparisonStateBadge status="insufficient_metadata" />
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              The available metadata cannot decide the question. Conditions cannot override this
              state.
            </p>
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          The comparison endpoint returns a decision and measurement metadata, not paired values.
          The interface therefore does not render a shared comparison chart.
        </div>
      </section>

      <section aria-labelledby="source-limitations">
        <div className="mb-3">
          <h2 id="source-limitations" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <AlertTriangle className="size-4 text-amber-300" aria-hidden="true" />
            Known source limitations
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-400">
            These limitations are carried from the source files and registry. They are not display
            bugs and cannot be cleared by changing a filter.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {LIMITATIONS.map((item) => (
            <article
              key={item.title}
              className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="amber">{item.accession}</Badge>
                <h3 className="text-xs font-semibold text-ink-100">{item.title}</h3>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-ink-300">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="missing-capabilities">
        <h2 id="missing-capabilities" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <Info className="size-4 text-violet-400" aria-hidden="true" />
          Documented backend gaps
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          The interface does not invent endpoints or change the API contract. The following
          capabilities are not implemented in the current backend and are therefore absent:
        </p>
        <ul className="mt-3 grid gap-2 text-xs leading-relaxed text-ink-300 md:grid-cols-2">
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            No citation, publication, or file-catalog endpoint. Provenance lookup requires an exact
            file name discovered from a curated record.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            No paired comparison values or comparison statistics endpoint. The studio renders the
            decision only.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            No field-level metadata endpoint beyond the measurement registry.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            No arbitrary query, export, or download endpoint. Raw NASA files are not redistributed.
          </li>
        </ul>
      </section>

      <section className="surface p-5" aria-labelledby="reproducibility">
        <h2 id="reproducibility" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <FileSearch className="size-4 text-cyan-300" aria-hidden="true" />
          Reproducibility anchors
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          Every API response carries a request identifier and generation timestamp. These registry
          anchors identify the exact snapshot used by this interface.
        </p>
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-ink-500">Registry snapshot</dt>
            <dd className="mono mt-0.5 text-ink-200">{metaData?.registry_snapshot ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Registry version</dt>
            <dd className="mono mt-0.5 text-ink-200">{metaData?.registry_version ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">API version</dt>
            <dd className="mono mt-0.5 text-ink-200">{metaData?.api_version ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Comparison rules</dt>
            <dd className="mono mt-0.5 text-ink-200">
              {metaData ? formatCount(metaData.comparison_rule_count) : "—"}
            </dd>
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <dt className="text-ink-500">Dataset version</dt>
            <dd className="mono mt-0.5 break-all text-ink-200">
              {metaData?.dataset_version ?? "—"}
            </dd>
          </div>
        </dl>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/quality" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Open the quality center
          </Link>
          <Link href="/provenance" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Resolve source provenance
          </Link>
          <Link href="/compare" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Open the Comparison Studio
          </Link>
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="attribution">
        <h2 id="attribution" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <Database className="size-4 text-cyan-300" aria-hidden="true" />
          Attribution and disclaimer
        </h2>
        <div className="mt-2 space-y-2 text-xs leading-relaxed text-ink-300">
          <p>
            Source data are published by the NASA Physical Sciences Informatics system. NASA does
            not endorse this platform, its interpretations, or any derived presentation. Consult the
            original NASA source files and investigation records for authoritative information.
          </p>
          <p>
            The registry, quality warnings, comparability rules, and serving decisions are products
            of this project&apos;s Phase 1 and Phase 2 work. They are documented in the repository and
            exposed through the API. This interface is a Phase 3 client of that backend.
          </p>
          <p>
            Built by Team AFAQ. The platform is read-only and does not collect user data beyond
            standard server request logs.
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          <a
            href="https://psi.nasa.gov/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
          >
            NASA PSI
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
          >
            OpenAPI reference
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
}
