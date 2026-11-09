"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeftRight,
  BookOpen,
  GitCompare,
  Info,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useComparability, useComparison, useMeasurements } from "@/lib/api/hooks";
import type {
  ComparisonRule,
  ComparisonStatus,
  RegistryMeasurement,
} from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { COMPARISON_LABELS, fieldLabel } from "@/lib/labels";
import { formatCount, formatUnit } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EmptyState, ErrorState, InlineAlert, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, SelectFilter } from "@/components/ui/filter";
import { TD_CLASS, TH_CLASS, TableShell } from "@/components/ui/table-shell";
import { ComparisonStateBadge } from "@/components/scientific/state-badge";
import { ComparisonDecisionPanel } from "@/components/scientific/comparison-decision-panel";
import { QualityBanner } from "@/components/scientific/quality-banner";

const STATUS_ORDER: ComparisonStatus[] = [
  "comparable",
  "conditionally_comparable",
  "not_comparable",
  "blocked",
  "insufficient_metadata",
];

function parseConditions(
  searchParams: URLSearchParams,
): Record<string, boolean | null> | undefined {
  const entries = Array.from(searchParams.entries()).filter(([key]) =>
    key.startsWith("cond_"),
  );
  if (entries.length === 0) return undefined;
  const result: Record<string, boolean | null> = {};
  for (const [key, value] of entries) {
    result[key.slice("cond_".length)] =
      value === "true" ? true : value === "false" ? false : null;
  }
  return result;
}

function measurementLabel(measurement: RegistryMeasurement): string {
  return `${measurement.accession} · ${fieldLabel(measurement.parameter)} · ${formatUnit(measurement.unit)}`;
}

function conditionsToParams(
  conditions: Record<string, boolean | null>,
): Record<string, string | null> {
  const updates: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(conditions)) {
    updates[`cond_${key}`] = value === null ? null : String(value);
  }
  return updates;
}

