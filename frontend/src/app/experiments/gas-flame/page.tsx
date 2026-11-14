"use client";

import { Suspense, useMemo, useState } from "react";
import { AlertTriangle, Flame, Info } from "lucide-react";
import { useGasFlameFacets, useGasFlameTests } from "@/lib/api/hooks";
import type { GasFlameRow } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { formatCount, formatNumber } from "@/lib/format";
import { fieldLabel } from "@/lib/labels";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, TextFilter } from "@/components/ui/filter";
import { Pagination } from "@/components/ui/pagination";
import { TD_CLASS, TH_CLASS, TableShell } from "@/components/ui/table-shell";
import { RecordDrawer } from "@/components/scientific/record-drawer";
import { RowQualityFlags, ProvenanceLink, FieldGrid, DetailSection } from "@/components/scientific/record-fields";
import { ValueKindBadge } from "@/components/scientific/unit-label";
import { GasFlameFacetsPanel } from "@/components/scientific/gas-flame-facets-panel";
import { CitationButton, CitationDrawer } from "@/components/scientific/citation-drawer";

const PAGE_SIZE = 25;

interface GasForm {
  accession: string;
  flame_type: string;
  fuel: string;
  oxygen_min: string;
  oxygen_max: string;
  pressure_min: string;
  pressure_max: string;
  hot_ignition: string;
  extinction_mode: string;
  tfp: string;
  include_qualified: boolean;
  sort: string;
  order: "asc" | "desc";
}

function formFromParams(get: (key: string, fallback?: string) => string | undefined): GasForm {
  return {
    accession: get("accession") ?? "",
    flame_type: get("flame_type") ?? "",
    fuel: get("fuel") ?? "",
    oxygen_min: get("oxygen_min") ?? "",
    oxygen_max: get("oxygen_max") ?? "",
    pressure_min: get("pressure_min") ?? "",
    pressure_max: get("pressure_max") ?? "",
    hot_ignition: get("hot_ignition") ?? "",
    extinction_mode: get("extinction_mode") ?? "",
    tfp: get("tfp") ?? "",
    include_qualified: get("include_qualified") === "true",
    sort: get("sort") ?? "source_row",
    order: get("order") === "desc" ? "desc" : "asc",
  };
}

