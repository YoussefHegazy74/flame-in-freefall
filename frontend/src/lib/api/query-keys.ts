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

export const queryKeys = {
  health: ["health"] as const,
  meta: ["meta"] as const,
  investigations: (params: InvestigationParams) => ["investigations", params] as const,
  investigation: (accession: string) => ["investigation", accession] as const,
  datasets: (params: DatasetParams) => ["datasets", params] as const,
  dataset: (datasetId: string) => ["dataset", datasetId] as const,
  datasetsQuality: ["datasets-quality"] as const,
  datasetQuality: (datasetId: string) => ["dataset-quality", datasetId] as const,
  measurements: (params: MeasurementParams) => ["measurements", params] as const,
  measurement: (measurementId: string) => ["measurement", measurementId] as const,
  gasFlame: (params: GasFlameParams) => ["gas-flame", params] as const,
  gasFlameDetail: (observationId: string) => ["gas-flame-detail", observationId] as const,
  material: (params: MaterialParams) => ["material", params] as const,
  droplet: (params: DropletParams) => ["droplet", params] as const,
  telemetryRuns: (params: PageParams & { accession?: string; export_kind?: string }) =>
    ["telemetry-runs", params] as const,
  telemetryRun: (runId: string) => ["telemetry-run", runId] as const,
  telemetrySeries: (runId: string, params: TelemetrySeriesParams | null) =>
    ["telemetry-series", runId, params] as const,
  smokeRuns: (params: PageParams & { accession?: string }) => ["smoke-runs", params] as const,
  smokeRun: (runId: string) => ["smoke-run", runId] as const,
  smokeSeries: (runId: string, params: SmokeSeriesParams | null) =>
    ["smoke-series", runId, params] as const,
  comparability: ["comparability"] as const,
  comparison: (
    left: string,
    right: string,
    conditions?: Record<string, boolean | null>,
  ) => ["comparison", left, right, conditions ?? null] as const,
  provenance: (params: {
    accession: string;
    file: string;
    sheet?: string;
    row?: number;
  }) => ["provenance", params] as const,
};
