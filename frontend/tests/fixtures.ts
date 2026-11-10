import type {
  Citation,
  ComparisonDecision,
  ComparisonIntegrity,
  ComparisonMeasurement,
  DatasetField,
  DatasetFile,
  DatasetQuality,
  Envelope,
  GasFlameRow,
  Limitation,
  PairedValues,
  Publication,
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

export function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    citation_id: "cit_f_test",
    kind: "file",
    accession: "PSI-10",
    dataset_ids: ["psi-10-gas-flame"],
    file: {
      name: "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
      kind: "experimental_table",
      manifest_dataset: "gas_flame_test",
      priority: "primary",
      purpose: "Public experimental summary table.",
      in_added: true,
    },
    locator: { type: "file", sheet: null, row: null },
    source: {
      kind: "nasa_psi_file",
      accession: "PSI-10",
      file_name: "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
      sha256: "abc123",
      source_url: "https://psi.nasa.gov/example",
    },
    retrieval: {
      retrieved_at: "2026-11-08T22:14:49Z",
      http_status: 200,
      download_status: "downloaded",
      bytes: 1024,
      expected_bytes: 1024,
      checksum_expected: "abc123",
      checksum_actual: "abc123",
      checksum_match: true,
    },
    verification: { status: "verified", checks: ["sha256_match"] },
    availability: { status: "available", downloadable: true, reason: null },
    provenance: [],
    ...overrides,
  };
}

export function datasetFile(overrides: Partial<DatasetFile> = {}): DatasetFile {
  return {
    file_id: "cit_f_test",
    citation_id: "cit_f_test",
    file_name: "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
    accession: "PSI-10",
    dataset_ids: ["psi-10-gas-flame"],
    kind: "experimental_table",
    priority: "primary",
    purpose: "Public experimental summary table.",
    source_url: "https://psi.nasa.gov/example",
    availability: "available",
    downloadable: true,
    availability_reason: null,
    download: {
      status: "downloaded",
      http_status: 200,
      bytes: 1024,
      retrieved_at: "2026-11-08T22:14:49Z",
      sha256: "abc123",
      checksum_match: true,
    },
    verification: { status: "verified", checks: ["sha256_match"] },
    provenance: [],
    ...overrides,
  };
}

export function datasetField(overrides: Partial<DatasetField> = {}): DatasetField {
  return {
    field_id: "psi-10-gas-flame.oxygen_mole_fraction",
    measurement_id: "psi-10-gas-flame.oxygen_mole_fraction",
    dataset_id: "psi-10-gas-flame",
    accession: "PSI-10",
    canonical_name: "oxygen_mole_fraction",
    parameter: "oxygen_mole_fraction",
    description: "Oxygen mole fraction reported by the source.",
    physical_quantity: "oxygen_mole_fraction",
    unit: "mole fraction",
    unit_status: "stated",
    value_kind: "measured",
    measurement_method: "Source-reported field.",
    calibration: { status: "not_applicable", note: null },
    missingness: {
      availability: "available",
      restrictions: ["ramped_condition_rows"],
      canonical_presence: {
        measurement_id: "psi-10-gas-flame.oxygen_mole_fraction",
        checked: true,
        status: "available",
        reason: null,
        table: "gas_flame_test",
        field: "oxygen_mole_fraction",
        accession: "PSI-10",
        total_rows: 327,
        non_null_count: 327,
        alternatives: [],
      },
      policy: "Missing values remain null and are never zero-filled.",
    },
    integrity: {
      measurement_id: "psi-10-gas-flame.oxygen_mole_fraction",
      checked: true,
      status: "available",
      reason: null,
      table: "gas_flame_test",
      field: "oxygen_mole_fraction",
      accession: "PSI-10",
      total_rows: 327,
      non_null_count: 327,
      alternatives: [],
    },
    alternatives: [],
    flags: ["ramped_condition_rows"],
    comparability: {
      status: "conditionally_comparable",
      compatible_datasets: ["psi-159-gas-flame"],
      incompatible_datasets: [],
      rules: [
        {
          rule_id: "gas-flame-oxygen",
          status: "conditionally_comparable",
          scientific_justification: "Both datasets report oxygen mole fraction.",
        },
      ],
    },
    source_columns: [
      {
        raw_column: "X_O2",
        source_file: "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        applies_to: "normal flame table",
      },
    ],
    source_references: [],
    serving_state: "available_with_warnings",
    use_states: useStates,
    ...overrides,
  };
}

