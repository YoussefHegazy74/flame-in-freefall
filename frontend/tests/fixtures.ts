import type {
  ComparisonDecision,
  ComparisonMeasurement,
  DatasetQuality,
  Envelope,
  GasFlameRow,
  Quality,
  SeriesChannel,
  UseStates,
} from "@/lib/api/types";

export const useStates: UseStates = {
  exploration: "available_with_warnings",
  quantitative_comparison: "restricted",
  time_series: "blocked",
  provenance: "available",
};

export const responseQuality: Quality = {
  status: "partial",
  flags: ["use_available_with_warnings", "uncalibrated_channels"],
  warnings: ["Some channels are uncalibrated and remain labeled raw."],
};

export function envelope<T>(
  data: T,
  overrides: Partial<Envelope<T>> = {},
): Envelope<T> {
  return {
    data,
    meta: {
      request_id: "req_test",
      registry_snapshot: "2026-11-08",
      dataset_version: "dataset-version-test",
      registry_version: "1.0.0",
      generated_at: "2026-11-09T00:00:00Z",
      page: { limit: 25, offset: 0, total: 1, has_more: false },
      ...overrides.meta,
    },
    provenance: [],
    quality: responseQuality,
    ...overrides,
  };
}

export function datasetQuality(
  overrides: Partial<DatasetQuality> = {},
): DatasetQuality {
  return {
    dataset_id: "psi-10-gas-flame",
    accession: "PSI-10",
    display_name: "PSI-10 gas-flame tests",
    quality_status: "partial",
    base_state: "available_with_warnings",
    use_states: useStates,
    report_summary: {
      tables: 12,
      total_rows: 1200,
      point_rows: 1100,
      issues: 4,
      errors: 0,
      warnings: 4,
    },
    issues: [
      {
        severity: "warning",
        code: "unit_ambiguity",
        message: "PSI-69 burning rate is preserved as labeled.",
        details: { column: "burning_rate_mm_as_labeled", count: 258 },
      },
    ],
    ...overrides,
  };
}

export function comparisonMeasurement(
  overrides: Partial<ComparisonMeasurement> = {},
): ComparisonMeasurement {
  return {
    measurement_id: "psi-10-gas-flame.oxygen_mole_fraction",
    dataset_id: "psi-10-gas-flame",
    accession: "PSI-10",
    experiment_family: "gas_flame",
    parameter: "oxygen_mole_fraction",
    canonical_field: "oxygen_mole_fraction",
    canonical_channel: null,
    physical_quantity: "oxygen_mole_fraction",
    unit: "mole fraction",
    unit_status: "stated",
    value_kind: "measured",
    calibration_status: "not_applicable",
    availability: "available",
    comparison_status: "conditionally_comparable",
    quality_restrictions: ["ramped_condition_rows"],
    ...overrides,
  };
}

export function comparisonDecision(
  overrides: Partial<ComparisonDecision> = {},
): ComparisonDecision {
  return {
    left: comparisonMeasurement(),
    right: comparisonMeasurement({
      measurement_id: "psi-159-gas-flame.oxygen_mole_fraction",
      dataset_id: "psi-159-gas-flame",
      accession: "PSI-159",
    }),
    status: "conditionally_comparable",
    rule_id: "gas-flame-oxygen",
    reasons: [
      {
        code: "conditions_unverified",
        message: "Required comparison conditions are not yet verified.",
      },
    ],
    required_conditions: [
      {
        key: "same_oxygen_basis",
        description: "Both values are oxygen mole fraction, not percent or partial pressure.",
        satisfied: false,
      },
      {
        key: "flame_configuration_documented",
        description: "Normal or inverse configuration is known for both rows.",
        satisfied: false,
      },
    ],
    warnings: ["Ramped rows remain flagged."],
    scientific_justification:
      "Both datasets report oxygen mole fraction, but the comparison requires verified conditions.",
    source_references: [
      { kind: "document", path: "DATA_DICTIONARY.md", section: "4.1" },
    ],
    registry_version: "1.0.0",
    dataset_version: "dataset-version-test",
    ...overrides,
  };
}

export function gasFlameRow(overrides: Partial<GasFlameRow> = {}): GasFlameRow {
  return {
    observation_id: "obs-1",
    accession: "PSI-10",
    table_id: "gas_flame_test",
    source_file: "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
    source_sheet: null,
    source_row: 2,
    source_sha256: "abc123",
    retrieved_at: "2026-11-08T22:14:52Z",
    source_url: "https://psi.nasa.gov/example",
    parser_version: "1.0.0",
    quality_flags: [],
    flame_type: "Normal",
    day: "1",
    fuel: "C2H4",
    test_code: "T-01",
    fuel_mole_fraction: 0.2,
    fuel_mass_flow_mg_s: 1.2,
    diluent_mass_flow_mg_s: null,
    total_mass_flow_mg_s: 2.4,
    oxygen_mole_fraction: 0.21,
    oxygen_mole_fraction_initial: 0.21,
    oxygen_mole_fraction_final: 0.2,
    oxygen_mole_fraction_before: null,
    oxygen_mole_fraction_after: null,
    pressure_initial_atm: 1,
    pressure_final_atm: 0.9,
    pressure_mean_atm: 0.95,
    pressure_approx_bar: null,
    oxidizer_mass_flow_mg_s: null,
    fuel_mole_fraction_initial: null,
    fuel_mole_fraction_final: null,
    fuel_mole_fraction_before: null,
    fuel_mole_fraction_after: null,
    fuel_burn_rate_mg_s: null,
    stoich_mixture_fraction: 0.1,
    adiabatic_flame_temp_k: 2200,
    cool_flame_flag: null,
    tfp_flag: null,
    hot_ignition: "Yes",
    burn_time_s: 3.2,
    extinction_mode: "SE",
    peak_burner_temp_c: 900,
    peak_burner_temp_k: 1173,
    color: null,
    comments: null,
    computed_fields: ["adiabatic_flame_temp_k", "stoich_mixture_fraction"],
    ...overrides,
  };
}

export function seriesChannel(
  overrides: Partial<SeriesChannel> = {},
): SeriesChannel {
  return {
    channel_name_raw: "PCM_AIR_TEMP",
    channel_name_canonical: "pcm_air_temp_c",
    unit: "degC",
    quality_flags: ["ok"],
    point_count: 10,
    ...overrides,
  };
}
