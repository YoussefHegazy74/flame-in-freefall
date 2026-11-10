"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, BookOpen, CheckCircle2, FileQuestion, Info, ShieldQuestion } from "lucide-react";
import type { DatasetField } from "@/lib/api/types";
import { useDatasetFields } from "@/lib/api/hooks";
import { formatCount, formatUnit, humanizeKey } from "@/lib/format";
import { fieldLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "@/components/ui/disclosure";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, SelectFilter } from "@/components/ui/filter";
import { ComparisonStateBadge, ServingStateBadge } from "./state-badge";
import { ValueKindBadge } from "./unit-label";

function integrityTone(status: string): "emerald" | "rose" | "amber" | "neutral" {
  if (status === "available") return "emerald";
  if (status === "missing") return "rose";
  if (status === "not_checked") return "neutral";
  return "amber";
}

function IntegrityStatusIcon({ status }: { status: string }) {
  if (status === "available") {
    return <CheckCircle2 className="size-3.5" aria-hidden="true" />;
  }
  if (status === "missing") {
    return <AlertTriangle className="size-3.5" aria-hidden="true" />;
  }
  if (status === "not_checked") {
    return <FileQuestion className="size-3.5" aria-hidden="true" />;
  }
  return <ShieldQuestion className="size-3.5" aria-hidden="true" />;
}

