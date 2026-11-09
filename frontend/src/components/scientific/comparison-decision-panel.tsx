"use client";

import Link from "next/link";
import { AlertTriangle, ArrowUpRight, CheckCircle2, Info, RefreshCw, ShieldAlert } from "lucide-react";
import type {
  ComparisonDecision,
  ComparisonMeasurement,
  RequiredCondition,
} from "@/lib/api/types";
import { fieldLabel } from "@/lib/labels";
import { formatUnit } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ComparisonStateBadge } from "./state-badge";
import { ValueKindBadge } from "./unit-label";
import { SourceReferenceList } from "./provenance";

function MeasurementCard({
  measurement,
  side,
}: {
  measurement: ComparisonMeasurement;
  side: "Left" | "Right";
}) {
  return (
    <div className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          {side}
        </span>
        <Badge tone="cyan">{measurement.accession}</Badge>
        <ComparisonStateBadge status={measurement.comparison_status} showIcon={false} />
      </div>
      <p className="mt-2 text-sm font-semibold text-ink-100">{fieldLabel(measurement.parameter)}</p>
      <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">
        {measurement.measurement_id}
      </p>
      <dl className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
        <div>
          <dt className="text-ink-500">Unit</dt>
          <dd className="font-mono text-ink-300">{formatUnit(measurement.unit)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Value kind</dt>
          <dd><ValueKindBadge valueKind={measurement.value_kind} /></dd>
        </div>
        <div>
          <dt className="text-ink-500">Calibration</dt>
          <dd className="text-ink-300">{measurement.calibration_status.replace(/_/g, " ")}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Availability</dt>
          <dd className="text-ink-300">{measurement.availability.replace(/_/g, " ")}</dd>
        </div>
      </dl>
      <Link
        href={`/datasets/${encodeURIComponent(measurement.dataset_id)}`}
        className="mt-3 inline-flex items-center gap-1 text-[11px] text-cyan-300 hover:text-cyan-200 focus-ring"
      >
        Open dataset context
        <ArrowUpRight className="size-3" aria-hidden="true" />
      </Link>
    </div>
  );
}

function ConditionChecklist({
  conditions,
  values,
  onChange,
}: {
  conditions: RequiredCondition[];
  values: Record<string, boolean | null>;
  onChange: (key: string, value: boolean) => void;
}) {
  if (conditions.length === 0) return null;
  return (
    <fieldset className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">
      <legend className="px-1 text-xs font-semibold text-cyan-200">
        Required conditions
      </legend>
      <p className="mt-1 text-[11px] leading-relaxed text-ink-400">
        The backend does not assume these conditions. Check only the conditions you can verify
        from the source metadata; the comparison remains conditional until every condition is
        explicitly satisfied.
      </p>
      <ul className="mt-3 space-y-2.5">
        {conditions.map((condition) => {
          const checked = values[condition.key] === true;
          return (
            <li key={condition.key}>
              <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-navy-700/60 bg-navy-950/40 p-2.5">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => onChange(condition.key, event.target.checked)}
                  className="mt-0.5 size-4 rounded border-navy-500 bg-navy-900 text-cyan-400 focus:ring-cyan-400"
                />
                <span>
                  <span className="block font-mono text-[11px] text-ink-200">{condition.key}</span>
                  <span className="mt-0.5 block text-[11px] leading-relaxed text-ink-400">
                    {condition.description}
                  </span>
                  {condition.satisfied === true ? (
                    <span className="mt-1 inline-flex items-center gap-1 text-[10px] text-emerald-300">
                      <CheckCircle2 className="size-3" aria-hidden="true" />
                      Already satisfied in the API response
                    </span>
                  ) : null}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

export function ComparisonDecisionPanel({
  decision,
  conditions,
  onConditionChange,
  onReevaluate,
  isReevaluating,
}: {
  decision: ComparisonDecision;
  conditions: Record<string, boolean | null>;
  onConditionChange: (key: string, value: boolean) => void;
  onReevaluate: () => void;
  isReevaluating: boolean;
}) {
  const noChart = decision.status !== "comparable";
  const verifiedCount = decision.required_conditions.filter(
    (condition) => conditions[condition.key] === true,
  ).length;

  return (
    <section className="surface overflow-hidden" aria-label="Comparison decision">
      <div className="border-b border-navy-700/70 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="kicker">Backend decision</span>
          <ComparisonStateBadge status={decision.status} />
          <span className="font-mono text-[10px] text-ink-500">{decision.status}</span>
          {decision.rule_id ? (
            <Badge tone="outline" className="font-mono">
              rule: {decision.rule_id}
            </Badge>
          ) : null}
        </div>
        <p className="mt-3 text-sm leading-relaxed text-ink-300">
          {decision.scientific_justification}
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <MeasurementCard measurement={decision.left} side="Left" />
          <MeasurementCard measurement={decision.right} side="Right" />
        </div>
      </div>

      <div className="space-y-4 p-5">
        <div>
          <h3 className="text-xs font-semibold text-ink-100">Reasons from the engine</h3>
          {decision.reasons.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {decision.reasons.map((reason) => (
                <li key={`${reason.code}-${reason.message}`} className="flex items-start gap-2 rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5 text-xs">
                  <Info className="mt-0.5 size-3.5 shrink-0 text-cyan-300" aria-hidden="true" />
                  <span>
                    <span className="mono text-[10px] text-ink-500">{reason.code}</span>
                    <span className="mt-0.5 block leading-relaxed text-ink-300">{reason.message}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-ink-400">No reason records were returned.</p>
          )}
        </div>

        {decision.required_conditions.length > 0 ? (
          <ConditionChecklist
            conditions={decision.required_conditions}
            values={conditions}
            onChange={onConditionChange}
          />
        ) : null}

        {decision.required_conditions.length > 0 ? (
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onReevaluate}
              disabled={isReevaluating}
              className={buttonStyles({ variant: "primary", size: "sm" })}
            >
              <RefreshCw
                className={cn("size-3.5", isReevaluating && "animate-spin")}
                aria-hidden="true"
              />
              Re-evaluate with current conditions
            </button>
            <p className="text-[11px] text-ink-400">
              {verifiedCount} of {decision.required_conditions.length} conditions marked verified.
              The backend makes the final decision; unchecking a condition can withdraw approval.
            </p>
          </div>
        ) : null}

        <div>
          <h3 className="flex items-center gap-2 text-xs font-semibold text-ink-100">
            <AlertTriangle className="size-3.5 text-amber-300" aria-hidden="true" />
            Warnings
          </h3>
          {decision.warnings.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {decision.warnings.map((warning) => (
                <li key={warning} className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-2.5 text-xs leading-relaxed text-amber-100">
                  {warning}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-ink-400">No additional comparison warnings.</p>
          )}
        </div>

        <div className={cn("rounded-xl border p-4", noChart ? "border-rose-400/20 bg-rose-400/5" : "border-emerald-400/20 bg-emerald-400/5")}>
          <div className="flex items-start gap-2.5">
            {noChart ? (
              <ShieldAlert className="mt-0.5 size-4 shrink-0 text-rose-300" aria-hidden="true" />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-300" aria-hidden="true" />
            )}
            <div>
              <p className="text-xs font-semibold text-ink-100">
                {noChart
                  ? "No shared comparison chart is rendered."
                  : "Comparison approved by the backend."}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-ink-300">
                {noChart
                  ? "The comparison is not approved in its current state. Rendering two series on a shared axis would imply a comparison the evidence does not support."
                  : "The API returns the decision and measurement metadata, not paired measurement values. This page does not fabricate a chart; use the source explorers to inspect individual rows with their units and provenance."}
              </p>
              <div className="mt-2 flex flex-wrap gap-3 text-[11px]">
                <Link
                  href={`/experiments/gas-flame?accession=${encodeURIComponent(decision.left.accession)}`}
                  className="text-cyan-300 hover:text-cyan-200 focus-ring"
                >
                  Inspect gas-flame rows
                </Link>
                <Link href="/quality" className="text-cyan-300 hover:text-cyan-200 focus-ring">
                  Review quality restrictions
                </Link>
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ink-100">Source references</h3>
          <div className="mt-2">
            <SourceReferenceList references={decision.source_references} />
          </div>
        </div>
      </div>
    </section>
  );
}