function GasFlameContent() {
  const { get, setParams, clearParams } = useUrlState();
  const applied = useMemo(() => formFromParams(get), [get]);
  const appliedKey = useMemo(() => JSON.stringify(applied), [applied]);
  const [draftState, setDraftState] = useState<{ key: string; value: GasForm } | null>(null);
  const form = draftState?.key === appliedKey ? draftState.value : applied;
  const [selectedRow, setSelectedRow] = useState<GasFlameRow | null>(null);
  const [citationId, setCitationId] = useState<string | null>(null);

  const offset = Number(get("offset") ?? 0) || 0;
  const pressureEnabled = Boolean(form.accession);

  const facets = useGasFlameFacets({
    accession: applied.accession || undefined,
    include_qualified: applied.include_qualified,
  });
  const facetData = facets.data?.data;

  const gas = useGasFlameTests({
    accession: applied.accession || undefined,
    flame_type: applied.flame_type || undefined,
    fuel: applied.fuel || undefined,
    oxygen_min: applied.oxygen_min ? Number(applied.oxygen_min) : undefined,
    oxygen_max: applied.oxygen_max ? Number(applied.oxygen_max) : undefined,
    pressure_min:
      applied.accession && applied.pressure_min ? Number(applied.pressure_min) : undefined,
    pressure_max:
      applied.accession && applied.pressure_max ? Number(applied.pressure_max) : undefined,
    hot_ignition: applied.hot_ignition || undefined,
    extinction_mode: applied.extinction_mode || undefined,
    tfp: applied.tfp || undefined,
    include_qualified: applied.include_qualified,
    sort: applied.sort,
    order: applied.order,
    limit: PAGE_SIZE,
    offset,
  });

  const page = gas.data?.meta.page;
  const total = page?.total ?? 0;
  const excludedQualified = page?.excluded_qualified_rows ?? 0;
  const pressureField = page?.pressure_field ?? null;
  const pressureUnit = page?.pressure_unit ?? null;
  const rows = gas.data?.data ?? [];
  const activeFilterCount = [
    applied.accession,
    applied.flame_type,
    applied.fuel,
    applied.oxygen_min,
    applied.oxygen_max,
    applied.pressure_min,
    applied.pressure_max,
    applied.hot_ignition,
    applied.extinction_mode,
    applied.tfp,
  ].filter(Boolean).length + (applied.include_qualified ? 1 : 0);

  const setField = <K extends keyof GasForm>(key: K, value: GasForm[K]) => {
    const next = { ...form, [key]: value };
    if (key === "accession" && value !== form.accession) {
      next.pressure_min = "";
      next.pressure_max = "";
    }
    setDraftState({ key: appliedKey, value: next });
  };

  const applyFilters = () => {
    setParams({
      accession: form.accession || null,
      flame_type: form.flame_type.trim() || null,
      fuel: form.fuel.trim() || null,
      oxygen_min: form.oxygen_min.trim() || null,
      oxygen_max: form.oxygen_max.trim() || null,
      pressure_min: form.accession && form.pressure_min.trim() ? form.pressure_min.trim() : null,
      pressure_max: form.accession && form.pressure_max.trim() ? form.pressure_max.trim() : null,
      hot_ignition: form.hot_ignition.trim() || null,
      extinction_mode: form.extinction_mode.trim() || null,
      tfp: form.tfp.trim() || null,
      include_qualified: form.include_qualified ? "true" : null,
      sort: form.sort === "source_row" ? null : form.sort,
      order: form.order === "asc" ? null : form.order,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Experiment explorer · Gas flame"
        title="PSI-10 and PSI-159 gas-flame tests"
        description={
          <>
            Summary-table rows only. Oxygen is a mole fraction; pressure fields use different units
            by accession. Tad and Zst are computed source fields, never measured temperatures or
            mixture fractions.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} rows</Badge>
            <Badge tone="neutral">Page size {PAGE_SIZE}</Badge>
            {applied.accession ? <Badge tone="violet">{applied.accession}</Badge> : null}
            {activeFilterCount > 0 ? <Badge tone="ember">{activeFilterCount} active filters</Badge> : null}
            {!applied.include_qualified && excludedQualified > 0 ? (
              <Badge tone="amber">{formatCount(excludedQualified)} qualified rows excluded</Badge>
            ) : null}
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-warning-soft p-3.5">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <p className="text-[11px] leading-relaxed text-ink-300">
            <span className="font-semibold text-amber-100">Qualified rows are hidden by default.</span>{" "}
            Rows carrying RAMP, RAMPED, or LOW O2 qualifiers are excluded unless you explicitly
            include them. They are experiment qualifiers, not blanks and not zeros. Missing numeric
            values are rendered as “—” and are never treated as zero.
          </p>
        </div>
      </section>

      {facetData ? (
        <GasFlameFacetsPanel facets={facetData} />
      ) : facets.isError ? (
        <p className="rounded-lg border border-amber-400/20 bg-warning-soft p-2.5 text-[11px] text-amber-100">
          Facet coverage could not be loaded. The row table below is unaffected; no facet values
          are inferred locally.
        </p>
      ) : null}

      <FilterBar
        label="Gas-flame filters"
        actions={
          <FilterActions
            onClear={() => {
              setDraftState(null);
              clearParams();
            }}
            resultLabel={
              gas.isFetching && !gas.isPending
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
        <div>
          <label htmlFor="gas-accession" className="mb-1 block text-[11px] font-medium text-ink-300">
            Accession
          </label>
          <select
            id="gas-accession"
            value={form.accession}
            onChange={(event) => setField("accession", event.target.value)}
            className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 focus:border-cyan-400/60 focus-ring"
          >
            <option value="">Both accessions</option>
            <option value="PSI-10">PSI-10 (pressure in atm)</option>
            <option value="PSI-159">PSI-159 (pressure in bar)</option>
          </select>
          <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
            Select one accession to enable pressure filters. Units are not mixed.
          </p>
        </div>

        <TextFilter
          id="gas-flame-type"
          label="Flame configuration (exact label)"
          value={form.flame_type}
          onChange={(value) => setField("flame_type", value)}
          placeholder="Normal, Inverse, inverse…"
          hint="Case is preserved; matching is exact."
          list="gas-flame-options"
        />
        <TextFilter
          id="gas-fuel"
          label="Fuel label"
          value={form.fuel}
          onChange={(value) => setField("fuel", value)}
          placeholder="e.g. ethane, C2H4, 30% butane"
          hint="Case-insensitive exact label, not chemistry-normalized."
          list="gas-fuel-options"
        />
        <TextFilter
          id="gas-oxygen-min"
          label="Oxygen mole fraction ≥"
          type="number"
          min={0}
          max={1}
          step={0.001}
          value={form.oxygen_min}
          onChange={(value) => setField("oxygen_min", value)}
          placeholder="0.00"
        />
        <TextFilter
          id="gas-oxygen-max"
          label="Oxygen mole fraction ≤"
          type="number"
          min={0}
          max={1}
          step={0.001}
          value={form.oxygen_max}
          onChange={(value) => setField("oxygen_max", value)}
          placeholder="1.00"
        />
        <TextFilter
          id="gas-pressure-min"
          label={`Pressure ≥${form.accession ? ` (${form.accession === "PSI-10" ? "atm" : "bar"})` : ""}`}
          type="number"
          step={0.01}
          value={form.pressure_min}
          onChange={(value) => setField("pressure_min", value)}
          placeholder={pressureEnabled ? "0.0" : "Select accession"}
          hint={pressureEnabled ? undefined : "PSI-10 uses atm; PSI-159 uses bar."}
          disabled={!pressureEnabled}
        />
        <TextFilter
          id="gas-pressure-max"
          label={`Pressure ≤${form.accession ? ` (${form.accession === "PSI-10" ? "atm" : "bar"})` : ""}`}
          type="number"
          step={0.01}
          value={form.pressure_max}
          onChange={(value) => setField("pressure_max", value)}
          placeholder={pressureEnabled ? "2.0" : "Select accession"}
          disabled={!pressureEnabled}
        />
        <TextFilter
          id="gas-hot-ignition"
          label="Hot ignition (exact label)"
          value={form.hot_ignition}
          onChange={(value) => setField("hot_ignition", value)}
          placeholder="Yes, No, flash…"
          hint="Case is preserved; matching is exact."
          list="gas-ignition-options"
        />
        <TextFilter
          id="gas-extinction"
          label="Extinction mode (exact label)"
          value={form.extinction_mode}
          onChange={(value) => setField("extinction_mode", value)}
          placeholder="SE or FT"
          list="gas-extinction-options"
        />
        <TextFilter
          id="gas-tfp"
          label="TFP flag (exact label)"
          value={form.tfp}
          onChange={(value) => setField("tfp", value)}
          placeholder="Yes or No"
          hint="TFP values remain unexpanded."
          list="gas-tfp-options"
        />
        <div>
          <label htmlFor="gas-sort" className="mb-1 block text-[11px] font-medium text-ink-300">
            Sort field
          </label>
          <select
            id="gas-sort"
            value={form.sort}
            onChange={(event) => setField("sort", event.target.value)}
            className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 focus:border-cyan-400/60 focus-ring"
          >
            <option value="source_row">Source row</option>
            <option value="oxygen_mole_fraction">Oxygen mole fraction</option>
            <option value="peak_burner_temp_c">Peak burner temperature (°C)</option>
            <option value="observation_id">Observation ID</option>
            {form.accession ? <option value="pressure">Pressure ({form.accession === "PSI-10" ? "atm" : "bar"})</option> : null}
          </select>
        </div>
        <div>
          <label htmlFor="gas-order" className="mb-1 block text-[11px] font-medium text-ink-300">
            Sort direction
          </label>
          <select
            id="gas-order"
            value={form.order}
            onChange={(event) => setField("order", event.target.value === "desc" ? "desc" : "asc")}
            className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 focus:border-cyan-400/60 focus-ring"
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
        <div className="flex items-start gap-2 rounded-lg border border-navy-700/70 bg-navy-950/50 p-2.5 sm:col-span-2">
          <input
            id="gas-include-qualified"
            type="checkbox"
            checked={form.include_qualified}
            onChange={(event) => setField("include_qualified", event.target.checked)}
            className="mt-0.5 size-4 rounded border-navy-500 bg-navy-900 text-cyan-400 focus:ring-cyan-400"
          />
          <div>
            <label htmlFor="gas-include-qualified" className="cursor-pointer text-[11px] font-medium text-ink-200">
              Include rows with RAMP / RAMPED / LOW O2 qualifiers
            </label>
            <p className="mt-0.5 text-[10px] leading-relaxed text-ink-500">
              Qualified rows remain flagged. They are not converted into fixed set points.
            </p>
          </div>
        </div>
      </FilterBar>

      <datalist id="gas-fuel-options">
        {(facetData?.fuel ?? []).map((facet) => (
          <option key={facet.value} value={facet.value} label={`${facet.value} (${facet.count})`} />
        ))}
      </datalist>
      <datalist id="gas-flame-options">
        {(facetData?.flame_type ?? []).map((facet) => (
          <option key={facet.value} value={facet.value} label={`${facet.value} (${facet.count})`} />
        ))}
      </datalist>
      <datalist id="gas-ignition-options">
        {(facetData?.hot_ignition ?? []).map((facet) => (
          <option key={facet.value} value={facet.value} label={`${facet.value} (${facet.count})`} />
        ))}
      </datalist>
      <datalist id="gas-extinction-options">
        {(facetData?.extinction_mode ?? []).map((facet) => (
          <option key={facet.value} value={facet.value} label={`${facet.value} (${facet.count})`} />
        ))}
      </datalist>
      <datalist id="gas-tfp-options">
        {(facetData?.tfp ?? []).map((facet) => (
          <option key={facet.value} value={facet.value} label={`${facet.value} (${facet.count})`} />
        ))}
      </datalist>

      {gas.isPending ? (
        <LoadingState label="Loading gas-flame rows…" rows={5} />
      ) : gas.isError ? (
        <ErrorState
          error={gas.error}
          title="Gas-flame rows could not be loaded"
          onRetry={() => gas.refetch()}
        >
          <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
            Pressure filters require an explicit accession. Oxygen bounds must be ordered low to
            high.
          </p>
        </ErrorState>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No gas-flame rows match these filters"
          description="No row is synthesized or interpolated to fill the table. Clear the filters or widen the oxygen/pressure bounds."
          icon={<Flame className="size-6" aria-hidden="true" />}
          action={
            <button type="button" className={buttonStyles()} onClick={() => clearParams()}>
              Clear filters
            </button>
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
            <Info className="size-3.5 text-cyan-300" aria-hidden="true" />
            <span>Row click opens full record fields and source identity.</span>
            {pressureField ? (
              <Badge tone="outline" className="font-mono">
                pressure filter field: {pressureField} ({pressureUnit})
              </Badge>
            ) : (
              <Badge tone="amber">Mixed pressure units: choose an accession before pressure filtering</Badge>
            )}
          </div>
          <TableShell caption="Gas-flame test rows with source labels, measured values, computed fields, quality flags, and provenance">
            <thead>
              <tr>
                <th scope="col" className={TH_CLASS}>Test / accession</th>
                <th scope="col" className={TH_CLASS}>Configuration</th>
                <th scope="col" className={TH_CLASS}>Fuel (as labeled)</th>
                <th scope="col" className={TH_CLASS}>O₂ mole fraction</th>
                <th scope="col" className={TH_CLASS}>Pressure initial (atm)</th>
                <th scope="col" className={TH_CLASS}>Pressure as labeled (bar)</th>
                <th scope="col" className={TH_CLASS}>
                  <span className="flex items-center gap-1">Tad (K) <ValueKindBadge valueKind="computed" /></span>
                </th>
                <th scope="col" className={TH_CLASS}>
                  <span className="flex items-center gap-1">Zst <ValueKindBadge valueKind="computed" /></span>
                </th>
                <th scope="col" className={TH_CLASS}>Outcome</th>
                <th scope="col" className={TH_CLASS}>Row flags</th>
                <th scope="col" className={TH_CLASS}><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.observation_id} className="hover:bg-navy-800/35">
                  <td className={TD_CLASS}>
                    <p className="font-medium text-ink-100">{row.test_code ?? "no test code"}</p>
                    <p className="mt-0.5 text-[10px] text-ink-500">
                      {row.accession} · source row {row.source_row}
                    </p>
                  </td>
                  <td className={TD_CLASS}>
                    <span className="font-mono text-[11px] text-ink-200">{row.flame_type ?? "—"}</span>
                    <p className="mt-0.5 text-[10px] text-ink-500">Day {row.day ?? "—"}</p>
                  </td>
                  <td className={TD_CLASS}>{row.fuel ?? "—"}</td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.oxygen_mole_fraction === null ? "—" : formatNumber(row.oxygen_mole_fraction)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.pressure_initial_atm === null ? "—" : formatNumber(row.pressure_initial_atm)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.pressure_approx_bar === null ? "—" : formatNumber(row.pressure_approx_bar)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.adiabatic_flame_temp_k === null ? "—" : formatNumber(row.adiabatic_flame_temp_k)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.stoich_mixture_fraction === null ? "—" : formatNumber(row.stoich_mixture_fraction)}
                  </td>
                  <td className={TD_CLASS}>
                    <p className="text-[11px] text-ink-200">Ignition: {row.hot_ignition ?? "—"}</p>
                    <p className="text-[10px] text-ink-500">Extinction: {row.extinction_mode ?? "—"}</p>
                  </td>
                  <td className={TD_CLASS}>
                    <RowQualityFlags flags={row.quality_flags} />
                  </td>
                  <td className={TD_CLASS}>
                    <button
                      type="button"
                      onClick={() => setSelectedRow(row)}
                      className="whitespace-nowrap text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                      aria-label={`Open record for row ${row.test_code ?? row.observation_id}`}
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
            label="gas-flame rows"
          />
        </>
      )}

      <RecordDrawer
        open={selectedRow !== null}
        title={selectedRow ? `Test ${selectedRow.test_code ?? selectedRow.observation_id}` : "Gas-flame record"}
        subtitle={
          selectedRow ? (
            <span>
              {selectedRow.accession} · {selectedRow.flame_type ?? "configuration not stated"} ·{" "}
              source row {selectedRow.source_row}
            </span>
          ) : null
        }
        onClose={() => setSelectedRow(null)}
      >
        {selectedRow ? (
          <GasFlameRecord
            row={selectedRow}
            onOpenCitation={(id) => {
              setSelectedRow(null);
              setCitationId(id);
            }}
          />
        ) : null}
      </RecordDrawer>

      <CitationDrawer citationId={citationId} onClose={() => setCitationId(null)} />
    </div>
  );
}

function GasFlameRecord({
  row,
  onOpenCitation,
}: {
  row: GasFlameRow;
  onOpenCitation: (citationId: string) => void;
}) {
  const fields = [
    { key: "test_code", value: row.test_code },
    { key: "flame_type", value: row.flame_type },
    { key: "day", value: row.day },
    { key: "fuel", value: row.fuel },
    { key: "oxygen_mole_fraction", value: row.oxygen_mole_fraction },
    { key: "oxygen_mole_fraction_initial", value: row.oxygen_mole_fraction_initial },
    { key: "oxygen_mole_fraction_final", value: row.oxygen_mole_fraction_final },
    { key: "pressure_initial_atm", value: row.pressure_initial_atm, unit: "atm" },
    { key: "pressure_final_atm", value: row.pressure_final_atm, unit: "atm" },
    { key: "pressure_mean_atm", value: row.pressure_mean_atm, unit: "atm" },
    { key: "pressure_approx_bar", value: row.pressure_approx_bar, unit: "bar (as labeled)" },
    { key: "fuel_mass_flow_mg_s", value: row.fuel_mass_flow_mg_s, unit: "mg/s" },
    { key: "diluent_mass_flow_mg_s", value: row.diluent_mass_flow_mg_s, unit: "mg/s" },
    { key: "total_mass_flow_mg_s", value: row.total_mass_flow_mg_s, unit: "mg/s" },
    { key: "oxidizer_mass_flow_mg_s", value: row.oxidizer_mass_flow_mg_s, unit: "mg/s" },
    { key: "fuel_burn_rate_mg_s", value: row.fuel_burn_rate_mg_s, unit: "mg/s" },
    { key: "hot_ignition", value: row.hot_ignition },
    { key: "extinction_mode", value: row.extinction_mode },
    { key: "burn_time_s", value: row.burn_time_s, unit: "s" },
    { key: "peak_burner_temp_c", value: row.peak_burner_temp_c, unit: "°C" },
    { key: "peak_burner_temp_k", value: row.peak_burner_temp_k, unit: "K" },
    { key: "tfp_flag", value: row.tfp_flag },
    { key: "cool_flame_flag", value: row.cool_flame_flag },
    { key: "color", value: row.color },
    { key: "comments", value: row.comments },
  ];
  return (
    <div className="space-y-4">
      <DetailSection
        title="Computed fields"
        description="The source registry marks these fields as computed. They are not measurements."
      >
        <div className="flex flex-wrap gap-2">
          <ValueKindBadge valueKind="computed" />
          {row.computed_fields.map((field) => (
            <Badge key={field} tone="violet">{fieldLabel(field)}</Badge>
          ))}
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
          <div>
            <dt className="text-ink-500">Adiabatic flame temperature</dt>
            <dd className="font-mono text-ink-200">
              {row.adiabatic_flame_temp_k === null ? "—" : `${formatNumber(row.adiabatic_flame_temp_k)} K`}
            </dd>
          </div>
          <div>
            <dt className="text-ink-500">Stoichiometric mixture fraction</dt>
            <dd className="font-mono text-ink-200">
              {row.stoich_mixture_fraction === null ? "—" : formatNumber(row.stoich_mixture_fraction)}
            </dd>
          </div>
        </dl>
      </DetailSection>

      <DetailSection title="Recorded conditions and outcomes">
        <FieldGrid fields={fields} columns={2} />
      </DetailSection>

      <DetailSection title="Row quality flags" description="Flags are preserved exactly as returned by the API.">
        <RowQualityFlags flags={row.quality_flags} />
      </DetailSection>

      <DetailSection title="Source identity">
        <FieldGrid
          fields={[
            { key: "observation_id", value: row.observation_id },
            { key: "table_id", value: row.table_id },
            { key: "source_file", value: row.source_file },
            { key: "source_sheet", value: row.source_sheet },
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
            sheet={row.source_sheet}
            row={row.source_row}
          />
          <div className="mt-2">
            <CitationButton citationId={row.citation_id} onClick={onOpenCitation} />
          </div>
        </div>
      </DetailSection>
    </div>
  );
}

export default function GasFlamePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading gas-flame explorer…" rows={5} />}>
      <GasFlameContent />
    </Suspense>
  );
}