function FieldCard({ field }: { field: DatasetField }) {
  const presence = field.integrity;

  return (
    <li className="surface-flat p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-ink-100">{fieldLabel(field.canonical_name)}</h3>
            <ValueKindBadge valueKind={field.value_kind} />
            <ComparisonStateBadge status={field.comparability.status} showIcon={false} />
            <ServingStateBadge state={field.serving_state} showIcon={false} />
          </div>
          <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">{field.field_id}</p>
          <p className="mt-2 max-w-3xl text-[11px] leading-relaxed text-ink-300">{field.description}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Unit</p>
          <p className="font-mono text-xs text-ink-200">{formatUnit(field.unit)}</p>
          <p className="mt-0.5 text-[10px] text-ink-500">{field.unit_status.replace(/_/g, " ")}</p>
        </div>
      </div>

      {field.flags.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={`Flags for ${field.canonical_name}`}>
          {field.flags.map((flag) => (
            <li
              key={flag}
              className="rounded border border-amber-400/20 bg-amber-400/5 px-1.5 py-0.5 font-mono text-[10px] text-amber-200"
            >
              {flag}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 grid gap-3 text-[11px] sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
          <p className="text-ink-500">Canonical presence</p>
          <p className="mt-1 flex items-center gap-1.5 text-ink-200">
            <IntegrityStatusIcon status={presence.status} />
            <Badge tone={integrityTone(presence.status)}>{presence.status.replace(/_/g, " ")}</Badge>
          </p>
          <p className="mt-1 font-mono text-[10px] text-ink-400">
            {presence.checked
              ? `${formatCount(presence.non_null_count)} / ${formatCount(presence.total_rows)} non-null`
              : presence.reason ?? "presence not checked"}
          </p>
          {presence.table ? (
            <p className="mt-0.5 font-mono text-[10px] text-ink-500">
              {presence.table}.{presence.field}
            </p>
          ) : null}
        </div>
        <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
          <p className="text-ink-500">Calibration</p>
          <p className="mt-1 text-ink-200">{field.calibration.status.replace(/_/g, " ")}</p>
          {field.calibration.note ? (
            <p className="mt-1 text-[10px] leading-relaxed text-ink-400">{field.calibration.note}</p>
          ) : null}
        </div>
        <div className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
          <p className="text-ink-500">Missingness policy</p>
          <p className="mt-1 leading-relaxed text-ink-300">{field.missingness.policy}</p>
        </div>
      </div>

      {field.alternatives.length > 0 ? (
        <div className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-2.5">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-100">
            <AlertTriangle className="size-3.5" aria-hidden="true" />
            Documented alternative, not an automatic substitute
          </p>
          <ul className="mt-1.5 space-y-1.5">
            {field.alternatives.map((alternative) => (
              <li key={alternative.canonical_field} className="text-[11px] leading-relaxed text-ink-300">
                <span className="font-mono text-ink-200">{alternative.canonical_field}</span>{" "}
                <span className="text-ink-500">({formatUnit(alternative.unit)})</span> — {alternative.description}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <Disclosure summary="Source columns, comparability rules, and references" className="mt-3">
        <div className="space-y-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Verified source columns</p>
            {field.source_columns.length === 0 ? (
              <p className="mt-1 text-[11px] text-ink-400">
                No verified source-column mapping was recorded for this field.
              </p>
            ) : (
              <ul className="mt-1.5 space-y-1.5">
                {field.source_columns.map((column) => (
                  <li
                    key={`${column.raw_column}-${column.source_file}`}
                    className="rounded-lg border border-navy-700/60 bg-navy-950/40 p-2 text-[11px]"
                  >
                    <span className="font-mono text-ink-200">{column.raw_column}</span>
                    <span className="text-ink-500"> · {column.applies_to}</span>
                    <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">{column.source_file}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Comparability rules</p>
            {field.comparability.rules.length === 0 ? (
              <p className="mt-1 text-[11px] text-ink-400">No comparison rule references this field.</p>
            ) : (
              <ul className="mt-1.5 space-y-2">
                {field.comparability.rules.map((rule) => (
                  <li key={rule.rule_id} className="rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] text-ink-300">{rule.rule_id}</span>
                      <ComparisonStateBadge status={rule.status} showIcon={false} />
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-ink-300">
                      {rule.scientific_justification}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {field.missingness.restrictions.length > 0 ? (
            <div>
              <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Missingness restrictions</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {field.missingness.restrictions.map((restriction) => (
                  <li
                    key={restriction}
                    className="rounded border border-navy-600 bg-navy-800/70 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
                  >
                    {restriction}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Link
              href={`/compare?left=${encodeURIComponent(field.measurement_id)}`}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
            >
              Open comparison studio
              <ArrowUpRight className="size-3" aria-hidden="true" />
            </Link>
            <Link
              href={`/quality?dataset=${encodeURIComponent(field.dataset_id)}`}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
            >
              Review dataset limitations
              <ArrowUpRight className="size-3" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </Disclosure>
    </li>
  );
}

export function DatasetFieldsPanel({ datasetId }: { datasetId: string }) {
  const [valueKind, setValueKind] = useState("");
  const [comparisonStatus, setComparisonStatus] = useState("");
  const [physicalQuantity, setPhysicalQuantity] = useState("");
  const fields = useDatasetFields(datasetId, {
    value_kind: valueKind || undefined,
    comparison_status: comparisonStatus || undefined,
    physical_quantity: physicalQuantity || undefined,
    limit: 200,
  });
  const data = fields.data?.data;
  const items = data?.fields ?? [];
  const physicalQuantities = useMemo(() => {
    const values = new Set<string>();
    for (const field of data?.fields ?? []) values.add(field.physical_quantity);
    return Array.from(values).sort();
  }, [data?.fields]);
  const comparisonStatuses = useMemo(() => {
    const values = new Set<string>();
    for (const field of data?.fields ?? []) values.add(field.comparability.status);
    return Array.from(values).sort();
  }, [data?.fields]);

  return (
    <section className="surface p-5" aria-labelledby="dataset-fields">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="dataset-fields" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
            Field dictionary
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Canonical names, verified source columns, units, calibration, missingness, and
            comparability restrictions are returned by the backend. Descriptions are not inferred
            in the browser.
          </p>
        </div>
        {data ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="cyan">{formatCount(data.summary.field_count)} fields</Badge>
            <Badge tone="emerald">
              {formatCount(data.summary.with_canonical_values)} with canonical values
            </Badge>
            {data.summary.without_canonical_values > 0 ? (
              <Badge tone="rose">
                {formatCount(data.summary.without_canonical_values)} without canonical values
              </Badge>
            ) : null}
            {data.summary.presence_not_checked > 0 ? (
              <Badge tone="neutral">
                {formatCount(data.summary.presence_not_checked)} not checked
              </Badge>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        <FilterBar
          label="Field dictionary filters"
          actions={
            <p className="text-[11px] text-ink-400" aria-live="polite">
              {data ? `${items.length} of ${data.page.total} fields shown` : "Loading fields…"}
            </p>
          }
        >
          <SelectFilter
            id={`fields-kind-${datasetId}`}
            label="Value kind"
            value={valueKind}
            onChange={setValueKind}
            options={[
              { value: "measured", label: "Measured" },
              { value: "computed", label: "Computed" },
              { value: "raw", label: "Raw signal" },
              { value: "categorical", label: "Categorical" },
              { value: "derived", label: "Derived" },
            ]}
            placeholder="All value kinds"
          />
          <SelectFilter
            id={`fields-comparison-${datasetId}`}
            label="Comparability"
            value={comparisonStatus}
            onChange={setComparisonStatus}
            options={comparisonStatuses.map((value) => ({
              value,
              label: humanizeKey(value),
            }))}
            placeholder="All comparability states"
          />
          <SelectFilter
            id={`fields-quantity-${datasetId}`}
            label="Physical quantity"
            value={physicalQuantity}
            onChange={setPhysicalQuantity}
            options={physicalQuantities.map((value) => ({
              value,
              label: humanizeKey(value),
            }))}
            placeholder="All physical quantities"
          />
        </FilterBar>
      </div>

      {fields.isPending ? (
        <div className="mt-4">
          <LoadingState label="Loading field dictionary…" rows={3} />
        </div>
      ) : fields.isError ? (
        <div className="mt-4">
          <ErrorState
            error={fields.error}
            title="The field dictionary could not be loaded"
            onRetry={() => fields.refetch()}
          />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No field matches these filters"
            description="The registry is unchanged. Clear the value-kind, comparability, or physical-quantity filter. An empty list is not evidence that the dataset has no fields."
            icon={<Info className="size-6" aria-hidden="true" />}
          />
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((field) => (
            <FieldCard key={field.field_id} field={field} />
          ))}
        </ul>
      )}

      {data ? (
        <p className="mt-4 rounded-lg border border-cyan-400/15 bg-cyan-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          {formatCount(data.summary.with_verified_source_column)} of{" "}
          {formatCount(data.summary.field_count)} fields have a verified source-column mapping.
          Missing canonical values are reported explicitly; they are never zero-filled.
        </p>
      ) : null}
    </section>
  );
}
