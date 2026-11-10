import { apiRequest, type QueryParams } from "./client";
import type {
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

export interface PageParams {
  limit?: number;
  offset?: number;
}

export interface InvestigationParams extends PageParams {
  role?: string;
  q?: string;
}

export interface DatasetParams extends PageParams {
  family?: string;
  accession?: string;
  state?: string;
  use?: string;
}

export interface MeasurementParams extends PageParams {
  accession?: string;
  family?: string;
  dataset_id?: string;
  comparison_status?: string;
  serving_state?: string;
  use?: string;
}

export interface GasFlameParams extends PageParams {
  accession?: string;
  flame_type?: string;
  fuel?: string;
  oxygen_min?: number;
  oxygen_max?: number;
  pressure_min?: number;
  pressure_max?: number;
  hot_ignition?: string;
  extinction_mode?: string;
  tfp?: string;
  include_qualified?: boolean;
  sort?: string;
  order?: "asc" | "desc";
}

export interface MaterialParams extends PageParams {
  accession?: string;
  material?: string;
  flow_restrictor?: string;
  o2_min?: number;
  o2_max?: number;
}

export interface DropletParams extends PageParams {
  accession?: string;
  fuel?: string;
  pressure_min?: number;
  pressure_max?: number;
}

export interface TelemetrySeriesParams {
  channels: string[];
  start_ms: number;
  end_ms: number;
  max_points?: number;
}

export interface SmokeSeriesParams {
  channels: string[];
  start_s: number;
  end_s: number;
  max_points?: number;
}

export interface CitationParams extends PageParams {
  accession?: string;
  dataset_id?: string;
  kind?: string;
  verification_status?: string;
  availability?: string;
}

export interface DatasetFileParams extends PageParams {
  kind?: string;
  availability?: string;
}

export interface DatasetFieldParams extends PageParams {
  value_kind?: string;
  physical_quantity?: string;
  comparison_status?: string;
}

export interface DatasetLimitationParams extends PageParams {
  scope?: string;
  category?: string;
  severity?: string;
  status?: string;
}

export interface PublicationParams extends PageParams {
  accession?: string;
  dataset_id?: string;
  q?: string;
  year?: number;
  status?: string;
}

export interface GasFlameFacetParams {
  accession?: string;
  include_qualified?: boolean;
}

function pageQuery(params: PageParams): QueryParams {
  return { limit: params.limit, offset: params.offset };
}

export const api = {
  getHealth(signal?: AbortSignal) {
    return apiRequest<HealthData>("/health", { signal, timeoutMs: 8_000 });
  },

  getMeta(signal?: AbortSignal) {
    return apiRequest<MetaData>("/meta", { signal });
  },

  getInvestigations(params: InvestigationParams = {}, signal?: AbortSignal) {
    return apiRequest<Investigation[]>("/investigations", {
      query: { ...pageQuery(params), role: params.role, q: params.q },
      signal,
    });
  },

  getInvestigation(accession: string, signal?: AbortSignal) {
    return apiRequest<InvestigationDetail>(
      `/investigations/${encodeURIComponent(accession)}`,
      { signal },
    );
  },

  getDatasets(params: DatasetParams = {}, signal?: AbortSignal) {
    return apiRequest<DatasetSummary[]>("/datasets", {
      query: {
        ...pageQuery(params),
        family: params.family,
        accession: params.accession,
        state: params.state,
        use: params.use,
      },
      signal,
    });
  },

  getDataset(datasetId: string, signal?: AbortSignal) {
    return apiRequest<DatasetDetail>(`/datasets/${encodeURIComponent(datasetId)}`, {
      signal,
    });
  },

  getDatasetQuality(datasetId: string, signal?: AbortSignal) {
    return apiRequest<DatasetQuality>(
      `/datasets/${encodeURIComponent(datasetId)}/quality`,
      { signal },
    );
  },

  getDatasetFiles(
    datasetId: string,
    params: DatasetFileParams = {},
    signal?: AbortSignal,
  ) {
    return apiRequest<DatasetFilesResponse>(
      `/datasets/${encodeURIComponent(datasetId)}/files`,
      {
        query: {
          ...pageQuery(params),
          kind: params.kind,
          availability: params.availability,
        },
        signal,
      },
    );
  },

  getDatasetFields(
    datasetId: string,
    params: DatasetFieldParams = {},
    signal?: AbortSignal,
  ) {
    return apiRequest<DatasetFieldsResponse>(
      `/datasets/${encodeURIComponent(datasetId)}/fields`,
      {
        query: {
          ...pageQuery(params),
          value_kind: params.value_kind,
          physical_quantity: params.physical_quantity,
          comparison_status: params.comparison_status,
        },
        signal,
      },
    );
  },

  getDatasetLimitations(
    datasetId: string,
    params: DatasetLimitationParams = {},
    signal?: AbortSignal,
  ) {
    return apiRequest<DatasetLimitationsResponse>(
      `/datasets/${encodeURIComponent(datasetId)}/limitations`,
      {
        query: {
          ...pageQuery(params),
          scope: params.scope,
          category: params.category,
          severity: params.severity,
          status: params.status,
        },
        signal,
      },
    );
  },

  getDatasetsQuality(signal?: AbortSignal) {
    return apiRequest<DatasetQuality[]>("/datasets/quality", { signal });
  },

  getMeasurements(params: MeasurementParams = {}, signal?: AbortSignal) {
    return apiRequest<Measurement[]>("/measurements", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        family: params.family,
        dataset_id: params.dataset_id,
        comparison_status: params.comparison_status,
        serving_state: params.serving_state,
        use: params.use,
      },
      signal,
    });
  },

  getMeasurement(measurementId: string, signal?: AbortSignal) {
    return apiRequest<Measurement>(
      `/measurements/${encodeURIComponent(measurementId)}`,
      { signal },
    );
  },

  getGasFlameTests(params: GasFlameParams = {}, signal?: AbortSignal) {
    return apiRequest<GasFlameRow[]>("/gas-flame/tests", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        flame_type: params.flame_type,
        fuel: params.fuel,
        oxygen_min: params.oxygen_min,
        oxygen_max: params.oxygen_max,
        pressure_min: params.pressure_min,
        pressure_max: params.pressure_max,
        hot_ignition: params.hot_ignition,
        extinction_mode: params.extinction_mode,
        tfp: params.tfp,
        include_qualified: params.include_qualified,
        sort: params.sort,
        order: params.order,
      },
      signal,
    });
  },

  getGasFlameTest(observationId: string, signal?: AbortSignal) {
    return apiRequest<GasFlameRow>(
      `/gas-flame/tests/${encodeURIComponent(observationId)}`,
      { signal },
    );
  },

  getGasFlameFacets(params: GasFlameFacetParams = {}, signal?: AbortSignal) {
    return apiRequest<GasFlameFacets>("/gas-flame/facets", {
      query: {
        accession: params.accession,
        include_qualified: params.include_qualified,
      },
      signal,
    });
  },

  getMaterialTests(params: MaterialParams = {}, signal?: AbortSignal) {
    return apiRequest<MaterialRow[]>("/material/tests", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        material: params.material,
        flow_restrictor: params.flow_restrictor,
        o2_min: params.o2_min,
        o2_max: params.o2_max,
      },
      signal,
    });
  },

  getDropletTests(params: DropletParams = {}, signal?: AbortSignal) {
    return apiRequest<DropletRow[]>("/droplet/tests", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        fuel: params.fuel,
        pressure_min: params.pressure_min,
        pressure_max: params.pressure_max,
      },
      signal,
    });
  },

  getTelemetryRuns(params: PageParams & { accession?: string; export_kind?: string } = {}, signal?: AbortSignal) {
    return apiRequest<TelemetryRunSummary[]>("/telemetry/runs", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        export_kind: params.export_kind,
      },
      signal,
    });
  },

  getTelemetryRun(runId: string, signal?: AbortSignal) {
    return apiRequest<TelemetryRunDetail>(
      `/telemetry/runs/${encodeURIComponent(runId)}`,
      { signal },
    );
  },

  getTelemetrySeries(
    runId: string,
    params: TelemetrySeriesParams,
    signal?: AbortSignal,
  ) {
    return apiRequest<TelemetrySeries>(
      `/telemetry/runs/${encodeURIComponent(runId)}/series`,
      {
        query: {
          channels: params.channels,
          start_ms: params.start_ms,
          end_ms: params.end_ms,
          max_points: params.max_points,
        },
        signal,
        timeoutMs: 30_000,
      },
    );
  },

  getSmokeRuns(params: PageParams & { accession?: string } = {}, signal?: AbortSignal) {
    return apiRequest<SmokeRunSummary[]>("/smoke/runs", {
      query: { ...pageQuery(params), accession: params.accession },
      signal,
    });
  },

  getSmokeRun(runId: string, signal?: AbortSignal) {
    return apiRequest<SmokeRunDetail>(`/smoke/runs/${encodeURIComponent(runId)}`, {
      signal,
    });
  },

  getSmokeSeries(runId: string, params: SmokeSeriesParams, signal?: AbortSignal) {
    return apiRequest<SmokeSeries>(
      `/smoke/runs/${encodeURIComponent(runId)}/series`,
      {
        query: {
          channels: params.channels,
          start_s: params.start_s,
          end_s: params.end_s,
          max_points: params.max_points,
        },
        signal,
        timeoutMs: 30_000,
      },
    );
  },

  getComparability(signal?: AbortSignal) {
    return apiRequest<ComparabilitySummary>("/comparability", { signal });
  },

  getCitations(params: CitationParams = {}, signal?: AbortSignal) {
    return apiRequest<Citation[]>("/citations", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        dataset_id: params.dataset_id,
        kind: params.kind,
        verification_status: params.verification_status,
        availability: params.availability,
      },
      signal,
    });
  },

  getCitation(citationId: string, signal?: AbortSignal) {
    return apiRequest<Citation>(`/citations/${encodeURIComponent(citationId)}`, {
      signal,
    });
  },

  getPublications(params: PublicationParams = {}, signal?: AbortSignal) {
    return apiRequest<PublicationsResponse>("/publications", {
      query: {
        ...pageQuery(params),
        accession: params.accession,
        dataset_id: params.dataset_id,
        q: params.q,
        year: params.year,
        status: params.status,
      },
      signal,
    });
  },

  getPublication(publicationId: string, signal?: AbortSignal) {
    return apiRequest<Publication>(
      `/publications/${encodeURIComponent(publicationId)}`,
      { signal },
    );
  },

  compare(
    left: string,
    right: string,
    conditions?: Record<string, boolean | null>,
    signal?: AbortSignal,
  ) {
    return apiRequest<ComparisonDecision>("/compare", {
      query: {
        left,
        right,
        conditions: conditions ? JSON.stringify(conditions) : undefined,
      },
      signal,
    });
  },

  getProvenance(
    params: { accession: string; file: string; sheet?: string; row?: number },
    signal?: AbortSignal,
  ) {
    return apiRequest<ProvenanceResponse>("/provenance", {
      query: {
        accession: params.accession,
        file: params.file,
        sheet: params.sheet,
        row: params.row,
      },
      signal,
    });
  },
};
