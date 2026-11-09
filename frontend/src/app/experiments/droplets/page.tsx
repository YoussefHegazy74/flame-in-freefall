"use client";

import { Suspense, useMemo, useState } from "react";
import { AlertTriangle, Droplets, Info } from "lucide-react";
import { useDropletTests } from "@/lib/api/hooks";
import type { DropletRow } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { formatCount, formatNumber } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, TextFilter } from "@/components/ui/filter";
import { Pagination } from "@/components/ui/pagination";
import { TD_CLASS, TH_CLASS, TableShell } from "@/components/ui/table-shell";
import { RecordDrawer } from "@/components/scientific/record-drawer";
import { RowQualityFlags, ProvenanceLink, FieldGrid, DetailSection } from "@/components/scientific/record-fields";

const PAGE_SIZE = 25;

interface DropletForm {
  fuel: string;
  pressure_min: string;
  pressure_max: string;
}

function formFromParams(get: (key: string, fallback?: string) => string | undefined): DropletForm {
  return {
    fuel: get("fuel") ?? "",
    pressure_min: get("pressure_min") ?? "",
    pressure_max: get("pressure_max") ?? "",
  };
}

function DropletsContent() {
  const { get, setParams, clearParams } = useUrlState();
  const applied = useMemo(() => formFromParams(get), [get]);
  const appliedKey = useMemo(() => JSON.stringify(applied), [applied]);
  const [draftState, setDraftState] = useState<{ key: string; value: DropletForm } | null>(null);
  const form = draftState?.key === appliedKey ? draftState.value : applied;
  const [selectedRow, setSelectedRow] = useState<DropletRow | null>(null);

  const offset = Number(get("offset") ?? 0) || 0;

  const droplet = useDropletTests({
    accession: "PSI-69",
    fuel: applied.fuel || undefined,
    pressure_min: applied.pressure_min ? Number(applied.pressure_min) : undefined,
    pressure_max: applied.pressure_max ? Number(applied.pressure_max) : undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const page = droplet.data?.meta.page;
  const total = page?.total ?? 0;
  const rows = droplet.data?.data ?? [];

  const setField = <K extends keyof DropletForm>(key: K, value: DropletForm[K]) => {
    setDraftState({ key: appliedKey, value: { ...form, [key]: value } });
  };

  const applyFilters = () => {
    setParams({
      fuel: form.fuel.trim() || null,
      pressure_min: form.pressure_min.trim() || null,
      pressure_max: form.pressure_max.trim() || null,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Experiment explorer · Droplets"
        title="PSI-69 FLEX droplet tests"
        description={
          <>
            Droplet ignition and burning summaries. Ambient pressure is in mmHg, diameters are in
            mm, and the source burning-rate header says mm. That rate is preserved as labeled and is
            not converted to mm/s.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} rows</Badge>
            <Badge tone="neutral">PSI-69</Badge>
            <Badge tone="amber">Burning rate unit ambiguous</Badge>
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3.5">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-amber-100">Burning rate is not a spread rate.</p>
            <p className="mt-1">
              The source column is “Burning rate; mm”. It is displayed as{" "}
              <span className="mono">burning_rate_mm_as_labeled</span> and is not converted to mm/s.
              No BASS or FLEX flame-spread rate is inferred. Missing visible-flame extinction
              diameters remain “—”.
            </p>
          </div>
        </div>
      </section>

      <FilterBar
        label="Droplet filters"
        actions={
          <FilterActions
            onClear={() => {
              setDraftState(null);
              clearParams();
            }}
            resultLabel={
              droplet.isFetching && !droplet.isPending
                ? "Refreshing rows…"
                : `${formatCount(total)} matching row${total === 1 ? "" : "s"}`
            }
          >
            <button type="button" onClick={applyFilters} className={buttonStyles({ variant: "primary", size: "sm" })}>
              Apply filters
            </button>
          </FilterActions>
        }
      >
        <TextFilter
          id="droplet-fuel"
          label="Fuel (exact label, case-insensitive)"
          value={form.fuel}
          onChange={(value) => setField("fuel", value)}
          placeholder="Methanol or Heptane"
          hint="Labels are source values; no chemistry normalization is applied."
        />
        <TextFilter
          id="droplet-pressure-min"
          label="Ambient pressure ≥ (mmHg)"
          type="number"
          step={0.1}
          value={form.pressure_min}
          onChange={(value) => setField("pressure_min", value)}
          placeholder="e.g. 760"
        />
        <TextFilter
          id="droplet-pressure-max"
          label="Ambient pressure ≤ (mmHg)"
          type="number"
          step={0.1}
          value={form.pressure_max}
          onChange={(value) => setField("pressure_max", value)}
          placeholder="e.g. 2320"
        />
        <div className="surface-inset flex items-start gap-2 p-2.5 text-[11px] leading-relaxed text-ink-400">
          <Info className="mt-0.5 size-3.5 shrink-0 text-cyan-300" aria-hidden="true" />
          Missing values are not zero. Row flags identify sentinel and ambiguity tokens.
        </div>
      </FilterBar>

      {droplet.isPending ? (
        <LoadingState label="Loading droplet rows…" rows={5} />
      ) : droplet.isError ? (
        <ErrorState
          error={droplet.error}
          title="Droplet rows could not be loaded"
          onRetry={() => droplet.refetch()}
        >
          <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
            Pressure bounds must be ordered low to high.
          </p>
        </ErrorState>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No droplet rows match these filters"
          description="Clear the fuel and pressure filters. No measurement is synthesized to fill the table."
          icon={<Droplets className="size-6" aria-hidden="true" />}
          action={
            <button type="button" className={buttonStyles()} onClick={() => clearParams()}>
              Clear filters
            </button>
          }
        />
      ) : (
        <>
          <TableShell caption="PSI-69 droplet test rows with as-labeled burning rate, ambient pressure, initial composition, quality flags, and provenance">
            <thead>
              <tr>
                <th scope="col" className={TH_CLASS}>FLEX test</th>
                <th scope="col" className={TH_CLASS}>Fuel</th>
                <th scope="col" className={TH_CLASS}>Ambient pressure (mmHg)</th>
                <th scope="col" className={TH_CLASS}>Initial O₂ mole fraction</th>
                <th scope="col" className={TH_CLASS}>Initial diameter (mm)</th>
                <th scope="col" className={TH_CLASS}>Flame extinction diameter (mm)</th>
                <th scope="col" className={TH_CLASS}>Burning rate (as labeled; mm)</th>
                <th scope="col" className={TH_CLASS}>Burn time (s)</th>
                <th scope="col" className={TH_CLASS}>Test end</th>
                <th scope="col" className={TH_CLASS}>Row flags</th>
                <th scope="col" className={TH_CLASS}><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.observation_id} className="hover:bg-navy-800/35">
                  <td className={TD_CLASS}>
                    <p className="font-medium text-ink-100">{row.flex_test_number ?? "—"}</p>
                    <p className="mt-0.5 text-[10px] text-ink-500">
                      {row.flex_identifier ?? "no FLEX id"} · {row.test_date ?? "date not stated"}
                    </p>
                  </td>
                  <td className={TD_CLASS}>{row.fuel ?? "—"}</td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.ambient_pressure_mm_hg === null ? "—" : formatNumber(row.ambient_pressure_mm_hg)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.o2_initial_mole_fraction === null ? "—" : formatNumber(row.o2_initial_mole_fraction)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.droplet_initial_diameter_mm === null ? "—" : formatNumber(row.droplet_initial_diameter_mm)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.visible_flame_extinction_diameter_mm === null
                      ? "—"
                      : formatNumber(row.visible_flame_extinction_diameter_mm)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-amber-200`}>
                    {row.burning_rate_mm_as_labeled === null
                      ? "—"
                      : formatNumber(row.burning_rate_mm_as_labeled)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.burn_time_s === null ? "—" : formatNumber(row.burn_time_s)}
                  </td>
                  <td className={TD_CLASS}>{row.test_end ?? "—"}</td>
                  <td className={TD_CLASS}>
                    <RowQualityFlags flags={row.quality_flags} />
                  </td>
                  <td className={TD_CLASS}>
                    <button
                      type="button"
                      onClick={() => setSelectedRow(row)}
                      className="whitespace-nowrap text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                      aria-label={`Open droplet row ${row.flex_test_number ?? row.observation_id}`}
                    >
                      Open record
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
          <Pagination
            total={total}
            limit={PAGE_SIZE}
            offset={offset}
            onPageChange={(nextOffset) =>
              setParams({ offset: nextOffset || null }, { resetOffset: false, scroll: true })
            }
            label="droplet rows"
          />
        </>
      )}

      <RecordDrawer
        open={selectedRow !== null}
        title={selectedRow ? `FLEX test ${selectedRow.flex_test_number ?? selectedRow.observation_id}` : "Droplet record"}
        subtitle={selectedRow ? `${selectedRow.fuel ?? "fuel not stated"} · ${selectedRow.test_date ?? "date not stated"}` : null}
        onClose={() => setSelectedRow(null)}
      >
        {selectedRow ? <DropletRecord row={selectedRow} /> : null}
      </RecordDrawer>
    </div>
  );
}

function DropletRecord({ row }: { row: DropletRow }) {
  return (
    <div className="space-y-4">
      <DetailSection
        title="Recorded conditions and outcomes"
        description="Burning rate is shown with its source header meaning, not converted."
      >
        <FieldGrid
          fields={[
            { key: "flex_test_number", value: row.flex_test_number },
            { key: "test_date", value: row.test_date },
            { key: "flex_identifier", value: row.flex_identifier },
            { key: "test_gmt", value: row.test_gmt },
            { key: "fuel", value: row.fuel },
            { key: "ambient_pressure_mm_hg", value: row.ambient_pressure_mm_hg, unit: "mmHg" },
            { key: "o2_initial_mole_fraction", value: row.o2_initial_mole_fraction },
            { key: "n2_initial_mole_fraction", value: row.n2_initial_mole_fraction },
            { key: "co_initial_mole_fraction", value: row.co_initial_mole_fraction },
            { key: "he_initial_mole_fraction", value: row.he_initial_mole_fraction },
            { key: "droplet_initial_diameter_mm", value: row.droplet_initial_diameter_mm, unit: "mm" },
            { key: "visible_flame_extinction_diameter_mm", value: row.visible_flame_extinction_diameter_mm, unit: "mm" },
            { key: "burning_rate_mm_as_labeled", value: row.burning_rate_mm_as_labeled, unit: "mm as labeled" },
            { key: "burn_time_s", value: row.burn_time_s, unit: "s" },
            { key: "test_end", value: row.test_end },
          ]}
          columns={2}
        />
      </DetailSection>

      <DetailSection title="Row quality flags" description="The unit ambiguity is a source limitation, not a display choice.">
        <RowQualityFlags flags={row.quality_flags} />
      </DetailSection>

      <DetailSection title="Source identity">
        <FieldGrid
          fields={[
            { key: "observation_id", value: row.observation_id },
            { key: "table_id", value: row.table_id },
            { key: "source_file", value: row.source_file },
            { key: "source_row", value: row.source_row },
            { key: "source_sha256", value: row.source_sha256 },
            { key: "retrieved_at", value: row.retrieved_at },
            { key: "parser_version", value: row.parser_version },
          ]}
          columns={2}
        />
        <div className="mt-3">
          <ProvenanceLink
            accession={row.accession}
            file={row.source_file}
            row={row.source_row}
          />
        </div>
      </DetailSection>
    </div>
  );
}

export default function DropletsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading droplet explorer…" rows={5} />}>
      <DropletsContent />
    </Suspense>
  );
}
