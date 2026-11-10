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
  citation_id?: string | null;
  file_citation_id?: string | null;
  row_citation_ids?: string[];
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
  field?: string;
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
  citation_id?: string;
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
  integrity?: ComparisonIntegrity;
  paired_values?: PairedValues;
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
  citation_id?: string | null;
  row_citation_ids?: string[];
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

/* ------------------------------------------------------------------ */
/* Phase 4: citations, dataset files/fields/limitations, publications  */
/* ------------------------------------------------------------------ */

export type CitationKind = "file" | "row";

export interface CitationFileInfo {
  name: string;
  kind: string;
  manifest_dataset: string | null;
  priority: string | null;
  purpose: string | null;
  in_added: boolean;
}

export interface CitationLocator {
  type: string;
  sheet: string | null;
  row: number | null;
  row_range?: number[] | null;
}

export interface CitationSource {
  kind: string;
  accession: string;
  file_name: string;
  sha256: string | null;
  source_url: string | null;
}

export interface CitationRetrieval {
  retrieved_at: string | null;
  http_status: number | null;
  download_status: string | null;
  bytes: number | null;
  expected_bytes: number | null;
  checksum_expected: string | null;
  checksum_actual: string | null;
  checksum_match: boolean | null;
}

export interface CitationVerification {
  status: string;
  checks: string[];
}

export interface CitationAvailability {
  status: string;
  downloadable: boolean;
  reason: string | null;
}

export interface RowVerification {
  row_verified: boolean;
  row_tables: string[];
  warnings: string[];
}

export type CitationProvenance = SourceReference | ProvenanceRecord;

export interface Citation {
  citation_id: string;
  kind: CitationKind | string;
  accession: string;
  dataset_ids: string[];
  file: CitationFileInfo;
  locator: CitationLocator;
  source: CitationSource;
  retrieval: CitationRetrieval;
  verification: CitationVerification;
  availability: CitationAvailability;
  provenance: CitationProvenance[];
  row_verification?: RowVerification | null;
}

export interface DatasetFileDownload {
  status: string;
  http_status: number | null;
  bytes: number | null;
  retrieved_at: string | null;
  sha256: string | null;
  checksum_match: boolean | null;
}

export interface DatasetFile {
  file_id: string;
  citation_id: string;
  file_name: string;
  accession: string;
  dataset_ids: string[];
  kind: string;
  priority: string | null;
  purpose: string | null;
  source_url: string | null;
  availability: string;
  downloadable: boolean;
  availability_reason: string | null;
  download: DatasetFileDownload;
  verification: CitationVerification;
  provenance: SourceReference[];
}

export interface DatasetFilesSummary {
  curated_files: number;
  available_files: number;
  unavailable_files: number;
  downloadable_files: number;
  known_unavailable_files: number;
  experimental_tables: number;
}

export interface DatasetFilesInventory {
  public_inventory_file_count: number;
  curated_file_count: number;
  not_selected_file_count: number;
  public_experimental_table_count: number;
  archive_status: string;
  note: string;
}

export interface DatasetFilesResponse {
  dataset_id: string;
  accession: string;
  display_name: string;
  files: DatasetFile[];
  summary: DatasetFilesSummary;
  inventory: DatasetFilesInventory;
  page: PageMeta;
}

export interface FieldAlternative {
  canonical_field: string;
  unit: string;
  description: string;
  evidence: SourceReference;
}

export interface CanonicalPresence {
  measurement_id: string;
  checked: boolean;
  status: string;
  reason: string | null;
  table: string | null;
  field: string | null;
  accession: string | null;
  total_rows: number | null;
  non_null_count: number | null;
  alternatives: FieldAlternative[];
}

export interface FieldCalibration {
  status: string;
  note: string | null;
}

export interface FieldMissingness {
  availability: string;
  restrictions: string[];
  canonical_presence: CanonicalPresence;
  policy: string;
}

