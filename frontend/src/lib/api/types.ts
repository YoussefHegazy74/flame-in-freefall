export type ServingState =
  | "available"
  | "available_with_warnings"
  | "restricted"
  | "blocked"
  | "metadata_only";

export type QualityStatus =
  | "verified"
  | "partial"
  | "blocked"
  | "experimental_table_only"
  | "not_available";

export type ComparisonStatus =
  | "comparable"
  | "conditionally_comparable"
  | "not_comparable"
  | "blocked"
  | "insufficient_metadata";

export type ServingUse =
  | "exploration"
  | "quantitative_comparison"
  | "time_series"
  | "provenance";

export type UseStates = Record<ServingUse, ServingState>;

export type ValueKind = "measured" | "computed" | "raw" | "categorical" | "derived";

export type UnitStatus = "stated" | "not_stated" | "ambiguous" | "not_applicable";

export interface PageMeta {
  limit: number;
  offset: number;
  total: number;
  has_more: boolean;
  excluded_qualified_rows?: number;
  pressure_field?: string | null;
  pressure_unit?: string | null;
  o2_field?: string | null;
  o2_unit_note?: string | null;
  spread_rate_available?: boolean;
  [key: string]: unknown;
}

export interface ResponseMeta {
  request_id: string;
  registry_snapshot?: string | null;
  dataset_version?: string | null;
  registry_version?: string | null;
  retrieved_at?: string | null;
  generated_at: string;
  page?: PageMeta | null;
  [key: string]: unknown;
}

export interface Quality {
  status: QualityStatus;
  flags: string[];
  warnings?: string[];
}

export interface ProvenanceRecord {
  accession: string;
  file: string;
  sheet?: string | null;
  field?: string | null;
  rows?: number[];
  row_range?: [number, number] | number[];
  sha256?: string | null;
  retrieved_at?: string | null;
  source_url?: string | null;
}

export interface Envelope<T> {
  data: T;
  meta: ResponseMeta;
  provenance: ProvenanceRecord[];
  quality: Quality;
}

export interface Reason {
  code: string;
  message: string;
}

export interface ServingDecision {
  resource_type: string;
  resource_id: string;
  dataset_id: string;
  use: ServingUse;
  state: ServingState;
  base_state: ServingState;
  reasons: Reason[];
  restrictions: string[];
  registry_version: string;
  dataset_version: string;
}

export interface SourceReference {
  kind: string;
  accession?: string;
  file_name?: string;
  sha256?: string;
  source_url?: string;
  path?: string;
  section?: string;
}

export interface Investigation {
  accession: string;
  acronym: string;
  title: string;
  doi?: string | null;
  research_area: string;
  sub_research_area: string;
  project_type: string;
  start_date?: string | null;
  end_date?: string | null;
  version: number;
  public: boolean;
  restricted: boolean;
  file_count: number;
  removed_file_count: number;
  experimental_table_count: number;
  experimental_table_bytes: number;
  experimental_table_only_count: number;
  archive_status: string;
  registered_total_bytes: number;
  mvp_role: string;
  rationale: string;
  limitations: string[];
}

export interface DatasetSummary {
  dataset_id: string;
  accession: string;
  display_name: string;
  experiment_family: string;
  canonical_tables: string[];
  download_status: string;
  measurement_file_status: string;
  access_scope: string;
  base_state: ServingState;
  use_states: UseStates;
  measurement_count: number;
  reasons: Reason[];
  restrictions: string[];
  source_references: SourceReference[];
}

export interface InvestigationDetail extends Investigation {
  curated_datasets: DatasetSummary[];
}

export interface Measurement {
  measurement_id: string;
  dataset_id: string;
  accession: string;
  experiment_family: string;
  parameter: string;
  canonical_field: string | null;
  canonical_channel: string | null;
  physical_quantity: string;
  physical_meaning?: string;
  unit: string;
  unit_status: UnitStatus;
  measurement_method?: string;
  value_kind: ValueKind;
  calibration_status: string;
  availability: string;
  comparison_status: ComparisonStatus;
  compatible_datasets: string[];
  incompatible_datasets: string[];
  quality_restrictions: string[];
  serving_state: ServingState;
  use_states: UseStates;
  scientific_justification?: string;
  notes?: string;
  source_file_keys?: string[];
  source_references?: SourceReference[];
  serving?: ServingDecision;
}

export interface DatasetDetail extends DatasetSummary {
  serving: Record<ServingUse, ServingDecision>;
  measurements: Measurement[];
}