export function limitation(overrides: Partial<Limitation> = {}): Limitation {
  return {
    limitation_id: "lim_d_test",
    scope: "dataset",
    scope_id: "psi-10-gas-flame",
    dataset_id: "psi-10-gas-flame",
    accession: "PSI-10",
    category: "value_kind",
    severity: "warning",
    code: "computed_tad_zst",
    explanation: "Tad and Zst are computed by the source, not measured.",
    affected_operations: ["quantitative_comparison"],
    evidence: [{ kind: "document", path: "DATA_DICTIONARY.md" }],
    resolution_status: "open",
    resolution_note: "Preserved and labeled; not resolved by the platform.",
    ...overrides,
  };
}

export function publication(overrides: Partial<Publication> = {}): Publication {
  return {
    publication_id: "pub_test",
    title: "A Mechanistic Study of Soret Diffusion",
    title_variants: [],
    authors: ["Yang Fan", "Law C.K."],
    authors_raw: "Yang Fan, Law C.K.",
    authors_raw_variants: [],
    author_parse: "source_comma_or_and_delimited",
    doi: "10.2514/6.2009-988",
    doi_url: "https://doi.org/10.2514/6.2009-988",
    year: null,
    venue: null,
    status: "published",
    related_investigations: [
      {
        accession: "PSI-23",
        title: "ACME s-Flame",
        doi: "10.60555/k57n-p030",
        acronym: "ACME s-Flame",
      },
    ],
    source_references: [
      {
        kind: "psi_investigation_registry",
        path: "data/registry/psi_combustion_investigations.json",
        accession: "PSI-23",
        field: "publications",
      },
    ],
    verification: {
      status: "registry_verified",
      source: "data/registry/psi_combustion_investigations.json",
      snapshot_date: "2026-11-08",
      verified_fields: ["title", "authors", "doi", "status"],
      unavailable_fields: ["year", "venue"],
      conflicts: { title_variants: [], authors_raw_variants: [] },
    },
    field_status: {
      title: "source_provided",
      authors: "source_provided",
      doi: "source_provided",
      year: "not_available_in_registry",
      venue: "not_available_in_registry",
      status: "source_provided",
    },
    ...overrides,
  };
}

export function comparisonIntegrity(
  overrides: Partial<ComparisonIntegrity> = {},
): ComparisonIntegrity {
  const check = datasetField().integrity;
  return {
    status: "verified",
    checks: [check],
    failures: [],
    not_checked: [],
    messages: [],
    ...overrides,
  };
}

export function pairedValues(overrides: Partial<PairedValues> = {}): PairedValues {
  return {
    available: false,
    status: "not_available",
    alignment: {
      method_id: null,
      verified: false,
      keys: [],
      value_fields: {},
      unit_policy: null,
    },
    conditions: {
      supplied: {},
      required: [
        { key: "same_oxygen_basis", satisfied: false },
      ],
    },
    observations: [],
    series: [],
    exclusions: [],
    dataset_version: "dataset-version-test",
    provenance: [],
    reason: {
      code: "no_verified_alignment",
      message: "No verified record-level alignment method is registered.",
      rule_id: "gas-flame-oxygen",
      required_alignment: {
        keys: ["test_code", "source_row"],
        note: "A reviewed alignment method must be committed before values can be paired.",
      },
    },
    ...overrides,
  };
}
