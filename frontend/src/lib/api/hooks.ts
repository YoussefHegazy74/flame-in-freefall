"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./endpoints";
import type {
  CitationParams,
  DatasetFieldParams,
  DatasetFileParams,
  DatasetLimitationParams,
  DatasetParams,
  DropletParams,
  GasFlameFacetParams,
  GasFlameParams,
  InvestigationParams,
  MaterialParams,
  MeasurementParams,
  PageParams,
  PublicationParams,
  SmokeSeriesParams,
  TelemetrySeriesParams,
} from "./endpoints";
import { queryKeys } from "./query-keys";
import type {
  AssistantAnswer,
  AssistantQueryParams,
  AssistantStatus,
  AssistantSuggestionsResponse,
  AssistantToolsResponse,
  Citation,
  ComparabilitySummary,
  ComparisonDecision,
  DatasetDetail,
  DatasetFieldsResponse,
  DatasetFilesResponse,
  DatasetLimitationsResponse,
  DatasetQuality,
  DatasetSummary,
  DropletRow,
  Envelope,
  GasFlameFacets,
  GasFlameRow,
  HealthData,
  Investigation,
  InvestigationDetail,
  MaterialRow,
  Measurement,
  MetaData,
  ProvenanceResponse,
  Publication,
  PublicationsResponse,
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

export function useDatasetFiles(
  datasetId: string,
  params: DatasetFileParams = {},
  options?: QueryOptions<DatasetFilesResponse>,
) {
  return useQuery({
    queryKey: queryKeys.datasetFiles(datasetId, params),
    queryFn: ({ signal }) => api.getDatasetFiles(datasetId, params, signal),
    enabled: Boolean(datasetId),
    ...listOptions<DatasetFilesResponse>(),
    ...options,
  });
}

export function useDatasetFields(
  datasetId: string,
  params: DatasetFieldParams = {},
  options?: QueryOptions<DatasetFieldsResponse>,
) {
  return useQuery({
    queryKey: queryKeys.datasetFields(datasetId, params),
    queryFn: ({ signal }) => api.getDatasetFields(datasetId, params, signal),
    enabled: Boolean(datasetId),
    ...listOptions<DatasetFieldsResponse>(),
    ...options,
  });
}

export function useDatasetLimitations(
  datasetId: string,
  params: DatasetLimitationParams = {},
  options?: QueryOptions<DatasetLimitationsResponse>,
) {
  return useQuery({
    queryKey: queryKeys.datasetLimitations(datasetId, params),
    queryFn: ({ signal }) => api.getDatasetLimitations(datasetId, params, signal),
    enabled: Boolean(datasetId),
    ...listOptions<DatasetLimitationsResponse>(),
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

export function useGasFlameFacets(
  params: GasFlameFacetParams = {},
  options?: QueryOptions<GasFlameFacets>,
) {
  return useQuery({
    queryKey: queryKeys.gasFlameFacets(params),
    queryFn: ({ signal }) => api.getGasFlameFacets(params, signal),
    staleTime: 60_000,
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

export function useCitations(
  params: CitationParams = {},
  options?: QueryOptions<Citation[]>,
) {
  return useQuery({
    queryKey: queryKeys.citations(params),
    queryFn: ({ signal }) => api.getCitations(params, signal),
    ...listOptions<Citation[]>(),
    ...options,
  });
}

export function useCitation(
  citationId: string,
  enabled = true,
  options?: QueryOptions<Citation>,
) {
  return useQuery({
    queryKey: queryKeys.citation(citationId),
    queryFn: ({ signal }) => api.getCitation(citationId, signal),
    enabled: Boolean(enabled && citationId),
    staleTime: 60_000,
    ...options,
  });
}

export function usePublications(
  params: PublicationParams = {},
  options?: QueryOptions<PublicationsResponse>,
) {
  return useQuery({
    queryKey: queryKeys.publications(params),
    queryFn: ({ signal }) => api.getPublications(params, signal),
    ...listOptions<PublicationsResponse>(),
    ...options,
  });
}

export function usePublication(
  publicationId: string,
  options?: QueryOptions<Publication>,
) {
  return useQuery({
    queryKey: queryKeys.publication(publicationId),
    queryFn: ({ signal }) => api.getPublication(publicationId, signal),
    enabled: Boolean(publicationId),
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

// ----------------------------------------------------------------------
// Phase 5 assistant. Only the query is a mutation; it is still read-only
// science. Status, suggestions, and tools are ordinary bounded GETs.
// ----------------------------------------------------------------------
export function useAssistantStatus(
  includeIndex = false,
  options?: QueryOptions<AssistantStatus>,
) {
  return useQuery({
    queryKey: queryKeys.assistantStatus(includeIndex),
    queryFn: ({ signal }) =>
      api.getAssistantStatus(includeIndex, signal),
    staleTime: 30_000,
    refetchInterval: 60_000,
    ...options,
  });
}

export function useAssistantSuggestions(
  limit = 9,
  options?: QueryOptions<AssistantSuggestionsResponse>,
) {
  return useQuery({
    queryKey: queryKeys.assistantSuggestions(limit),
    queryFn: ({ signal }) => api.getAssistantSuggestions(limit, signal),
    staleTime: 5 * 60_000,
    ...options,
  });
}

export function useAssistantTools(options?: QueryOptions<AssistantToolsResponse>) {
  return useQuery({
    queryKey: queryKeys.assistantTools,
    queryFn: ({ signal }) => api.getAssistantTools(signal),
    staleTime: 5 * 60_000,
    ...options,
  });
}

export function useAssistantQuery(
  options?: Omit<
    UseMutationOptions<
      Envelope<AssistantAnswer>,
      Error,
      AssistantQueryParams
    >,
    "mutationFn"
  >,
) {
  return useMutation({
    mutationFn: (query: AssistantQueryParams) => api.queryAssistant(query),
    ...options,
  });
}