export interface QualityIssue {
  severity: "error" | "warning" | "info" | string;
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface DatasetQuality {
  dataset_id: string;
  accession: string;
  display_name: string;
  quality_status: QualityStatus;
  base_state: ServingState;
  use_states: UseStates;
  report_summary: {
    tables: number;
    total_rows: number;
    point_rows: number;
    issues: number;
    errors: number;
    warnings: number;
  };
  issues: QualityIssue[];
}

export interface QualityFlagDetail {
  field: string;
  raw_field: string;
  token: string;
  flag: string;
}

export type QualityFlag = string | QualityFlagDetail;

export interface ObservationBase {
  observation_id: string;
  accession: string;
  table_id: string;
  source_file: string;
  source_sheet?: string | null;
  source_row: number;
  source_sha256: string;
  retrieved_at: string;
  source_url: string;
  parser_version: string;
  quality_flags: QualityFlag[];
}

export interface GasFlameRow extends ObservationBase {
  flame_type: string | null;
  day: string | null;
  fuel: string | null;
  test_code: string | null;
  fuel_mole_fraction: number | null;
  fuel_mass_flow_mg_s: number | null;
  diluent_mass_flow_mg_s: number | null;
  total_mass_flow_mg_s: number | null;
  oxygen_mole_fraction: number | null;
  oxygen_mole_fraction_initial: number | null;
  oxygen_mole_fraction_final: number | null;
  oxygen_mole_fraction_before: number | null;
  oxygen_mole_fraction_after: number | null;
  pressure_initial_atm: number | null;
  pressure_final_atm: number | null;
  pressure_mean_atm: number | null;
  pressure_approx_bar: number | null;
  oxidizer_mass_flow_mg_s: number | null;
  fuel_mole_fraction_initial: number | null;
  fuel_mole_fraction_final: number | null;
  fuel_mole_fraction_before: number | null;
  fuel_mole_fraction_after: number | null;
  fuel_burn_rate_mg_s: number | null;
  stoich_mixture_fraction: number | null;
  adiabatic_flame_temp_k: number | null;
  cool_flame_flag: string | null;
  tfp_flag: string | null;
  hot_ignition: string | null;
  burn_time_s: number | null;
  extinction_mode: string | null;
  peak_burner_temp_c: number | null;
  peak_burner_temp_k: number | null;
  color: string | null;
  comments: string | null;
  computed_fields: string[];
}

export interface MaterialRow extends ObservationBase {
  record_type: string;
  test_date: string | null;
  gmt_day: string | null;
  as_run_test_no: string | null;
  test_no: string | null;
  sample_no: string | null;
  material: string | null;
  flow_restrictor: string | null;
  fan_display: string | null;
  air_display: string | null;
  radiometer_gain: string | null;
  total_frames: string | null;
  initial_o2_pct: number | null;
  final_o2_pct: number | null;
  o2_pct: number | null;
  initial_co2_pct: number | null;
  final_co2_pct: number | null;
  initial_co_ppm: number | null;
  final_co_ppm: number | null;
  pressure_atm: number | null;
  co2_mm_hg: number | null;
  observations: string | null;
}

export interface DropletRow extends ObservationBase {
  flex_test_number: number | null;
  test_date: string | null;
  flex_identifier: string | null;
  test_gmt: string | null;
  fuel: string | null;
  ambient_pressure_mm_hg: number | null;
  o2_initial_mole_fraction: number | null;
  n2_initial_mole_fraction: number | null;
  co_initial_mole_fraction: number | null;
  he_initial_mole_fraction: number | null;
  droplet_initial_diameter_mm: number | null;
  visible_flame_extinction_diameter_mm: number | null;
  burning_rate_mm_as_labeled: number | null;
  burn_time_s: number | null;
  test_end: string | null;
}

export interface TelemetryRunSummary {
  run_id: string;
  accession: string;
  source_file: string;
  source_sheet?: string | null;
  export_kind: string;
  physical_rows: number;
  empty_rows: number;
  invalid_time_rows: number;
  sentinel_rows: number;
  valid_rows: number;
  time_min_ms: number;
  time_max_ms: number;
  column_count: number;
  channel_count: number;
  sha256: string;
  retrieved_at: string;
  source_url: string;
  parser_version: string;
  notes: string | null;
  time_unit: "ms";
}

export interface SeriesChannel {
  channel_name_raw: string;
  channel_name_canonical: string;
  unit: string;
  quality_flags: string[];
  point_count?: number;
  missing_count?: number;
  sentinel_count?: number;
  min?: number | null;
  max?: number | null;
  constant?: boolean;
}

export interface TelemetryRunDetail extends TelemetryRunSummary {
  channels: SeriesChannel[];
}

export interface TelemetrySeries {
  run_id: string;
  time_unit: "ms";
  channels: SeriesChannel[];
  points: Array<Record<string, number | null>>;
  returned_points: number;
  excluded_sentinel_rows: number;
}

export interface SmokeRunSummary {
  run_id: string;
  accession: string;
  source_file: string;
  test_number: string | null;
  sample_number: string | null;
  carousel_number: number | null;
  test_numbers_json: string;
  sample_numbers_json: string;
  carousel_numbers_json: string;
  run_mode_codes_json: string;
  time_min_unix_s: number | null;
  time_max_unix_s: number | null;
  elapsed_test_time_min_s: number | null;
  elapsed_test_time_max_s: number | null;
  physical_rows: number;
  empty_rows: number;
  malformed_rows: number;
  invalid_time_rows: number;
  sentinel_time_rows: number;
  valid_rows: number;
  column_count: number;
  channel_count: number;
  issues_json: string;
  sha256: string;
  retrieved_at: string;
  source_url: string;
  parser_version: string;
  notes: string | null;
  time_unit: "s";
}

export interface SmokeRunDetail extends SmokeRunSummary {
  channels: SeriesChannel[];
  limitations?: string[];
}

export interface SmokeSeries {
  run_id: string;
  time_unit: "s";
  channels: SeriesChannel[];
  points: Array<Record<string, number | null>>;
  returned_points: number;
  excluded_sentinel_rows: number;
}

export interface RequiredCondition {
  key: string;
  description: string;
  satisfied: boolean | null;
}

export interface ComparisonMeasurement {
  measurement_id: string;
  dataset_id: string;
  accession: string;
  experiment_family: string;
  parameter: string;
  canonical_field: string | null;
  canonical_channel: string | null;
  physical_quantity: string;
  unit: string;
  unit_status: UnitStatus;
  value_kind: ValueKind;
  calibration_status: string;
  availability: string;
  comparison_status: ComparisonStatus;
  quality_restrictions: string[];
}

export interface ComparisonDecision {
  left: ComparisonMeasurement;
  right: ComparisonMeasurement;
  status: ComparisonStatus;
  rule_id: string | null;
  reasons: Reason[];
  required_conditions: RequiredCondition[];
  warnings: string[];
  scientific_justification: string;
  source_references: SourceReference[];
  registry_version: string;
  dataset_version: string;
}

export interface RegistryMeasurement extends ComparisonMeasurement {
  compatible_datasets: string[];
  incompatible_datasets: string[];
  serving_state: ServingState;
  use_states: UseStates;
}

export interface ComparisonRule {
  rule_id: string;
  left_measurement_id: string;
  right_measurement_id: string;
  status: ComparisonStatus;
  required_conditions: Array<{ key: string; description: string }>;
  policies: Record<string, string>;
  scientific_justification: string;
  notes: string;
  source_references: SourceReference[];
}

export interface ComparabilitySummary {
  registry_version: string;
  dataset_version: string;
  default_policy: {
    status: ComparisonStatus;
    justification: string;
    engine_behavior: string;
  };
  state_definitions: Record<
    ComparisonStatus,
    { definition: string; engine_behavior: string }
  >;
  measurement_status_counts: Partial<Record<ComparisonStatus, number>>;
  rule_status_counts: Partial<Record<ComparisonStatus, number>>;
  measurement_count: number;
  rule_count: number;
  concepts: Array<{
    physical_quantity: string;
    units: string[];
    dataset_ids: string[];
    measurement_ids: string[];
    comparison_statuses: Partial<Record<ComparisonStatus, number>>;
  }>;
  measurements: RegistryMeasurement[];
  rules: ComparisonRule[];
}

export interface ProvenanceResponse {
  origin: string;
  accession: string;
  file: string;
  sheet: string | null;
  sha256: string | null;
  retrieved_at: string | null;
  bytes: number | null;
  source_url: string | null;
  row: number | null;
  row_verified: boolean | null;
  row_tables: string[];
  warnings: string[];
}

export interface HealthData {
  status: string;
  api_version: string;
  registry_snapshot: string;
  dataset_version: string;
  registry_version: string;
  database: string;
  assistant: string;
  available_tables: number;
  missing_tables: string[];
}

export interface MetaDataset {
  dataset_id: string;
  accession: string;
  display_name: string;
  base_state: ServingState;
  use_states: UseStates;
  measurement_count: number;
}

export interface MetaData {
  api_version: string;
  registry_snapshot: string;
  dataset_version: string;
  registry_version: string;
  canonical_tables: Record<string, number>;
  canonical_rows: number;
  investigations_total: number;
  curated_dataset_count: number;
  measurement_count: number;
  comparison_rule_count: number;
  datasets: MetaDataset[];
}