function CompareContent() {
  const { get, setParams, clearParams, searchParams } = useUrlState();
  const measurements = useMeasurements({ limit: 200 });
  const comparability = useComparability();

  const left = get("left") ?? "";
  const right = get("right") ?? "";
  const ruleStatus = get("rule_status") ?? "";
  const ruleQuery = get("rule_q") ?? "";
  const appliedConditions = useMemo(
    () => parseConditions(searchParams),
    [searchParams],
  );

  const sameMeasurement = Boolean(left && right && left === right);

  const grouped = useMemo(() => {
    const map = new Map<string, RegistryMeasurement[]>();
    for (const measurement of measurements.data?.data ?? []) {
      const list = map.get(measurement.physical_quantity) ?? [];
      list.push(measurement);
      map.set(measurement.physical_quantity, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [measurements.data]);

  const summary = comparability.data?.data;
  const filteredRules = useMemo(() => {
    const rules = summary?.rules ?? [];
    const query = ruleQuery.trim().toLowerCase();
    return rules.filter((rule) => {
      if (ruleStatus && rule.status !== ruleStatus) return false;
      if (!query) return true;
      return (
        rule.rule_id.toLowerCase().includes(query) ||
        rule.left_measurement_id.toLowerCase().includes(query) ||
        rule.right_measurement_id.toLowerCase().includes(query) ||
        rule.scientific_justification.toLowerCase().includes(query)
      );
    });
  }, [summary, ruleQuery, ruleStatus]);

  const applyPair = (nextLeft: string, nextRight: string) => {
    const updates: Record<string, string | null> = { left: nextLeft, right: nextRight };
    for (const key of Array.from(searchParams.keys())) {
      if (key.startsWith("cond_")) updates[key] = null;
    }
    setParams(updates);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analysis · Comparison Studio"
        title="Backend-approved measurement comparisons"
        description={
          <>
            Select two registered measurements. The backend evaluates its explicit rules, units,
            value kinds, calibration status, and required conditions. A matching column name is not
            evidence of comparability, and this page never renders a shared chart from unpaired
            values.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(summary?.measurement_count ?? 0)} measurements</Badge>
            <Badge tone="neutral">{formatCount(summary?.rule_count ?? 0)} explicit rules</Badge>
            <Badge tone="amber">Default: not comparable</Badge>
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-3.5">
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-amber-100">
              A comparison decision is not a paired dataset.
            </p>
            <p className="mt-1">
              <span className="mono">/compare</span> returns the decision and measurement metadata,
              not paired measurement values. No chart is fabricated here. Use the source explorers
              to inspect individual rows with their units, flags, and provenance.
            </p>
          </div>
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="comparison-selection">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="comparison-selection" className="text-sm font-semibold text-ink-100">
              Select two measurements
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-400">
              The selection is stored in the URL. If the API cannot decide from the available
              metadata, it returns <span className="mono">insufficient_metadata</span>; that state
              cannot be overridden with condition checkboxes.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => applyPair(right, left)}
              disabled={!left || !right}
              className={buttonStyles({ size: "sm" })}
            >
              <ArrowLeftRight className="size-3.5" aria-hidden="true" />
              Swap sides
            </button>
            <button
              type="button"
              onClick={() => clearParams()}
              className={buttonStyles({ variant: "ghost", size: "sm" })}
            >
              Clear selection
            </button>
          </div>
        </div>

        {measurements.isPending ? (
          <div className="mt-4">
            <LoadingState label="Loading registered measurements…" rows={2} />
          </div>
        ) : measurements.isError ? (
          <div className="mt-4">
            <ErrorState
              error={measurements.error}
              title="Registered measurements could not be loaded"
              onRetry={() => measurements.refetch()}
            />
          </div>
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <MeasurementSelect
              id="compare-left"
              label="Left measurement"
              value={left}
              grouped={grouped}
              onChange={(value) => applyPair(value, right)}
            />
            <MeasurementSelect
              id="compare-right"
              label="Right measurement"
              value={right}
              grouped={grouped}
              onChange={(value) => applyPair(left, value)}
            />
          </div>
        )}

        {sameMeasurement ? (
          <InlineAlert tone="warning" className="mt-3">
            The same measurement is selected on both sides. The backend requires two different
            measurements; no comparison request was sent.
          </InlineAlert>
        ) : null}
        {!left || !right ? (
          <InlineAlert tone="info" className="mt-3">
            Select both sides to ask the backend for a decision. Selecting two measurements does not
            itself create a valid comparison.
          </InlineAlert>
        ) : null}
      </section>

      {left && right && !sameMeasurement ? (
        <ComparisonResult
          key={`${left}::${right}::${JSON.stringify(appliedConditions ?? null)}`}
          left={left}
          right={right}
          appliedConditions={appliedConditions}
        />
      ) : null}

      {summary ? (
        <section className="surface p-5" aria-labelledby="comparability-registry">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2
                id="comparability-registry"
                className="flex items-center gap-2 text-sm font-semibold text-ink-100"
              >
                <BookOpen className="size-4 text-cyan-300" aria-hidden="true" />
                Comparability registry
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-ink-400">
                Counts are returned by <span className="mono">/comparability</span>. Zero
                measurements are unconditionally comparable in this snapshot; conditional rules
                still require verified conditions.
              </p>
            </div>
            <Badge tone="outline" className="font-mono">
              registry {summary.registry_version}
            </Badge>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-ink-500">
                Measurement states
              </p>
              <ul className="mt-2 space-y-1.5">
                {STATUS_ORDER.map((status) => (
                  <li key={status} className="flex items-center justify-between gap-3">
                    <ComparisonStateBadge status={status} showIcon={false} />
                    <span className="font-mono text-xs text-ink-300">
                      {formatCount(summary.measurement_status_counts[status] ?? 0)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-navy-700/70 bg-navy-950/40 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-ink-500">Rule states</p>
              <ul className="mt-2 space-y-1.5">
                {STATUS_ORDER.map((status) => (
                  <li key={status} className="flex items-center justify-between gap-3">
                    <ComparisonStateBadge status={status} showIcon={false} />
                    <span className="font-mono text-xs text-ink-300">
                      {formatCount(summary.rule_status_counts[status] ?? 0)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-cyan-100">
              <Info className="size-3.5" aria-hidden="true" />
              Default policy: {COMPARISON_LABELS[summary.default_policy.status]}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-300">
              {summary.default_policy.justification}
            </p>
            <p className="mt-1 font-mono text-[10px] text-ink-500">
              {summary.default_policy.engine_behavior}
            </p>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {STATUS_ORDER.map((status) => {
              const definition = summary.state_definitions[status];
              if (!definition) return null;
              return (
                <div
                  key={status}
                  className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3.5"
                >
                  <ComparisonStateBadge status={status} showIcon={false} />
                  <p className="mt-2 text-[11px] leading-relaxed text-ink-300">
                    {definition.definition}
                  </p>
                  <p className="mt-1.5 text-[10px] leading-relaxed text-ink-500">
                    {definition.engine_behavior}
                  </p>
                </div>
              );
            })}
          </div>

          <Disclosure
            summary={`Browse documented comparison rules (${formatCount(summary?.rule_count ?? 0)})`}
            className="mt-4"
          >
            <FilterBar
              label="Comparison rule filters"
              className="bg-transparent p-0"
              actions={
                <FilterActions
                  onClear={() => {
                    setParams({ rule_status: null, rule_q: null });
                  }}
                  resultLabel={`${formatCount(filteredRules.length)} of ${formatCount(summary?.rule_count ?? 0)} rules shown`}
                />
              }
            >
              <SelectFilter
                id="rule-status"
                label="Rule status"
                value={ruleStatus}
                onChange={(value) => setParams({ rule_status: value || null })}
                options={STATUS_ORDER.map((status) => ({
                  value: status,
                  label: COMPARISON_LABELS[status],
                }))}
                placeholder="All rule states"
              />
              <div>
                <label
                  htmlFor="rule-search"
                  className="mb-1 block text-[11px] font-medium text-ink-300"
                >
                  Search rule, measurement, or justification
                </label>
                <div className="relative">
                  <Search
                    className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
                    aria-hidden="true"
                  />
                  <input
                    id="rule-search"
                    type="search"
                    value={ruleQuery}
                    onChange={(event) =>
                      setParams({ rule_q: event.target.value || null }, { resetOffset: false })
                    }
                    placeholder="e.g. oxygen, pressure, psi10"
                    className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 pl-8 pr-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
                  />
                </div>
                <p className="mt-1 text-[10px] leading-relaxed text-ink-500">
                  This filter browses the full rule list returned by the API. It does not change any
                  comparison decision.
                </p>
              </div>
            </FilterBar>

            {filteredRules.length === 0 ? (
              <EmptyState
                title="No documented rule matches this filter"
                description="The registry list is unchanged. Clear the rule status or search text to see all documented rules."
                icon={<GitCompare className="size-6" aria-hidden="true" />}
              />
            ) : (
              <div className="mt-3">
                <TableShell caption="Documented comparison rules with status, measurement pair, required conditions, and scientific justification">
                  <thead>
                    <tr>
                      <th scope="col" className={TH_CLASS}>Rule</th>
                      <th scope="col" className={TH_CLASS}>Status</th>
                      <th scope="col" className={TH_CLASS}>Measurement pair</th>
                      <th scope="col" className={TH_CLASS}>Required conditions</th>
                      <th scope="col" className={TH_CLASS}>Justification</th>
                      <th scope="col" className={TH_CLASS}>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRules.map((rule) => (
                      <RuleRow
                        key={rule.rule_id}
                        rule={rule}
                        onSelect={() =>
                          applyPair(rule.left_measurement_id, rule.right_measurement_id)
                        }
                      />
                    ))}
                  </tbody>
                </TableShell>
              </div>
            )}
          </Disclosure>
        </section>
      ) : comparability.isPending ? (
        <LoadingState label="Loading the comparability registry…" rows={4} />
      ) : comparability.isError ? (
        <ErrorState
          error={comparability.error}
          title="The comparability registry could not be loaded"
          onRetry={() => comparability.refetch()}
        />
      ) : null}

      <section className="surface p-5" aria-labelledby="compare-next-steps">
        <h2 id="compare-next-steps" className="text-sm font-semibold text-ink-100">
          What this studio does not do
        </h2>
        <ul className="mt-3 grid gap-2 text-xs leading-relaxed text-ink-300 md:grid-cols-2">
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            It does not pair individual rows or compute a shared statistic.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            It does not convert units, normalize categorical labels, or resolve blends.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            It does not turn a conditional or blocked rule into an approval.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            It does not infer a causal or risk claim from a comparison state.
          </li>
        </ul>
        <div className="mt-3 flex flex-wrap gap-3">
          <Link href="/quality" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Review quality restrictions
          </Link>
          <Link href="/about" className="text-xs font-medium text-cyan-300 hover:text-cyan-200 focus-ring">
            Read the methods and limitations
          </Link>
        </div>
      </section>
    </div>
  );
}

function ComparisonResult({
  left,
  right,
  appliedConditions,
}: {
  left: string;
  right: string;
  appliedConditions?: Record<string, boolean | null>;
}) {
  const { setParams } = useUrlState();
  const comparison = useComparison(left, right, appliedConditions, true);
  const decision = comparison.data?.data;
  const [overrides, setOverrides] = useState<Record<string, boolean | null>>({});

  const draftConditions = useMemo(() => {
    const next: Record<string, boolean | null> = {};
    if (!decision) return next;
    for (const condition of decision.required_conditions) {
      const supplied =
        appliedConditions !== undefined &&
        Object.prototype.hasOwnProperty.call(appliedConditions, condition.key);
      next[condition.key] = Object.prototype.hasOwnProperty.call(overrides, condition.key)
        ? overrides[condition.key]
        : supplied
          ? appliedConditions?.[condition.key] ?? null
          : condition.satisfied ?? null;
    }
    return next;
  }, [decision, appliedConditions, overrides]);

  const changeCondition = (key: string, value: boolean) => {
    setOverrides((current) => ({ ...current, [key]: value }));
  };

  const reevaluate = () => {
    setParams({ left, right, ...conditionsToParams(draftConditions) });
    if (Object.values(draftConditions).every((value) => value === null)) {
      comparison.refetch();
    }
  };

  const dirty =
    decision !== undefined &&
    decision.required_conditions.some((condition) => {
      const supplied =
        appliedConditions !== undefined &&
        Object.prototype.hasOwnProperty.call(appliedConditions, condition.key);
      const applied = supplied
        ? appliedConditions?.[condition.key] ?? null
        : condition.satisfied ?? null;
      return applied !== draftConditions[condition.key];
    });

  if (comparison.isPending) {
    return <LoadingState label="Evaluating the comparison with the backend…" rows={4} />;
  }

  if (comparison.isError) {
    return (
      <ErrorState
        error={comparison.error}
        title="The comparison could not be evaluated"
        onRetry={() => comparison.refetch()}
      >
        <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
          The backend returns an error for unknown measurements or invalid condition payloads. No
          local fallback decision is invented.
        </p>
      </ErrorState>
    );
  }

  if (!decision) return null;

  return (
    <div className="space-y-3">
      {dirty ? (
        <InlineAlert tone="warning" title="Conditions changed but not applied">
          The checklist differs from the conditions used for the decision shown below. Choose
          “Re-evaluate with current conditions” to send the new values to the backend.
        </InlineAlert>
      ) : null}
      <ComparisonDecisionPanel
        decision={decision}
        conditions={draftConditions}
        onConditionChange={changeCondition}
        onReevaluate={reevaluate}
        isReevaluating={comparison.isFetching}
      />
      {comparison.data ? (
        <QualityBanner
          quality={comparison.data.quality}
          title="Comparison response quality"
        />
      ) : null}
    </div>
  );
}

function MeasurementSelect({
  id,
  label,
  value,
  grouped,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  grouped: Array<[string, RegistryMeasurement[]]>;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] font-medium text-ink-300">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 text-xs text-ink-100 focus:border-cyan-400/60 focus-ring"
      >
        <option value="">Choose a measurement…</option>
        {grouped.map(([quantity, items]) => (
          <optgroup key={quantity} label={fieldLabel(quantity)}>
            {items.map((measurement) => (
              <option key={measurement.measurement_id} value={measurement.measurement_id}>
                {measurementLabel(measurement)} — {COMPARISON_LABELS[measurement.comparison_status]}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
        {value || "No measurement selected"}
      </p>
    </div>
  );
}

function RuleRow({ rule, onSelect }: { rule: ComparisonRule; onSelect: () => void }) {
  return (
    <tr className="hover:bg-navy-800/35">
      <td className={TD_CLASS}>
        <span className="break-all font-mono text-[10px] text-ink-200">{rule.rule_id}</span>
      </td>
      <td className={TD_CLASS}>
        <ComparisonStateBadge status={rule.status} showIcon={false} />
      </td>
      <td className={TD_CLASS}>
        <p className="break-all font-mono text-[10px] text-ink-300">{rule.left_measurement_id}</p>
        <p className="mt-0.5 break-all font-mono text-[10px] text-ink-500">
          {rule.right_measurement_id}
        </p>
      </td>
      <td className={TD_CLASS}>
        {rule.required_conditions.length === 0 ? (
          <span className="text-[10px] text-ink-500">None</span>
        ) : (
          <ul className="space-y-1">
            {rule.required_conditions.map((condition) => (
              <li key={condition.key} className="font-mono text-[10px] text-ink-300">
                {condition.key}
              </li>
            ))}
          </ul>
        )}
      </td>
      <td className={`${TD_CLASS} max-w-md text-[11px] leading-relaxed text-ink-300`}>
        {rule.scientific_justification}
      </td>
      <td className={TD_CLASS}>
        <button
          type="button"
          onClick={onSelect}
          className="whitespace-nowrap text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
          aria-label={`Load pair for rule ${rule.rule_id}`}
        >
          Load pair
        </button>
      </td>
    </tr>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading Comparison Studio…" rows={4} />}>
      <CompareContent />
    </Suspense>
  );
}
