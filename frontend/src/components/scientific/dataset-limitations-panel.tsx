"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import type { Limitation } from "@/lib/api/types";
import { useDatasetLimitations } from "@/lib/api/hooks";
import { formatCount, humanizeKey } from "@/lib/format";
import { labelForUse } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "@/components/ui/disclosure";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, SelectFilter } from "@/components/ui/filter";
import { SourceReferenceList } from "./provenance";

function severityTone(severity: string): "rose" | "amber" | "cyan" | "neutral" {
  if (severity === "error") return "rose";
  if (severity === "warning") return "amber";
  if (severity === "info") return "cyan";
  return "neutral";
}

function LimitationCard({ limitation }: { limitation: Limitation }) {
  return (
    <li className="surface-flat p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={severityTone(limitation.severity)}>{limitation.severity}</Badge>
            <Badge tone="outline">{humanizeKey(limitation.category)}</Badge>
            <Badge tone="neutral">{limitation.scope} scope</Badge>
            <Badge tone={limitation.resolution_status === "open" ? "rose" : "emerald"}>
              {humanizeKey(limitation.resolution_status)}
            </Badge>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-ink-300">{limitation.explanation}</p>
          <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
            {limitation.code} · {limitation.limitation_id}
          </p>
        </div>
      </div>

      <div className="mt-3 grid gap-3 text-[11px] sm:grid-cols-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Affected operations</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {limitation.affected_operations.map((operation) => (
              <li
                key={operation}
                className="rounded border border-amber-400/20 bg-amber-400/5 px-1.5 py-0.5 font-mono text-[10px] text-amber-200"
              >
                {labelForUse(operation)}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Resolution</p>
          <p className="mt-1 leading-relaxed text-ink-300">{limitation.resolution_note}</p>
        </div>
      </div>

      {limitation.scope === "measurement" ? (
        <div className="mt-3 flex flex-wrap gap-3 border-t border-navy-700/60 pt-2.5">
          <Link
            href={`/compare?left=${encodeURIComponent(limitation.scope_id)}`}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
          >
            Open measurement in comparison studio
            <ArrowUpRight className="size-3" aria-hidden="true" />
          </Link>
        </div>
      ) : null}

      <Disclosure summary="Evidence" className="mt-3">
        <SourceReferenceList references={limitation.evidence} />
      </Disclosure>
    </li>
  );
}

export function DatasetLimitationsPanel({
  datasetId,
  compact = false,
}: {
  datasetId: string;
  compact?: boolean;
}) {
  const [scope, setScope] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const limitations = useDatasetLimitations(datasetId, {
    scope: scope || undefined,
    severity: severity || undefined,
    status: status || undefined,
    limit: 200,
  });
  const data = limitations.data?.data;
  const items = data?.limitations ?? [];
  const scopes = useMemo(() => {
    const values = new Set<string>();
    for (const limitation of data?.limitations ?? []) values.add(limitation.scope);
    return Array.from(values).sort();
  }, [data?.limitations]);
  const statuses = useMemo(() => {
    const values = new Set<string>();
    for (const limitation of data?.limitations ?? []) values.add(limitation.resolution_status);
    return Array.from(values).sort();
  }, [data?.limitations]);

  return (
    <section className="surface p-5" aria-labelledby={`dataset-limitations-${datasetId}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id={`dataset-limitations-${datasetId}`}
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <ShieldAlert className="size-4 text-amber-300" aria-hidden="true" />
            Limitations and restrictions
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Dataset- and measurement-scoped limitations returned by the backend. They remain
            attached to the affected operations; this panel never marks a limitation resolved.
          </p>
        </div>
        {data ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="amber">{formatCount(data.summary.total)} total</Badge>
            <Badge tone="rose">{formatCount(data.summary.by_severity.error ?? 0)} errors</Badge>
            <Badge tone="amber">{formatCount(data.summary.by_severity.warning ?? 0)} warnings</Badge>
            <Badge tone="neutral">{formatCount(data.summary.by_status.open ?? 0)} open</Badge>
          </div>
        ) : null}
      </div>

      {compact ? null : (
        <div className="mt-4">
          <FilterBar
            label="Limitation filters"
            actions={
              <p className="text-[11px] text-ink-400" aria-live="polite">
                {data ? `${items.length} of ${data.page.total} limitations shown` : "Loading limitations…"}
              </p>
            }
          >
            <SelectFilter
              id={`limitations-scope-${datasetId}`}
              label="Scope"
              value={scope}
              onChange={setScope}
              options={scopes.map((value) => ({ value, label: humanizeKey(value) }))}
              placeholder="All scopes"
            />
            <SelectFilter
              id={`limitations-severity-${datasetId}`}
              label="Severity"
              value={severity}
              onChange={setSeverity}
              options={[
                { value: "error", label: "Error" },
                { value: "warning", label: "Warning" },
                { value: "info", label: "Info" },
              ]}
              placeholder="All severities"
            />
            <SelectFilter
              id={`limitations-status-${datasetId}`}
              label="Resolution status"
              value={status}
              onChange={setStatus}
              options={statuses.map((value) => ({ value, label: humanizeKey(value) }))}
              placeholder="All statuses"
            />
          </FilterBar>
        </div>
      )}

      {limitations.isPending ? (
        <div className="mt-4">
          <LoadingState label="Loading limitations…" rows={3} />
        </div>
      ) : limitations.isError ? (
        <div className="mt-4">
          <ErrorState
            error={limitations.error}
            title="Limitations could not be loaded"
            onRetry={() => limitations.refetch()}
          />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No limitation matches these filters"
            description="The registry is unchanged. Clear the scope, severity, or status filter. An empty list is not evidence that no limitation exists."
            icon={<Info className="size-6" aria-hidden="true" />}
          />
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((limitation) => (
            <LimitationCard key={limitation.limitation_id} limitation={limitation} />
          ))}
        </ul>
      )}

      {data ? (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-amber-400/15 bg-amber-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden="true" />
          <span>
            {formatCount(data.summary.by_scope.dataset ?? 0)} dataset-scoped and{" "}
            {formatCount(data.summary.by_scope.measurement ?? 0)} measurement-scoped limitations.
            {data.summary.by_status.open
              ? ` ${formatCount(data.summary.by_status.open)} remain open.`
              : " None are marked open in this response."}
          </span>
        </p>
      ) : null}
    </section>
  );
}

export function LimitationSummary({ limitations }: { limitations: Limitation[] }) {
  const errors = limitations.filter((item) => item.severity === "error").length;
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-400">
      {errors > 0 ? (
        <AlertTriangle className="size-3.5 text-rose-300" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="size-3.5 text-emerald-300" aria-hidden="true" />
      )}
      {formatCount(limitations.length)} limitations · {formatCount(errors)} errors
    </span>
  );
}