export interface FieldComparabilityRule {
  rule_id: string;
  status: ComparisonStatus;
  scientific_justification: string;
}

export interface FieldComparability {
  status: ComparisonStatus;
  compatible_datasets: string[];
  incompatible_datasets: string[];
  rules: FieldComparabilityRule[];
}

export interface SourceColumnMapping {
  raw_column: string;
  source_file: string;
  applies_to: string;
}

export interface DatasetField {
  field_id: string;
  measurement_id: string;
  dataset_id: string;
  accession: string;
  canonical_name: string;
  parameter: string;
  description: string;
  physical_quantity: string;
  unit: string;
  unit_status: UnitStatus;
  value_kind: ValueKind;
  measurement_method: string;
  calibration: FieldCalibration;
  missingness: FieldMissingness;
  integrity: CanonicalPresence;
  alternatives: FieldAlternative[];
  flags: string[];
  comparability: FieldComparability;
  source_columns: SourceColumnMapping[];
  source_references: SourceReference[];
  serving_state: ServingState;
  use_states: UseStates;
}

export interface DatasetFieldsSummary {
  field_count: number;
  with_verified_source_column: number;
  with_canonical_values: number;
  without_canonical_values: number;
  presence_not_checked: number;
  value_kinds: Partial<Record<ValueKind, number>>;
  comparison_statuses: Partial<Record<ComparisonStatus, number>>;
}

export interface DatasetFieldsResponse {
  dataset_id: string;
  accession: string;
  display_name: string;
  fields: DatasetField[];
  summary: DatasetFieldsSummary;
  page: PageMeta;
}

export interface Limitation {
  limitation_id: string;
  scope: string;
  scope_id: string;
  dataset_id: string;
  accession: string;
  category: string;
  severity: "error" | "warning" | "info" | string;
  code: string;
  explanation: string;
  affected_operations: string[];
  evidence: SourceReference[];
  resolution_status: string;
  resolution_note: string;
}

export interface DatasetLimitationsSummary {
  total: number;
  by_scope: Record<string, number>;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
}

export interface DatasetLimitationsResponse {
  dataset_id: string;
  accession: string;
  display_name: string;
  limitations: Limitation[];
  summary: DatasetLimitationsSummary;
  page: PageMeta;
}

export interface PublicationRelatedInvestigation {
  accession: string;
  title: string;
  doi: string | null;
  acronym: string;
}

export interface PublicationVerification {
  status: string;
  source: string;
  snapshot_date: string;
  verified_fields: string[];
  unavailable_fields: string[];
  conflicts: {
    title_variants: string[];
    authors_raw_variants: string[];
  };
}

export interface Publication {
  publication_id: string;
  title: string;
  title_variants: string[];
  authors: string[];
  authors_raw: string;
  authors_raw_variants: string[];
  author_parse: string;
  doi: string | null;
  doi_url: string | null;
  year: number | null;
  venue: string | null;
  status: string;
  related_investigations: PublicationRelatedInvestigation[];
  source_references: SourceReference[];
  verification: PublicationVerification;
  field_status: Record<string, string>;
}

export interface PublicationsSummary {
  publication_count: number;
  with_doi: number;
  without_doi: number;
  year_available: boolean;
  venue_available: boolean;
  note: string;
}

export interface PublicationsResponse {
  publications: Publication[];
  page: PageMeta;
  summary: PublicationsSummary;
}

export interface FacetValue {
  value: string;
  count: number;
  by_accession: Record<string, number>;
}

export interface FacetHistogramBin {
  min: number;
  max: number;
  count: number;
}

export interface FacetNumericGroup {
  accession: string;
  field: string;
  unit: string;
  count: number;
  missing_count: number;
  min: number | null;
  max: number | null;
  histogram: FacetHistogramBin[];
}

export interface FacetNumeric {
  by_accession: FacetNumericGroup[];
  note: string;
}

export interface FacetOxygen extends FacetNumeric {
  field: string;
  unit: string;
}

