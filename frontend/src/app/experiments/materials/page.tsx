"use client";

import { Suspense, useMemo, useState } from "react";
import { AlertTriangle, FlaskConical, Info } from "lucide-react";
import { useMaterialTests } from "@/lib/api/hooks";
import type { MaterialRow } from "@/lib/api/types";
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
import { CitationButton, CitationDrawer } from "@/components/scientific/citation-drawer";

const PAGE_SIZE = 25;

interface MaterialForm {
  accession: string;
  material: string;
  flow_restrictor: string;
  o2_min: string;
  o2_max: string;
}

function formFromParams(get: (key: string, fallback?: string) => string | undefined): MaterialForm {
  return {
    accession: get("accession") ?? "",
    material: get("material") ?? "",
    flow_restrictor: get("flow_restrictor") ?? "",
    o2_min: get("o2_min") ?? "",
    o2_max: get("o2_max") ?? "",
  };
}

function MaterialsContent() {
  const { get, setParams, clearParams } = useUrlState();
  const applied = useMemo(() => formFromParams(get), [get]);
  const appliedKey = useMemo(() => JSON.stringify(applied), [applied]);
  const [draftState, setDraftState] = useState<{ key: string; value: MaterialForm } | null>(null);
  const form = draftState?.key === appliedKey ? draftState.value : applied;
  const [selectedRow, setSelectedRow] = useState<MaterialRow | null>(null);
  const [citationId, setCitationId] = useState<string | null>(null);

  const offset = Number(get("offset") ?? 0) || 0;
  const o2Enabled = Boolean(form.accession);
  const o2Column = form.accession === "PSI-25" ? "initial_o2_pct" : form.accession === "PSI-26" ? "o2_pct" : null;

  const material = useMaterialTests({
    accession: applied.accession || undefined,
    material: applied.material || undefined,
    flow_restrictor: applied.flow_restrictor || undefined,
    o2_min: applied.accession && applied.o2_min ? Number(applied.o2_min) : undefined,
    o2_max: applied.accession && applied.o2_max ? Number(applied.o2_max) : undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const page = material.data?.meta.page;
  const total = page?.total ?? 0;
  const o2Note = page?.o2_unit_note ?? null;
  const rows = material.data?.data ?? [];

  const setField = <K extends keyof MaterialForm>(key: K, value: MaterialForm[K]) => {
    const next = { ...form, [key]: value };
    if (key === "accession" && value !== form.accession) {
      next.o2_min = "";
      next.o2_max = "";
    }
    setDraftState({ key: appliedKey, value: next });
  };

  const applyFilters = () => {
    setParams({
      accession: form.accession || null,
      material: form.material.trim() || null,
      flow_restrictor: form.flow_restrictor.trim() || null,
      o2_min: form.accession && form.o2_min.trim() ? form.o2_min.trim() : null,
      o2_max: form.accession && form.o2_max.trim() ? form.o2_max.trim() : null,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Experiment explorer · Materials"
        title="PSI-25 and PSI-26 material test matrices"
        description={
          <>
            As-run material records. Material names are free text and are not normalized. Oxygen
            columns differ by accession, and no BASS flame-spread rate is published in these tables.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} rows</Badge>
            <Badge tone="neutral">Page size {PAGE_SIZE}</Badge>
            {applied.accession ? <Badge tone="violet">{applied.accession}</Badge> : null}
            <Badge tone="amber">No spread rate available</Badge>
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3.5">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-amber-100">Oxygen columns are not interchangeable.</p>
            <p className="mt-1">
              PSI-25 uses <span className="mono">initial_o2_pct</span> and{" "}
              <span className="mono">final_o2_pct</span>. PSI-26 uses an{" "}
              <span className="mono">o2_pct</span> header that says percent while observed values are
              around 0.22. The value is preserved as labeled and is not relabeled or converted.
            </p>
            {o2Note ? <p className="mt-1 text-amber-200">{o2Note}</p> : null}
          </div>
        </div>
      </section>

      <FilterBar
        label="Material filters"
        actions={
          <FilterActions
            onClear={() => {
              setDraftState(null);
              clearParams();
            }}
            resultLabel={
              material.isFetching && !material.isPending
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
          <label htmlFor="material-accession" className="mb-1 block text-[11px] font-medium text-ink-300">
            Accession
          </label>
          <select
            id="material-accession"
            value={form.accession}
            onChange={(event) => setField("accession", event.target.value)}
            className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 focus:border-cyan-400/60 focus-ring"
          >
            <option value="">Both accessions</option>
            <option value="PSI-25">PSI-25 (BASS-II)</option>
            <option value="PSI-26">PSI-26 (BASS)</option>
          </select>
          <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
            Select one accession to enable oxygen filters.
          </p>
        </div>
        <TextFilter
          id="material-name"
          label="Material (free-text substring)"
          value={form.material}
          onChange={(value) => setField("material", value)}
          placeholder="e.g. SIBAL, PMMA, rod"
          hint="Case-insensitive substring search. Labels are not normalized."
        />
        <TextFilter
          id="material-flow"
          label="Flow restrictor (exact label)"
          value={form.flow_restrictor}
          onChange={(value) => setField("flow_restrictor", value)}
          placeholder="e.g. 0, 1, 2"
        />
        <TextFilter
          id="material-o2-min"
          label={`Oxygen ≥${form.accession ? ` (${form.accession === "PSI-25" ? "initial O₂ %" : "o2_pct, as labeled"})` : ""}`}
          type="number"
          step={0.01}
          value={form.o2_min}
          onChange={(value) => setField("o2_min", value)}
          placeholder={o2Enabled ? "0.0" : "Select accession"}
          hint={o2Enabled ? `Filter field: ${o2Column}` : "Different columns and units per accession."}
          disabled={!o2Enabled}
        />
        <TextFilter
          id="material-o2-max"
          label={`Oxygen ≤${form.accession ? ` (${form.accession === "PSI-25" ? "initial O₂ %" : "o2_pct, as labeled"})` : ""}`}
          type="number"
          step={0.01}
          value={form.o2_max}
          onChange={(value) => setField("o2_max", value)}
          placeholder={o2Enabled ? "30.0" : "Select accession"}
          disabled={!o2Enabled}
        />
      </FilterBar>

      {material.isPending ? (
        <LoadingState label="Loading material rows…" rows={5} />
      ) : material.isError ? (
        <ErrorState
          error={material.error}
          title="Material rows could not be loaded"
          onRetry={() => material.refetch()}
        >
          <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
            Oxygen filters require an explicit accession. Bounds must be ordered low to high.
          </p>
        </ErrorState>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No material rows match these filters"
          description="No row is synthesized to fill the table. Clear the filters or widen the oxygen bounds."
          icon={<FlaskConical className="size-6" aria-hidden="true" />}
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
            <span>Row-level sentinels such as -1 and “none” are preserved as flags, not converted to zero.</span>
            {o2Column ? <Badge tone="outline" className="font-mono">O₂ filter field: {o2Column}</Badge> : null}
          </div>
          <TableShell caption="Material test rows with free-text material labels, as-labeled oxygen and gas concentrations, quality flags, and provenance">
            <thead>
              <tr>
                <th scope="col" className={TH_CLASS}>Test / accession</th>
                <th scope="col" className={TH_CLASS}>Material (as labeled)</th>
                <th scope="col" className={TH_CLASS}>Flow restrictor</th>
                <th scope="col" className={TH_CLASS}>Initial O₂ %</th>
                <th scope="col" className={TH_CLASS}>Final O₂ %</th>
                <th scope="col" className={TH_CLASS}>O₂ % header (ambiguous)</th>
                <th scope="col" className={TH_CLASS}>Initial / final CO₂ %</th>
                <th scope="col" className={TH_CLASS}>Initial / final CO ppm</th>
                <th scope="col" className={TH_CLASS}>Pressure (atm)</th>
                <th scope="col" className={TH_CLASS}>Row flags</th>
                <th scope="col" className={TH_CLASS}><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.observation_id} className="hover:bg-navy-800/35">
                  <td className={TD_CLASS}>
                    <p className="font-medium text-ink-100">{row.test_no ?? row.as_run_test_no ?? "no test number"}</p>
                    <p className="mt-0.5 text-[10px] text-ink-500">
                      {row.accession} · sample {row.sample_no ?? "—"} · {row.record_type}
                    </p>
                  </td>
                  <td className={TD_CLASS}>
                    <span className="text-[11px] text-ink-200">{row.material ?? "—"}</span>
                    <p className="mt-0.5 text-[10px] text-ink-500">Not normalized</p>
                  </td>
                  <td className={`${TD_CLASS} font-mono text-ink-200`}>{row.flow_restrictor ?? "—"}</td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.initial_o2_pct === null ? "—" : formatNumber(row.initial_o2_pct)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.final_o2_pct === null ? "—" : formatNumber(row.final_o2_pct)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-amber-200`}>
                    {row.o2_pct === null ? "—" : formatNumber(row.o2_pct)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {formatNumber(row.initial_co2_pct)} / {formatNumber(row.final_co2_pct)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {formatNumber(row.initial_co_ppm)} / {formatNumber(row.final_co_ppm)}
                  </td>
                  <td className={`${TD_CLASS} font-mono tabular-nums text-ink-200`}>
                    {row.pressure_atm === null ? "—" : formatNumber(row.pressure_atm)}
                  </td>
                  <td className={TD_CLASS}>
                    <RowQualityFlags flags={row.quality_flags} />
                  </td>
                  <td className={TD_CLASS}>
                    <button
                      type="button"
                      onClick={() => setSelectedRow(row)}
                      className="whitespace-nowrap text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                      aria-label={`Open record for material row ${row.test_no ?? row.observation_id}`}
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
            label="material rows"
          />
        </>
      )}

      <RecordDrawer
        open={selectedRow !== null}
        title={selectedRow ? `Material test ${selectedRow.test_no ?? selectedRow.as_run_test_no ?? selectedRow.observation_id}` : "Material record"}
        subtitle={selectedRow ? `${selectedRow.accession} · ${selectedRow.material ?? "material not stated"}` : null}
        onClose={() => setSelectedRow(null)}
      >
        {selectedRow ? (
          <MaterialRecord
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

function MaterialRecord({
  row,
  onOpenCitation,
}: {
  row: MaterialRow;
  onOpenCitation: (citationId: string) => void;
}) {
  return (
    <div className="space-y-4">
      <DetailSection
        title="As-labeled values"
        description="Oxygen and gas concentrations are shown under their original column meaning. No unit conversion is applied."
      >
        <FieldGrid
          fields={[
            { key: "test_date", value: row.test_date },
            { key: "gmt_day", value: row.gmt_day },
            { key: "as_run_test_no", value: row.as_run_test_no },
            { key: "test_no", value: row.test_no },
            { key: "sample_no", value: row.sample_no },
            { key: "record_type", value: row.record_type },
            { key: "material", value: row.material },
            { key: "flow_restrictor", value: row.flow_restrictor },
            { key: "fan_display", value: row.fan_display },
            { key: "air_display", value: row.air_display },
            { key: "radiometer_gain", value: row.radiometer_gain },
            { key: "total_frames", value: row.total_frames },
            { key: "initial_o2_pct", value: row.initial_o2_pct, unit: "% as labeled" },
            { key: "final_o2_pct", value: row.final_o2_pct, unit: "% as labeled" },
            { key: "o2_pct", value: row.o2_pct, unit: "% header; ambiguous" },
            { key: "initial_co2_pct", value: row.initial_co2_pct, unit: "% as labeled" },
            { key: "final_co2_pct", value: row.final_co2_pct, unit: "% as labeled" },
            { key: "initial_co_ppm", value: row.initial_co_ppm, unit: "ppm as labeled" },
            { key: "final_co_ppm", value: row.final_co_ppm, unit: "ppm as labeled" },
            { key: "pressure_atm", value: row.pressure_atm, unit: "atm" },
            { key: "co2_mm_hg", value: row.co2_mm_hg, unit: "mmHg" },
            { key: "observations", value: row.observations },
          ]}
          columns={2}
        />
      </DetailSection>

      <DetailSection title="Row quality flags" description="Sentinels and not-measured tokens remain visible; they are not zeros.">
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

export default function MaterialsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading material explorer…" rows={5} />}>
      <MaterialsContent />
    </Suspense>
  );
}
