"use client";

import {
  keepPreviousData,
  useQuery,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./endpoints";
import type {
  DatasetParams,
  DropletParams,
  GasFlameParams,
  InvestigationParams,
  MaterialParams,
  MeasurementParams,
  PageParams,
  SmokeSeriesParams,
  TelemetrySeriesParams,
} from "./endpoints";
import { queryKeys } from "./query-keys";
import type {
  ComparabilitySummary,
  ComparisonDecision,
  DatasetDetail,
  DatasetQuality,
  DatasetSummary,
  DropletRow,
  Envelope,
  GasFlameRow,
  HealthData,
  Investigation,
  InvestigationDetail,
  MaterialRow,
  Measurement,
  MetaData,
  ProvenanceResponse,
  SmokeRunDetail,
  SmokeRunSummary,
  SmokeSeries,
  TelemetryRunDetail,
  TelemetryRunSummary,
  TelemetrySeries,
} from "./types";

type QueryOptions<T> = Omit<
  UseQueryOptions<Envelope<T>, Error, Envelope<T>>,
  "queryKey" | "queryFn"
>;

function listOptions<T>(): QueryOptions<T> {
  return {
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  };
}

export function useHealth(options?: QueryOptions<HealthData>) {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => api.getHealth(signal),
    staleTime: 30_000,
    refetchInterval: 60_000,
    ...options,
  });
}

export function useMeta(options?: QueryOptions<MetaData>) {
  return useQuery({
    queryKey: queryKeys.meta,
    queryFn: ({ signal }) => api.getMeta(signal),
    staleTime: 60_000,
    ...options,
  });
}

export function useInvestigations(
  params: InvestigationParams = {},
  options?: QueryOptions<Investigation[]>,
) {
  return useQuery({
    queryKey: queryKeys.investigations(params),
    queryFn: ({ signal }) => api.getInvestigations(params, signal),
    ...listOptions<Investigation[]>(),
    ...options,
  });
}

export function useInvestigation(
  accession: string,
  options?: QueryOptions<InvestigationDetail>,
) {
  return useQuery({
    queryKey: queryKeys.investigation(accession),
    queryFn: ({ signal }) => api.getInvestigation(accession, signal),
    enabled: Boolean(accession),
    staleTime: 60_000,
    ...options,
  });
}

export function useDatasets(
  params: DatasetParams = {},
  options?: QueryOptions<DatasetSummary[]>,
) {
  return useQuery({
    queryKey: queryKeys.datasets(params),
    queryFn: ({ signal }) => api.getDatasets(params, signal),
    ...listOptions<DatasetSummary[]>(),
    ...options,
  });
}

export function useDataset(datasetId: string, options?: QueryOptions<DatasetDetail>) {
  return useQuery({
    queryKey: queryKeys.dataset(datasetId),
    queryFn: ({ signal }) => api.getDataset(datasetId, signal),
    enabled: Boolean(datasetId),
    staleTime: 60_000,
    ...options,
  });
}

export function useDatasetsQuality(options?: QueryOptions<DatasetQuality[]>) {
  return useQuery({
    queryKey: queryKeys.datasetsQuality,
    queryFn: ({ signal }) => api.getDatasetsQuality(signal),
    staleTime: 60_000,
    ...options,
  });
}

export function useDatasetQuality(
  datasetId: string,
  options?: QueryOptions<DatasetQuality>,
) {
  return useQuery({
    queryKey: queryKeys.datasetQuality(datasetId),
    queryFn: ({ signal }) => api.getDatasetQuality(datasetId, signal),
    enabled: Boolean(datasetId),
    staleTime: 60_000,
    ...options,
  });
}

export function useMeasurements(
  params: MeasurementParams = {},
  options?: QueryOptions<Measurement[]>,
) {
  return useQuery({
    queryKey: queryKeys.measurements(params),
    queryFn: ({ signal }) => api.getMeasurements(params, signal),
    ...listOptions<Measurement[]>(),
    ...options,
  });
}

export function useMeasurement(
  measurementId: string,
  options?: QueryOptions<Measurement>,
) {
  return useQuery({
    queryKey: queryKeys.measurement(measurementId),
    queryFn: ({ signal }) => api.getMeasurement(measurementId, signal),
    enabled: Boolean(measurementId),
    staleTime: 60_000,
    ...options,
  });
}