export interface GasFlameFacetAccession {
  accession: string;
  total_rows: number;
  included_rows: number;
  excluded_qualified_rows: number;
}

export interface GasFlameFacets {
  accessions: GasFlameFacetAccession[];
  flame_type: FacetValue[];
  fuel: FacetValue[];
  hot_ignition: FacetValue[];
  extinction_mode: FacetValue[];
  tfp: FacetValue[];
  pressure: FacetNumeric;
  oxygen: FacetOxygen;
  oxygen_initial: FacetNumeric;
  include_qualified: boolean;
  excluded_qualified_rows: number;
  notes: string[];
}

export type IntegrityCheck = CanonicalPresence;

export interface ComparisonIntegrity {
  status: string;
  checks: IntegrityCheck[];
  failures: IntegrityCheck[];
  not_checked: IntegrityCheck[];
  messages: string[];
}

export interface PairedAlignment {
  method_id: string | null;
  verified: boolean;
  keys: string[];
  value_fields: Record<string, string | null>;
  unit_policy: string | null;
}

export interface PairedCondition {
  key: string;
  satisfied: boolean | null;
}

export interface PairedValuesReason {
  code: string;
  message: string;
  rule_id?: string | null;
  decision_status?: ComparisonStatus;
  missing_conditions?: string[];
  required_alignment?: {
    keys: string[];
    note: string;
  };
}

/**
 * The backend withholds observations until a reviewed alignment executor is
 * registered. The optional nested shape keeps the frontend tolerant of an
 * executor that returns either flat or per-side values, but the chart guard
 * accepts only numeric pairs.
 */
export interface PairedObservation {
  pair_id: string;
  keys?: Record<string, string | number | null>;
  left_value?: number;
  right_value?: number;
  left_unit?: string;
  right_unit?: string;
  left?: {
    value?: number;
    unit?: string;
    source_row?: number | null;
    citation_id?: string | null;
  };
  right?: {
    value?: number;
    unit?: string;
    source_row?: number | null;
    citation_id?: string | null;
  };
}

export interface PairedSeriesPoint {
  x: number;
  y: number;
  pair_id?: string;
}

export interface PairedSeries {
  series_id: string;
  label: string;
  x_unit: string;
  y_unit: string;
  points: PairedSeriesPoint[];
}

export interface PairedValues {
  available: boolean;
  status: string;
  alignment: PairedAlignment;
  conditions: {
    supplied: Record<string, boolean | null>;
    required: PairedCondition[];
  };
  observations: PairedObservation[];
  series: PairedSeries[];
  exclusions: Array<Record<string, unknown>>;
  dataset_version: string;
  provenance: SourceReference[];
  reason: PairedValuesReason | null;
}

/* ------------------------------------------------------------------ */
/* Phase 5: grounded assistant                                         */
/* ------------------------------------------------------------------ */

export type AssistantEvidenceStatus =
  | "fully_supported"
  | "partially_supported"
  | "insufficient_evidence"
  | "unavailable_data"
  | "conflicting_evidence";

export type AssistantAnswerType =
  | "factual"
  | "numerical"
  | "exploratory"
  | "comparison"
  | "methodology"
  | "clarification_required";

export type AssistantConfidence = "high" | "moderate" | "low";

export type AssistantValueKind =
  | "measured"
  | "computed"
  | "derived"
  | "categorical"
  | "raw"
  | "not_applicable";

export type AssistantClaimType =
  | "numerical"
  | "factual"
  | "comparison"
  | "limitation"
  | "provenance";

export type AssistantToolStatus = "ok" | "empty" | "rejected" | "failed";

export type AssistantSeverity = "error" | "warning" | "info";

export type AssistantEvidenceSourceType =
  | "document"
  | "dataset_card"
  | "investigation"
  | "publication"
  | "citation"
  | "tool_result";

export type AssistantMode = "deterministic" | "provider" | "fallback";

