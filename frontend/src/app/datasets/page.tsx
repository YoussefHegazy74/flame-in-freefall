"use client";

import { Suspense } from "react";
import Link from "next/link";
import { Database } from "lucide-react";
import { useDatasets } from "@/lib/api/hooks";
import type { ServingState } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { familyLabel, labelForUse } from "@/lib/labels";
import { formatCount } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, SelectFilter } from "@/components/ui/filter";
import { Pagination } from "@/components/ui/pagination";
import { DatasetCard } from "@/components/scientific/dataset-card";

const PAGE_SIZE = 9;
const FAMILIES = ["gas_flame", "material", "droplet", "telemetry", "smoke", "smoke_log", "metadata"];
const STATES: ServingState[] = [
  "available",
  "available_with_warnings",
  "restricted",
  "blocked",
  "metadata_only",
];
const USES = ["exploration", "quantitative_comparison", "time_series", "provenance"];

function DatasetsContent() {
  const { get, setParams, clearParams } = useUrlState();
  const family = get("family") ?? "";
  const state = get("state") ?? "";
  const use = get("use") ?? "exploration";
  const offset = Number(get("offset") ?? 0) || 0;

  const datasets = useDatasets({
    family: family || undefined,
    state: state || undefined,
    use,
    limit: PAGE_SIZE,
    offset,
  });

  const page = datasets.data?.meta.page;
  const total = page?.total ?? 0;
  const items = datasets.data?.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Catalog"
        title="Curated datasets"
        description={
          <>
            Nine MVP datasets with explicit download status, access scope, measurement counts, and
            per-use serving states. The browser does not upgrade a restricted or blocked state.
          </>
        }
        actions={
          <Link href="/quality" className={buttonStyles()}>
            Quality center
          </Link>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} datasets</Badge>
            <Badge tone="neutral">Serving use: {labelForUse(use)}</Badge>
            {family ? <Badge tone="violet">Family: {familyLabel(family)}</Badge> : null}
            {state ? <Badge tone="ember">State: {state.replace(/_/g, " ")}</Badge> : null}
          </>
        }
      />

      <FilterBar
        label="Dataset filters"
        actions={
          <FilterActions
            onClear={() => clearParams()}
            resultLabel={
              datasets.isFetching && !datasets.isPending
                ? "Refreshing datasets…"
                : `${formatCount(total)} dataset${total === 1 ? "" : "s"} for ${labelForUse(use).toLowerCase()}`
            }
          />
        }
      >
        <SelectFilter
          id="dataset-family"
          label="Experiment family"
          value={family}
          onChange={(value) => setParams({ family: value || null })}
          options={FAMILIES.map((item) => ({ value: item, label: familyLabel(item) }))}
          placeholder="All families"
        />
        <SelectFilter
          id="dataset-use"
          label="Serving use"
          value={use}
          onChange={(value) => setParams({ use: value || "exploration" })}
          options={USES.map((item) => ({ value: item, label: labelForUse(item) }))}
          placeholder="Exploration"
          hint="The state filter is evaluated against this use."
        />
        <SelectFilter
          id="dataset-state"
          label="Serving state for selected use"
          value={state}
          onChange={(value) => setParams({ state: value || null })}
          options={STATES.map((item) => ({
            value: item,
            label: item.replace(/_/g, " "),
          }))}
          placeholder="All states"
        />
        <div className="surface-inset flex items-start gap-2 p-2.5 text-[11px] leading-relaxed text-ink-400">
          <Database className="mt-0.5 size-3.5 shrink-0 text-cyan-300" aria-hidden="true" />
          A dataset may be available for exploration while blocked for time series or restricted
          for quantitative comparison.
        </div>
      </FilterBar>

      {datasets.isPending ? (
        <LoadingState label="Loading curated datasets…" rows={3} />
      ) : datasets.isError ? (
        <ErrorState
          error={datasets.error}
          title="The dataset catalog could not be loaded"
          onRetry={() => datasets.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No datasets match these filters"
          description="Clear the family, use, and state filters. The API returned no dataset for this combination; nothing was removed locally."
          icon={<Database className="size-6" aria-hidden="true" />}
          action={
            <button type="button" className={buttonStyles()} onClick={() => clearParams()}>
              Clear filters
            </button>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((dataset) => (
              <DatasetCard key={dataset.dataset_id} dataset={dataset} />
            ))}
          </div>
          <Pagination
            total={total}
            limit={PAGE_SIZE}
            offset={offset}
            onPageChange={(nextOffset) =>
              setParams({ offset: nextOffset || null }, { resetOffset: false, scroll: true })
            }
            label="datasets"
          />
        </>
      )}
    </div>
  );
}

export default function DatasetsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading dataset catalog…" rows={3} />}>
      <DatasetsContent />
    </Suspense>
  );
}
