"use client";

import { BarChart3, Info, Layers } from "lucide-react";
import type { FacetNumericGroup, FacetValue, GasFlameFacets } from "@/lib/api/types";
import { formatCount, formatNumber } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "@/components/ui/disclosure";

function FacetValueList({
  title,
  values,
  emptyNote,
}: {
  title: string;
  values: FacetValue[];
  emptyNote: string;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.08em] text-muted-2">{title}</p>
      {values.length === 0 ? (
        <p className="mt-1.5 text-[11px] text-muted">{emptyNote}</p>
      ) : (
        <ul className="mt-1.5 space-y-1.5">
          {values.map((value) => (
            <li
              key={value.value}
              className="rounded-lg border border-border/60 bg-background/35 px-2.5 py-1.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="break-all font-mono text-[11px] text-text-soft">{value.value}</span>
                <span className="text-[10px] text-muted">{formatCount(value.count)} rows</span>
              </div>
              <p className="mt-0.5 text-[10px] text-muted-2">
                {Object.entries(value.by_accession)
                  .map(([accession, count]) => `${accession}: ${formatCount(count)}`)
                  .join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NumericFacetGroup({ group }: { group: FacetNumericGroup }) {
  return (
    <li className="rounded-lg border border-border/60 bg-background/35 p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-text-soft">{group.accession}</span>
        <Badge tone="outline">{group.unit}</Badge>
      </div>
      <p className="mt-1 text-[11px] text-muted">
        {formatCount(group.count)} values · {formatCount(group.missing_count)} missing
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-2">
        {group.field} · {group.min === null ? "—" : formatNumber(group.min)} to{" "}
        {group.max === null ? "—" : formatNumber(group.max)} {group.unit}
      </p>
      {group.histogram.length > 0 ? (
        <div className="mt-2">
          <p className="text-[10px] uppercase tracking-[0.08em] text-muted-2">Histogram bins</p>
          <ul className="mt-1 flex flex-wrap gap-1">
            {group.histogram.map((bin) => (
              <li
                key={`${bin.min}-${bin.max}`}
                className="rounded border border-border-strong bg-surface-2/60 px-1.5 py-0.5 font-mono text-[10px] text-muted"
                title={`${bin.min} to ${bin.max} ${group.unit}: ${bin.count} rows`}
              >
                {formatNumber(bin.min)}–{formatNumber(bin.max)}: {formatCount(bin.count)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}

export function GasFlameFacetsPanel({ facets }: { facets: GasFlameFacets }) {
  return (
    <section className="surface p-5 sm:p-6" aria-labelledby="gas-flame-facets">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="gas-flame-facets"
            className="flex items-center gap-2 text-[15px] font-semibold text-foreground"
          >
            <BarChart3 className="size-4 text-accent-strong" aria-hidden="true" />
            Facet coverage from the API
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted">
            Counts and ranges are computed from canonical gas-flame rows, not from this browser
            page. Pressure and oxygen ranges stay separate per accession so atm and bar values are
            never combined.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="cyan">
            {formatCount(
              facets.accessions.reduce((sum, item) => sum + item.included_rows, 0),
            )}{" "}
            included rows
          </Badge>
          {facets.excluded_qualified_rows > 0 ? (
            <Badge tone="amber">
              {formatCount(facets.excluded_qualified_rows)} qualified rows excluded
            </Badge>
          ) : null}
          <Badge tone={facets.include_qualified ? "violet" : "neutral"}>
            {facets.include_qualified ? "qualified rows included" : "qualified rows excluded"}
          </Badge>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse text-left text-[11px]">
          <caption className="sr-only">
            Gas-flame facet row counts by accession and qualified-row exclusion
          </caption>
          <thead>
            <tr className="border-b border-border/70">
              <th scope="col" className="px-2 py-1.5 font-medium text-muted">Accession</th>
              <th scope="col" className="px-2 py-1.5 font-medium text-muted">Total rows</th>
              <th scope="col" className="px-2 py-1.5 font-medium text-muted">Included</th>
              <th scope="col" className="px-2 py-1.5 font-medium text-muted">Excluded qualifiers</th>
            </tr>
          </thead>
          <tbody>
            {facets.accessions.map((item) => (
              <tr key={item.accession} className="border-b border-border/40 last:border-0">
                <td className="px-2 py-1.5 font-mono text-text-soft">{item.accession}</td>
                <td className="px-2 py-1.5 font-mono text-muted">{formatCount(item.total_rows)}</td>
                <td className="px-2 py-1.5 font-mono text-muted">{formatCount(item.included_rows)}</td>
                <td className="px-2 py-1.5 font-mono text-muted">
                  {formatCount(item.excluded_qualified_rows)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <FacetValueList
          title="Flame configuration"
          values={facets.flame_type}
          emptyNote="No flame-configuration value is present in the selected scope."
        />
        <FacetValueList
          title="Fuel label"
          values={facets.fuel}
          emptyNote="No fuel label is present in the selected scope."
        />
        <FacetValueList
          title="Hot ignition"
          values={facets.hot_ignition}
          emptyNote="No hot-ignition value is present in the selected scope."
        />
        <FacetValueList
          title="Extinction mode"
          values={facets.extinction_mode}
          emptyNote="No extinction-mode value is present in the selected scope."
        />
        <FacetValueList
          title="TFP flag"
          values={facets.tfp}
          emptyNote="No TFP value is present in the selected scope."
        />
        <div>
          <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.08em] text-muted-2">
            <Layers className="size-3" aria-hidden="true" />
            Pressure range
          </p>
          {facets.pressure.by_accession.length === 0 ? (
            <p className="mt-1.5 text-[11px] text-muted">No pressure values were returned.</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {facets.pressure.by_accession.map((group) => (
                <NumericFacetGroup key={`${group.accession}-${group.field}`} group={group} />
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-4">
        <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.08em] text-muted-2">
          <Layers className="size-3" aria-hidden="true" />
          Oxygen mole fraction range
        </p>
        {facets.oxygen.by_accession.length === 0 ? (
          <p className="mt-1.5 text-[11px] text-muted">No oxygen values were returned.</p>
        ) : (
          <ul className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
            {facets.oxygen.by_accession.map((group) => (
              <NumericFacetGroup key={`${group.accession}-${group.field}`} group={group} />
            ))}
          </ul>
        )}
      </div>

      {facets.notes.length > 0 ? (
        <Disclosure summary="Facet notes and exclusions" className="mt-4">
          <ul className="space-y-1.5">
            {facets.notes.map((note) => (
              <li key={note} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-muted">
                <Info className="mt-0.5 size-3 shrink-0 text-accent-strong" aria-hidden="true" />
                {note}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </section>
  );
}
