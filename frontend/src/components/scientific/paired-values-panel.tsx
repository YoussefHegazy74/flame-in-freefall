"use client";

import Link from "next/link";
import { AlertTriangle, ArrowUpRight, CheckCircle2, GitCompare, Info, ShieldAlert, ShieldQuestion } from "lucide-react";
import type {
  CanonicalPresence,
  ComparisonIntegrity,
  PairedObservation,
  PairedSeries,
  PairedValues,
} from "@/lib/api/types";
import { formatCount, formatNumber, formatUnit, humanizeKey } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "@/components/ui/disclosure";
import { LazyPairedScatterChart } from "@/components/charts/lazy-paired-scatter-chart";
import { SourceReferenceList } from "./provenance";

function integrityTone(status: string): "emerald" | "rose" | "amber" | "neutral" {
  if (status === "available") return "emerald";
  if (status === "missing") return "rose";
  if (status === "not_checked") return "neutral";
  return "amber";
}

function PresenceRow({ check }: { check: CanonicalPresence }) {
  return (
    <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="break-all font-mono text-[10px] text-ink-200">{check.measurement_id}</span>
        <Badge tone={integrityTone(check.status)}>{check.status.replace(/_/g, " ")}</Badge>
      </div>
      <p className="mt-1 text-[11px] text-ink-300">
        {check.checked
          ? `${formatCount(check.non_null_count)} / ${formatCount(check.total_rows)} non-null values`
          : check.reason ?? "presence was not checked"}
      </p>
      {check.table ? (
        <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">
          {check.table}.{check.field}
        </p>
      ) : null}
      {check.alternatives.length > 0 ? (
        <div className="mt-1.5 rounded border border-amber-400/20 bg-amber-400/5 p-2">
          <p className="flex items-center gap-1 text-[10px] font-medium text-amber-100">
            <AlertTriangle className="size-3" aria-hidden="true" />
            Documented alternative — not automatically substituted
          </p>
          <ul className="mt-1 space-y-1">
            {check.alternatives.map((alternative) => (
              <li key={alternative.canonical_field} className="text-[10px] leading-relaxed text-ink-300">
                <span className="font-mono text-ink-200">{alternative.canonical_field}</span>{" "}
                <span className="text-ink-500">({formatUnit(alternative.unit)})</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}

export function ComparisonIntegrityPanel({ integrity }: { integrity: ComparisonIntegrity }) {
  const tone =
    integrity.status === "verified"
      ? "emerald"
      : integrity.status === "missing"
        ? "rose"
        : "amber";

  return (
    <section className="surface p-5" aria-labelledby="comparison-integrity">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="comparison-integrity"
            className="flex items-center gap-2 text-sm font-semibold text-ink-100"
          >
            <ShieldQuestion className="size-4 text-cyan-300" aria-hidden="true" />
            Canonical measurement integrity
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Before a comparison is approved, the backend checks that each registry measurement has
            canonical values. A registry entry alone is not evidence that a measurement exists.
          </p>
        </div>
        <Badge tone={tone}>{integrity.status.replace(/_/g, " ")}</Badge>
      </div>

      {integrity.messages.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {integrity.messages.map((message) => (
            <li
              key={message}
              className="flex items-start gap-1.5 rounded-lg border border-amber-400/20 bg-amber-400/5 p-2 text-[11px] leading-relaxed text-amber-100"
            >
              <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
              {message}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Checks</p>
          {integrity.checks.length === 0 ? (
            <p className="mt-1.5 text-[11px] text-ink-400">No integrity checks were returned.</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {integrity.checks.map((check) => (
                <PresenceRow key={`check-${check.measurement_id}`} check={check} />
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
            Not checked
          </p>
          {integrity.not_checked.length === 0 ? (
            <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-emerald-300">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              Every registry measurement was checked against canonical data.
            </p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {integrity.not_checked.map((check) => (
                <PresenceRow key={`not-checked-${check.measurement_id}`} check={check} />
              ))}
            </ul>
          )}
          {integrity.failures.length > 0 ? (
            <div className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/5 p-2.5">
              <p className="text-[10px] font-medium text-rose-100">
                {formatCount(integrity.failures.length)} failed check
                {integrity.failures.length === 1 ? "" : "s"}
              </p>
              <ul className="mt-1 space-y-1">
                {integrity.failures.map((check) => (
                  <li key={`failure-${check.measurement_id}`} className="break-all font-mono text-[10px] text-rose-200">
                    {check.measurement_id}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function observationValue(
  observation: PairedObservation,
  side: "left" | "right",
): { value: number | null; unit: string | null; row: number | null; citationId: string | null } {
  const nested = observation[side];
  const value =
    nested?.value ?? (side === "left" ? observation.left_value : observation.right_value) ?? null;
  const unit =
    nested?.unit ?? (side === "left" ? observation.left_unit : observation.right_unit) ?? null;
  return {
    value: typeof value === "number" && Number.isFinite(value) ? value : null,
    unit: unit ?? null,
    row: nested?.source_row ?? null,
    citationId: nested?.citation_id ?? null,
  };
}

function derivedSeries(paired: PairedValues): PairedSeries[] {
  const series = paired.series
    .map((item) => ({
      ...item,
      points: item.points.filter(
        (point) => Number.isFinite(point.x) && Number.isFinite(point.y),
      ),
    }))
    .filter((item) => item.points.length > 0);
  if (series.length > 0) return series;

  const points: PairedSeries["points"] = [];
  for (const observation of paired.observations) {
    const left = observationValue(observation, "left");
    const right = observationValue(observation, "right");
    if (left.value === null || right.value === null) continue;
    if (!left.unit || !right.unit || left.unit !== right.unit) continue;
    points.push({ x: left.value, y: right.value, pair_id: observation.pair_id });
  }
  if (points.length === 0) return [];
  const unit = observationValue(paired.observations[0], "left").unit ?? "unit not stated";
  return [
    {
      series_id: "paired-observations",
      label: "Paired observations",
      x_unit: unit,
      y_unit: unit,
      points,
    },
  ];
}

export function isChartReady(paired: PairedValues): boolean {
  if (!paired.available) return false;
  if (!paired.alignment.verified) return false;
  return derivedSeries(paired).length > 0;
}

export function PairedValuesPanel({
  paired,
  leftLabel,
  rightLabel,
}: {
  paired: PairedValues;
  leftLabel: string;
  rightLabel: string;
}) {
  const chartReady = isChartReady(paired);
  const series = chartReady ? derivedSeries(paired) : [];
  const reason = paired.reason;

  return (
    <section className="surface p-5" aria-labelledby="paired-values">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="paired-values" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <GitCompare className="size-4 text-cyan-300" aria-hidden="true" />
            Paired scientific values
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            {leftLabel} versus {rightLabel}. Values are rendered only when the backend returns a
            verified record-level alignment. A comparison decision alone is not a paired dataset.
          </p>
        </div>
        <Badge tone={paired.available ? (paired.alignment.verified ? "emerald" : "amber") : "rose"}>
          {paired.status.replace(/_/g, " ")}
        </Badge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="surface-inset p-3">
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Alignment method</p>
          <p className="mt-1 break-all font-mono text-[11px] text-ink-200">
            {paired.alignment.method_id ?? "no verified method"}
          </p>
          <p className="mt-0.5 text-[10px] text-ink-500">
            {paired.alignment.verified ? "verified" : "unverified"}
          </p>
        </div>
        <div className="surface-inset p-3">
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Alignment keys</p>
          <p className="mt-1 break-all font-mono text-[11px] text-ink-200">
            {paired.alignment.keys.length > 0 ? paired.alignment.keys.join(", ") : "none registered"}
          </p>
        </div>
        <div className="surface-inset p-3">
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Observations</p>
          <p className="mt-1 font-mono text-[11px] text-ink-200">
            {formatCount(paired.observations.length)} paired
          </p>
          <p className="mt-0.5 text-[10px] text-ink-500">
            {formatCount(paired.exclusions.length)} excluded
          </p>
        </div>
        <div className="surface-inset p-3">
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Dataset version</p>
          <p className="mt-1 break-all font-mono text-[10px] text-ink-300">{paired.dataset_version}</p>
        </div>
      </div>

      {paired.alignment.unit_policy ? (
        <p className="mt-3 rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5 text-[11px] leading-relaxed text-ink-300">
          <span className="font-medium text-ink-200">Unit policy:</span>{" "}
          {paired.alignment.unit_policy}
        </p>
      ) : null}

      {!chartReady ? (
        <div className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/5 p-4">
          <div className="flex items-start gap-2.5">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-rose-300" aria-hidden="true" />
            <div>
              <p className="text-xs font-semibold text-rose-100">
                No chart is rendered for this comparison.
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-300">
                {reason?.message ??
                  "The backend did not return a verified alignment with numeric paired observations."}
              </p>
              {reason?.code ? (
                <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
                  reason: {reason.code}
                  {reason.rule_id ? ` · rule: ${reason.rule_id}` : ""}
                </p>
              ) : null}
              {reason?.required_alignment ? (
                <div className="mt-2 rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
                    Required alignment
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-ink-300">
                    {reason.required_alignment.keys.length > 0
                      ? reason.required_alignment.keys.join(", ")
                      : "no keys declared"}
                  </p>
                  <p className="mt-1 text-[10px] leading-relaxed text-ink-400">
                    {reason.required_alignment.note}
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <LazyPairedScatterChart
            series={series}
            leftLabel={leftLabel}
            rightLabel={rightLabel}
            accessibleDescription={`Paired scatter plot of ${leftLabel} against ${rightLabel} using backend-verified alignment. ${formatCount(series.reduce((sum, item) => sum + item.points.length, 0))} paired observations.`}
          />
          <Disclosure summary={`Paired observations (${formatCount(paired.observations.length)})`}>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[11px]">
                <caption className="sr-only">Paired observations with source row references</caption>
                <thead>
                  <tr className="border-b border-navy-700/70">
                    <th scope="col" className="px-2 py-1.5 font-medium text-ink-400">Pair</th>
                    <th scope="col" className="px-2 py-1.5 font-medium text-ink-400">Left value</th>
                    <th scope="col" className="px-2 py-1.5 font-medium text-ink-400">Right value</th>
                    <th scope="col" className="px-2 py-1.5 font-medium text-ink-400">Source rows</th>
                  </tr>
                </thead>
                <tbody>
                  {paired.observations.map((observation) => {
                    const left = observationValue(observation, "left");
                    const right = observationValue(observation, "right");
                    return (
                      <tr key={observation.pair_id} className="border-b border-navy-700/40 last:border-0">
                        <td className="px-2 py-1.5 break-all font-mono text-[10px] text-ink-300">
                          {observation.pair_id}
                        </td>
                        <td className="px-2 py-1.5 font-mono text-ink-200">
                          {left.value === null ? "—" : formatNumber(left.value)}{" "}
                          <span className="text-[10px] text-ink-500">{left.unit ?? ""}</span>
                        </td>
                        <td className="px-2 py-1.5 font-mono text-ink-200">
                          {right.value === null ? "—" : formatNumber(right.value)}{" "}
                          <span className="text-[10px] text-ink-500">{right.unit ?? ""}</span>
                        </td>
                        <td className="px-2 py-1.5 font-mono text-[10px] text-ink-400">
                          {left.row ?? "—"} / {right.row ?? "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Disclosure>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
            Required conditions
          </p>
          {paired.conditions.required.length === 0 ? (
            <p className="mt-1.5 text-[11px] text-ink-400">No condition was required by the rule.</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {paired.conditions.required.map((condition) => (
                <li
                  key={condition.key}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-navy-700/60 bg-navy-950/35 px-2.5 py-1.5"
                >
                  <span className="break-all font-mono text-[10px] text-ink-300">{condition.key}</span>
                  <Badge
                    tone={
                      condition.satisfied === true
                        ? "emerald"
                        : condition.satisfied === false
                          ? "rose"
                          : "neutral"
                    }
                  >
                    {condition.satisfied === null ? "not supplied" : String(condition.satisfied)}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-500">Exclusions</p>
          {paired.exclusions.length === 0 ? (
            <p className="mt-1.5 text-[11px] text-ink-400">No exclusion was returned.</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {paired.exclusions.map((exclusion, index) => (
                <li
                  key={`${JSON.stringify(exclusion)}-${index}`}
                  className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2 text-[10px] leading-relaxed text-ink-300"
                >
                  {Object.entries(exclusion).map(([key, value]) => (
                    <p key={key} className="break-all">
                      <span className="font-mono text-ink-500">{humanizeKey(key)}:</span>{" "}
                      {typeof value === "object" ? JSON.stringify(value) : String(value)}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {paired.provenance.length > 0 ? (
        <Disclosure summary="Paired-value provenance" className="mt-4">
          <SourceReferenceList references={paired.provenance} />
        </Disclosure>
      ) : (
        <p className="mt-4 flex items-start gap-1.5 rounded-lg border border-amber-400/15 bg-amber-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          <Info className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden="true" />
          No paired-value provenance was returned. Do not infer a source for these values.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-3 border-t border-navy-700/60 pt-3">
        <Link
          href="/quality"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
        >
          Review quality restrictions
          <ArrowUpRight className="size-3" aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}
