"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Cloud, RefreshCw } from "lucide-react";
import { useSmokeRun, useSmokeRuns, useSmokeSeries } from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";
import type { SmokeRunSummary } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { formatCount, formatDurationSeconds, formatNumber } from "@/lib/format";
import { parseChannelList, recommendedChannels } from "@/lib/series";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { EmptyState, ErrorState, InlineAlert, LoadingState } from "@/components/ui/states";
import { TextFilter } from "@/components/ui/filter";
import { TD_CLASS, TH_CLASS } from "@/components/ui/table-shell";
import { ChannelPicker } from "@/components/scientific/channel-picker";
import { QualityBanner } from "@/components/scientific/quality-banner";
import { LazyTimeSeriesChart } from "@/components/charts/lazy-time-series-chart";

const DEFAULT_MAX_POINTS = 20_000;

function jsonList(value: string | null | undefined): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => String(item));
  } catch {
    return [];
  }
}

function SmokeContent() {
  const { get, getNumber, setParams } = useUrlState();
  const runs = useSmokeRuns({ limit: 100 });
  const runId = get("run") ?? "";

  useEffect(() => {
    if (!runId && runs.data?.data.length) {
      setParams({ run: runs.data.data[0].run_id });
    }
  }, [runId, runs.data, setParams]);

  const run = useSmokeRun(runId, { enabled: Boolean(runId) });
  const runData = run.data?.data;
  const runChannels = useMemo(() => runData?.channels ?? [], [runData]);
  const channelsParam = get("channels");
  const appliedChannels = useMemo(
    () =>
      channelsParam === undefined
        ? recommendedChannels(runChannels)
        : parseChannelList(channelsParam),
    [channelsParam, runChannels],
  );
  const appliedKey = appliedChannels.join(",");

  const runMin = runData?.elapsed_test_time_min_s ?? 0;
  const runMax = runData?.elapsed_test_time_max_s ?? 0;
  const startParam = getNumber("start");
  const endParam = getNumber("end");
  const appliedStart = startParam ?? runMin;
  const appliedEnd = endParam ?? runMax;
  const appliedMaxPoints = getNumber("max_points") ?? DEFAULT_MAX_POINTS;

  const [formError, setFormError] = useState<string | null>(null);
  const appliedStateKey = [
    runId,
    appliedKey,
    appliedStart,
    appliedEnd,
    appliedMaxPoints,
  ].join("|");
  const [draftState, setDraftState] = useState<{
    key: string;
    value: {
      selected: string[];
      startText: string;
      endText: string;
      maxPointsText: string;
    };
  } | null>(null);
  const draft = draftState?.key === appliedStateKey ? draftState.value : null;
  const selected = draft?.selected ?? appliedChannels;
  const startText = draft?.startText ?? String(appliedStart);
  const endText = draft?.endText ?? String(appliedEnd);
  const maxPointsText = draft?.maxPointsText ?? String(appliedMaxPoints);

  const updateDraft = (
    patch: Partial<{
      selected: string[];
      startText: string;
      endText: string;
      maxPointsText: string;
    }>,
  ) => {
    setDraftState({
      key: appliedStateKey,
      value: { selected, startText, endText, maxPointsText, ...patch },
    });
  };

  const appliedRangeValid =
    Number.isFinite(appliedStart) &&
    Number.isFinite(appliedEnd) &&
    appliedStart < appliedEnd &&
    appliedStart >= runMin &&
    appliedEnd <= runMax;
  const seriesParams =
    runId && appliedChannels.length > 0 && appliedRangeValid
      ? {
          channels: appliedChannels,
          start_s: appliedStart,
          end_s: appliedEnd,
          max_points: appliedMaxPoints,
        }
      : null;
  const series = useSmokeSeries(runId, seriesParams);

  const selectRun = (nextRunId: string) => {
    setDraftState(null);
    setFormError(null);
    setParams({
      run: nextRunId,
      channels: null,
      start: null,
      end: null,
      max_points: null,
    });
  };

  const applySeries = () => {
    const start = Number(startText);
    const end = Number(endText);
    const maxPoints = Number(maxPointsText);
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      setFormError("Start and end must be finite numbers in elapsed seconds.");
      return;
    }
    if (start >= end) {
      setFormError("Start must be strictly less than end.");
      return;
    }
    if (start < runMin || end > runMax) {
      setFormError(
        `The requested range must stay within the run bounds ${formatNumber(runMin)}–${formatNumber(runMax)} s.`,
      );
      return;
    }
    if (!Number.isInteger(maxPoints) || maxPoints < 1 || maxPoints > 20_000) {
      setFormError("Max points must be an integer from 1 to 20,000.");
      return;
    }
    if (selected.length === 0) {
      setFormError("Select at least one channel.");
      return;
    }
    setFormError(null);
    setParams({
      channels: selected.join(","),
      start,
      end,
      max_points: maxPoints === DEFAULT_MAX_POINTS ? null : maxPoints,
    });
  };

  const rangeError = isApiError(series.error) && series.error.code === "range_too_large"
    ? (series.error.details as Record<string, unknown> | null)
    : null;
  const suggestedSpan = rangeError ? Number(rangeError.suggested_max_span_s) : NaN;
  const actualPoints = rangeError ? Number(rangeError.actual_points) : null;
  const selectedRun = runs.data?.data.find((item) => item.run_id === runId);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Time series · SAME-R smoke"
        title="PSI-101 smoke and housekeeping runs"
        description={
          <>
            44 separate HKP exports with elapsed-test-time channels in seconds. Choose one run,
            then choose channels and a bounded range. Runs are never concatenated, and detector
            voltages are not converted into smoke concentration.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(runs.data?.meta.page?.total ?? 0)} runs</Badge>
            <Badge tone="amber">Separate runs</Badge>
            {runData ? <Badge tone="neutral">{runData.channel_count} channels</Badge> : null}
            {runData ? <Badge tone="outline">time unit: {runData.time_unit}</Badge> : null}
          </>
        }
      />

      <section className="rounded-xl border border-amber-400/25 bg-warning-soft p-3.5">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-amber-100">
              Detector signals are not calibrated smoke measurements.
            </p>
            <p className="mt-1">
              -999 values are sentinels and are excluded from series. DustTrak all-zero segments are
              not automatically clean air. Material names require a validated join to the test logs;
              this interface does not infer that join.
            </p>
          </div>
        </div>
      </section>

      {runs.isPending ? (
        <LoadingState label="Loading smoke runs…" rows={3} />
      ) : runs.isError ? (
        <ErrorState
          error={runs.error}
          title="Smoke runs could not be loaded"
          onRetry={() => runs.refetch()}
        />
      ) : (runs.data?.data.length ?? 0) === 0 ? (
        <EmptyState
          title="No smoke runs were returned"
          description="The API returned an empty run list. No run or channel is synthesized."
          icon={<Cloud className="size-6" aria-hidden="true" />}
        />
      ) : (
        <>
          <section className="surface p-5" aria-labelledby="smoke-run-picker">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="smoke-run-picker" className="text-sm font-semibold text-ink-100">
                  Choose a run
                </h2>
                <p className="mt-1 text-xs text-ink-400">
                  Each HKP export has its own elapsed-time bounds, channel set, and checksum. The
                  selection is stored in the URL.
                </p>
              </div>
              {run.isFetching ? <Badge tone="neutral">Loading run detail…</Badge> : null}
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
              <div>
                <label htmlFor="smoke-run" className="mb-1 block text-[11px] font-medium text-ink-300">
                  Run
                </label>
                <select
                  id="smoke-run"
                  value={runId}
                  onChange={(event) => selectRun(event.target.value)}
                  className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 font-mono text-[11px] text-ink-100 focus:border-cyan-400/60 focus-ring"
                >
                  {(runs.data?.data ?? []).map((item) => (
                    <option key={item.run_id} value={item.run_id}>
                      {item.run_id}
                    </option>
                  ))}
                </select>
                <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
                  {selectedRun?.source_file ?? "—"}
                </p>
              </div>
              {selectedRun ? <SmokeRunFacts run={selectedRun} /> : null}
            </div>
          </section>

          {runId && run.isError ? (
            <ErrorState
              error={run.error}
              title="The selected smoke run could not be loaded"
              onRetry={() => run.refetch()}
            >
              <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
                A missing run is reported as an error. The interface does not substitute another
                run.
              </p>
            </ErrorState>
          ) : null}

          {runData ? (
            <div className="space-y-5">
              <section className="surface p-5" aria-labelledby="smoke-run-summary">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 id="smoke-run-summary" className="text-sm font-semibold text-ink-100">
                      Selected run
                    </h2>
                    <p className="mt-1 break-all font-mono text-[11px] text-ink-300">
                      {runData.run_id}
                    </p>
                    <p className="mt-1 break-all font-mono text-[10px] text-ink-500">
                      {runData.source_file}
                    </p>
                  </div>
                  <Badge tone="cyan">time unit: {runData.time_unit}</Badge>
                </div>
                <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <dt className="text-ink-500">Valid rows</dt>
                    <dd className="font-mono text-ink-200">{formatCount(runData.valid_rows)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Sentinel-time rows</dt>
                    <dd className="font-mono text-ink-200">{formatCount(runData.sentinel_time_rows)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Elapsed test time</dt>
                    <dd className="font-mono text-ink-200">
                      {formatNumber(runData.elapsed_test_time_min_s)}–
                      {formatNumber(runData.elapsed_test_time_max_s)} s
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Approximate span</dt>
                    <dd className="text-ink-200">
                      {formatDurationSeconds(
                        (runData.elapsed_test_time_max_s ?? 0) - (runData.elapsed_test_time_min_s ?? 0),
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Channels</dt>
                    <dd className="font-mono text-ink-200">{runData.channel_count}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Columns</dt>
                    <dd className="font-mono text-ink-200">{runData.column_count}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Carousel number</dt>
                    <dd className="font-mono text-ink-200">{runData.carousel_number ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Test / sample numbers</dt>
                    <dd className="font-mono text-[10px] text-ink-200">
                      tests {jsonList(runData.test_numbers_json).join(", ") || "—"} · samples{" "}
                      {jsonList(runData.sample_numbers_json).join(", ") || "—"}
                    </dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-ink-500">Checksum</dt>
                    <dd className="break-all font-mono text-[10px] text-ink-400">{runData.sha256}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-ink-500">Source URL</dt>
                    <dd className="break-all font-mono text-[10px] text-ink-400">
                      {runData.source_url}
                    </dd>
                  </div>
                </dl>
                {runData.notes ? (
                  <p className="mt-3 rounded-lg border border-amber-400/20 bg-warning-soft p-2.5 text-[11px] leading-relaxed text-amber-100">
                    {runData.notes}
                  </p>
                ) : null}
                {runData.limitations?.length ? (
                  <ul className="mt-3 space-y-1.5">
                    {runData.limitations.map((limitation) => (
                      <li
                        key={limitation}
                        className="flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-400"
                      >
                        <AlertTriangle className="mt-0.5 size-3 shrink-0 text-amber-300" aria-hidden="true" />
                        {limitation}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
                <section className="surface p-5" aria-labelledby="smoke-channel-selection">
                  <h2 id="smoke-channel-selection" className="text-sm font-semibold text-ink-100">
                    Channels
                  </h2>
                  <p className="mt-1 text-xs leading-relaxed text-ink-400">
                    Select up to eight channels. Channels are grouped by unit and raw/calibrated
                    status. Channels without a stated unit are plotted as raw signals, not physical
                    measurements.
                  </p>
                  <div className="mt-3">
                    <ChannelPicker
                      channels={runChannels}
                      selected={selected}
                      onChange={(next) => updateDraft({ selected: next })}
                      disabled={series.isFetching}
                    />
                  </div>
                </section>

                <section className="surface p-5" aria-labelledby="smoke-series-controls">
                  <h2 id="smoke-series-controls" className="text-sm font-semibold text-ink-100">
                    Time range and request size
                  </h2>
                  <p className="mt-1 text-xs leading-relaxed text-ink-400">
                    Bounds are inclusive and expressed in elapsed test seconds. The API returns at
                    most the requested number of distinct timestamps.
                  </p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <TextFilter
                      id="smoke-start"
                      label="Start (s)"
                      type="number"
                      step={0.1}
                      value={startText}
                      onChange={(value) => updateDraft({ startText: value })}
                    />
                    <TextFilter
                      id="smoke-end"
                      label="End (s)"
                      type="number"
                      step={0.1}
                      value={endText}
                      onChange={(value) => updateDraft({ endText: value })}
                    />
                    <TextFilter
                      id="smoke-max-points"
                      label="Max points (1–20,000)"
                      type="number"
                      min={1}
                      max={20_000}
                      step={1}
                      value={maxPointsText}
                      onChange={(value) => updateDraft({ maxPointsText: value })}
                      hint="No interpolation or browser downsampling."
                    />
                    <div className="flex items-end">
                      <button
                        type="button"
                        onClick={applySeries}
                        className={buttonStyles({ variant: "primary", className: "w-full" })}
                        disabled={selected.length === 0}
                      >
                        <RefreshCw className="size-4" aria-hidden="true" />
                        Load series
                      </button>
                    </div>
                  </div>
                  <p className="mt-2 text-[10px] leading-relaxed text-ink-500">
                    Run bounds: {formatNumber(runMin)}–{formatNumber(runMax)} s. A request whose
                    distinct timestamp count exceeds max points returns HTTP 413 with a suggested
                    narrower span; the interface never retries with a silently reduced range.
                  </p>
                  {formError ? (
                    <InlineAlert tone="warning" className="mt-3">
                      {formError}
                    </InlineAlert>
                  ) : null}
                  {selected.length === 0 ? (
                    <InlineAlert tone="info" className="mt-3">
                      Select at least one channel, then load the series.
                    </InlineAlert>
                  ) : null}
                </section>
              </div>

              <section aria-labelledby="smoke-series-result">
                <h2 id="smoke-series-result" className="mb-3 text-sm font-semibold text-ink-100">
                  Returned series
                </h2>
                {!appliedRangeValid ? (
                  <InlineAlert tone="warning">
                    The applied range is outside the run bounds or start is not less than end. No
                    series request was made.
                  </InlineAlert>
                ) : appliedChannels.length === 0 ? (
                  <InlineAlert tone="info">
                    No channels are applied. The chart is not drawn and no data is substituted.
                  </InlineAlert>
                ) : series.isPending ? (
                  <LoadingState label="Loading the bounded smoke series…" rows={4} />
                ) : series.isError ? (
                  <div className="space-y-3">
                    <ErrorState
                      error={series.error}
                      title="The smoke series could not be loaded"
                      onRetry={() => series.refetch()}
                    />
                    {rangeError && Number.isFinite(suggestedSpan) ? (
                      <div className="surface p-4">
                        <p className="text-xs leading-relaxed text-ink-300">
                          The API reports{" "}
                          {actualPoints !== null && Number.isFinite(actualPoints)
                            ? formatCount(actualPoints)
                            : "too many"}{" "}
                          distinct timestamps for this request. A span of about{" "}
                          <span className="mono text-ink-100">{formatNumber(suggestedSpan)} s</span>{" "}
                          would fit the current max-points limit. This action narrows the end of the
                          range; it does not change the measurement.
                        </p>
                        <button
                          type="button"
                          className={buttonStyles({ size: "sm", className: "mt-3" })}
                          onClick={() => {
                            const nextEnd = Math.min(runMax, appliedStart + suggestedSpan);
                            setDraftState(null);
                            setFormError(null);
                            setParams({ start: appliedStart, end: nextEnd });
                          }}
                        >
                          Use suggested end = {formatNumber(Math.min(runMax, appliedStart + suggestedSpan))} s
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : series.data ? (
                  <div className="space-y-4">
                    <LazyTimeSeriesChart
                      series={series.data.data}
                      accession={runData.accession}
                      runId={runData.run_id}
                      sourceFile={runData.source_file}
                      sourceUrl={runData.source_url}
                      retrievedAt={runData.retrieved_at}
                      timeRangeLabel={`${formatNumber(appliedStart)}–${formatNumber(appliedEnd)} s`}
                    />
                    <Disclosure
                      summary={`Response quality and channel metadata (${series.data.quality.flags.length} flags)`}
                    >
                      <div className="space-y-4">
                        <QualityBanner
                          quality={series.data.quality}
                          title="Smoke series response quality"
                        />
                        <div className="table-scroll rounded border border-navy-700/60">
                          <table className="w-full min-w-[720px] text-left text-[10px]">
                            <caption className="sr-only">Selected smoke channel metadata</caption>
                            <thead className="bg-navy-900">
                              <tr>
                                <th scope="col" className={TH_CLASS}>Canonical channel</th>
                                <th scope="col" className={TH_CLASS}>Raw name</th>
                                <th scope="col" className={TH_CLASS}>Unit</th>
                                <th scope="col" className={TH_CLASS}>Flags</th>
                              </tr>
                            </thead>
                            <tbody>
                              {series.data.data.channels.map((channel) => (
                                <tr key={channel.channel_name_canonical}>
                                  <td className={TD_CLASS}>{channel.channel_name_canonical}</td>
                                  <td className={`${TD_CLASS} break-all`}>
                                    {channel.channel_name_raw}
                                  </td>
                                  <td className={TD_CLASS}>{channel.unit}</td>
                                  <td className={TD_CLASS}>
                                    {channel.quality_flags.join(", ") || "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <p className="text-[10px] text-ink-500">
                          Request {series.data.meta.request_id}. Dataset version{" "}
                          <span className="mono">{series.data.meta.dataset_version ?? "—"}</span>.
                        </p>
                      </div>
                    </Disclosure>
                  </div>
                ) : null}
              </section>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function SmokeRunFacts({ run }: { run: SmokeRunSummary }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-xl border border-navy-700/60 bg-navy-950/35 p-3 text-[10px]">
      <div>
        <dt className="text-ink-500">Valid rows</dt>
        <dd className="font-mono text-ink-300">{formatCount(run.valid_rows)}</dd>
      </div>
      <div>
        <dt className="text-ink-500">Channels</dt>
        <dd className="font-mono text-ink-300">{run.channel_count}</dd>
      </div>
      <div>
        <dt className="text-ink-500">Elapsed time</dt>
        <dd className="font-mono text-ink-300">
          {formatNumber(run.elapsed_test_time_min_s)}–{formatNumber(run.elapsed_test_time_max_s)} s
        </dd>
      </div>
      <div>
        <dt className="text-ink-500">Sentinel-time rows</dt>
        <dd className="font-mono text-ink-300">{formatCount(run.sentinel_time_rows)}</dd>
      </div>
      <div className="col-span-2">
        <dt className="text-ink-500">Checksum</dt>
        <dd className="break-all font-mono text-ink-400">{run.sha256}</dd>
      </div>
    </dl>
  );
}

export default function SmokePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading smoke explorer…" rows={4} />}>
      <SmokeContent />
    </Suspense>
  );
}