export interface AssistantQueryParams {
  question: string;
  conversation_id?: string | null;
  accession?: string | null;
  dataset_id?: string | null;
  include_retrieval?: boolean;
  max_tool_calls?: number;
}

export interface AssistantCitationReference {
  citation_id: string;
  citation_type: "file" | "row";
  accession: string;
  dataset_ids: string[];
  file_name: string;
  sheet: string | null;
  row: number | null;
  source_url: string | null;
  sha256: string | null;
  verification_status: string;
  availability: string;
  downloadable: boolean;
  resolved: boolean;
}

export interface AssistantToolCall {
  call_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  status: AssistantToolStatus;
  duration_ms: number;
  result_summary: string | null;
  result_hash: string | null;
  error: string | null;
}

export interface AssistantSupportingData {
  data_id: string;
  tool_call_id: string;
  label: string;
  value_kind: AssistantValueKind;
  unit: string | null;
  dataset_id: string | null;
  accession: string | null;
  summary: string;
  values: Record<string, unknown>;
  citation_ids: string[];
}

export interface AssistantClaim {
  claim_id: string;
  text: string;
  claim_type: AssistantClaimType;
  value: number | string | null;
  unit: string | null;
  value_kind: AssistantValueKind | null;
  dataset_id: string | null;
  accession: string | null;
  tool_call_id: string | null;
  citation_ids: string[];
  supported: boolean;
  validation_notes: string[];
}

export interface AssistantLimitation {
  code: string;
  message: string;
  scope: string | null;
  severity: AssistantSeverity;
  citation_ids: string[];
}

export interface AssistantValidationCheck {
  name: string;
  passed: boolean;
  detail: string | null;
}

export interface AssistantValidationReport {
  passed: boolean;
  citation_validation_passed: boolean;
  claim_validation_passed: boolean;
  checks: AssistantValidationCheck[];
  errors: string[];
  warnings: string[];
}

export interface AssistantEvidenceItem {
  evidence_id: string;
  source_type: AssistantEvidenceSourceType;
  title: string;
  snippet: string;
  document_id: string | null;
  source_reference: string | null;
  accession: string | null;
  dataset_id: string | null;
  citation_id: string | null;
  section: string | null;
  content_hash: string | null;
  index_version: string | null;
  trusted_as_instruction: false;
}

export interface AssistantClarification {
  question: string;
  options: string[];
  missing: string[];
}

export interface AssistantAnswer {
  contract_version: string;
  request_id: string;
  conversation_id: string | null;
  answer: string;
  evidence_status: AssistantEvidenceStatus;
  answer_type: AssistantAnswerType;
  citations: AssistantCitationReference[];
  supporting_data: AssistantSupportingData[];
  claims: AssistantClaim[];
  limitations: AssistantLimitation[];
  tools_used: AssistantToolCall[];
  evidence: AssistantEvidenceItem[];
  confidence: AssistantConfidence;
  confidence_basis: string;
  dataset_version: string | null;
  provider: string;
  fallback_mode: boolean;
  fallback_reason: string | null;
  clarification: AssistantClarification | null;
  validation: AssistantValidationReport;
  generated_at: string;
}

export interface AssistantStatus {
  enabled: boolean;
  mode: AssistantMode;
  provider: string;
  model: string | null;
  retrieval_enabled: boolean;
  index_version: string | null;
  contract_version: string;
  fallback_mode: boolean;
  fallback_reason: string | null;
  tools_available: string[];
  notes: string[];
}

export interface AssistantSuggestion {
  question_id: string;
  category: string;
  question: string;
  answer_type_hint: AssistantAnswerType;
}

export interface AssistantSuggestionsResponse {
  suggestions: AssistantSuggestion[];
  count: number;
}

export interface AssistantToolDescription {
  name: string;
  description: string;
  category: string;
  arguments_schema: Record<string, unknown>;
}

export interface AssistantToolsResponse {
  tools: AssistantToolDescription[];
  count: number;
}