export function useGasFlameTests(
  params: GasFlameParams = {},
  options?: QueryOptions<GasFlameRow[]>,
) {
  return useQuery({
    queryKey: queryKeys.gasFlame(params),
    queryFn: ({ signal }) => api.getGasFlameTests(params, signal),
    ...listOptions<GasFlameRow[]>(),
    ...options,
  });
}

export function useMaterialTests(
  params: MaterialParams = {},
  options?: QueryOptions<MaterialRow[]>,
) {
  return useQuery({
    queryKey: queryKeys.material(params),
    queryFn: ({ signal }) => api.getMaterialTests(params, signal),
    ...listOptions<MaterialRow[]>(),
    ...options,
  });
}

export function useDropletTests(
  params: DropletParams = {},
  options?: QueryOptions<DropletRow[]>,
) {
  return useQuery({
    queryKey: queryKeys.droplet(params),
    queryFn: ({ signal }) => api.getDropletTests(params, signal),
    ...listOptions<DropletRow[]>(),
    ...options,
  });
}

export function useTelemetryRuns(
  params: PageParams & { accession?: string; export_kind?: string } = {},
  options?: QueryOptions<TelemetryRunSummary[]>,
) {
  return useQuery({
    queryKey: queryKeys.telemetryRuns(params),
    queryFn: ({ signal }) => api.getTelemetryRuns(params, signal),
    ...listOptions<TelemetryRunSummary[]>(),
    ...options,
  });
}

export function useTelemetryRun(
  runId: string,
  options?: QueryOptions<TelemetryRunDetail>,
) {
  return useQuery({
    queryKey: queryKeys.telemetryRun(runId),
    queryFn: ({ signal }) => api.getTelemetryRun(runId, signal),
    enabled: Boolean(runId),
    staleTime: 60_000,
    ...options,
  });
}

export function useTelemetrySeries(
  runId: string,
  params: TelemetrySeriesParams | null,
  options?: QueryOptions<TelemetrySeries>,
) {
  return useQuery({
    queryKey: queryKeys.telemetrySeries(runId, params),
    queryFn: ({ signal }) => api.getTelemetrySeries(runId, params!, signal),
    enabled: Boolean(runId && params && params.channels.length > 0),
    staleTime: 30_000,
    ...options,
  });
}

export function useSmokeRuns(
  params: PageParams & { accession?: string } = {},
  options?: QueryOptions<SmokeRunSummary[]>,
) {
  return useQuery({
    queryKey: queryKeys.smokeRuns(params),
    queryFn: ({ signal }) => api.getSmokeRuns(params, signal),
    ...listOptions<SmokeRunSummary[]>(),
    ...options,
  });
}

export function useSmokeRun(runId: string, options?: QueryOptions<SmokeRunDetail>) {
  return useQuery({
    queryKey: queryKeys.smokeRun(runId),
    queryFn: ({ signal }) => api.getSmokeRun(runId, signal),
    enabled: Boolean(runId),
    staleTime: 60_000,
    ...options,
  });
}

export function useSmokeSeries(
  runId: string,
  params: SmokeSeriesParams | null,
  options?: QueryOptions<SmokeSeries>,
) {
  return useQuery({
    queryKey: queryKeys.smokeSeries(runId, params),
    queryFn: ({ signal }) => api.getSmokeSeries(runId, params!, signal),
    enabled: Boolean(runId && params && params.channels.length > 0),
    staleTime: 30_000,
    ...options,
  });
}

export function useComparability(options?: QueryOptions<ComparabilitySummary>) {
  return useQuery({
    queryKey: queryKeys.comparability,
    queryFn: ({ signal }) => api.getComparability(signal),
    staleTime: 60_000,
    ...options,
  });
}

export function useComparison(
  left: string,
  right: string,
  conditions: Record<string, boolean | null> | undefined,
  enabled: boolean,
  options?: QueryOptions<ComparisonDecision>,
) {
  return useQuery({
    queryKey: queryKeys.comparison(left, right, conditions),
    queryFn: ({ signal }) => api.compare(left, right, conditions, signal),
    enabled: Boolean(enabled && left && right),
    staleTime: 30_000,
    ...options,
  });
}

export function useProvenance(
  params: { accession: string; file: string; sheet?: string; row?: number },
  enabled: boolean,
  options?: QueryOptions<ProvenanceResponse>,
) {
  return useQuery({
    queryKey: queryKeys.provenance(params),
    queryFn: ({ signal }) => api.getProvenance(params, signal),
    enabled: Boolean(enabled && params.accession && params.file),
    staleTime: 60_000,
    ...options,
  });
}
