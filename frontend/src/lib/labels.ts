export const FIELD_LABELS: Record<string, string> = {
  accession: "Investigation",
  flame_type: "Flame configuration",
  fuel: "Fuel",
  test_code: "Test code",
  day: "Test day",
  fuel_mole_fraction: "Fuel mole fraction",
  fuel_mass_flow_mg_s: "Fuel mass flow (mg/s)",
  diluent_mass_flow_mg_s: "Diluent mass flow (mg/s)",
  total_mass_flow_mg_s: "Total mass flow (mg/s)",
  oxygen_mole_fraction: "Oxygen mole fraction",
  oxygen_mole_fraction_initial: "Initial oxygen mole fraction",
  oxygen_mole_fraction_final: "Final oxygen mole fraction",
  oxygen_mole_fraction_before: "Oxygen mole fraction before",
  oxygen_mole_fraction_after: "Oxygen mole fraction after",
  pressure_initial_atm: "Initial pressure (atm)",
  pressure_final_atm: "Final pressure (atm)",
  pressure_mean_atm: "Mean pressure (atm)",
  pressure_approx_bar: "Pressure, as labeled (bar)",
  oxidizer_mass_flow_mg_s: "Oxidizer mass flow (mg/s)",
  fuel_mole_fraction_initial: "Initial fuel mole fraction",
  fuel_mole_fraction_final: "Final fuel mole fraction",
  fuel_mole_fraction_before: "Fuel mole fraction before",
  fuel_mole_fraction_after: "Fuel mole fraction after",
  fuel_burn_rate_mg_s: "Fuel burn rate (mg/s)",
  stoich_mixture_fraction: "Stoichiometric mixture fraction (Zst)",
  adiabatic_flame_temp_k: "Adiabatic flame temperature (K)",
  cool_flame_flag: "Cool-flame flag",
  tfp_flag: "TFP flag (unexpanded)",
  hot_ignition: "Hot ignition",
  burn_time_s: "Burn time (s)",
  extinction_mode: "Extinction mode",
  peak_burner_temp_c: "Peak burner temperature (°C)",
  peak_burner_temp_k: "Peak burner temperature (K)",
  color: "Color",
  comments: "Comments",
  material: "Material (free text)",
  initial_o2_pct: "Initial O₂, as labeled (%)",
  final_o2_pct: "Final O₂, as labeled (%)",
  o2_pct: "O₂, as labeled (% header; ambiguous)",
  initial_co2_pct: "Initial CO₂, as labeled (%)",
  final_co2_pct: "Final CO₂, as labeled (%)",
  initial_co_ppm: "Initial CO, as labeled (ppm)",
  final_co_ppm: "Final CO, as labeled (ppm)",
  pressure_atm: "Pressure (atm)",
  co2_mm_hg: "CO₂ (mmHg)",
  flow_restrictor: "Flow restrictor",
  fan_display: "Fan setting (as displayed)",
  air_display: "Air setting (as displayed)",
  radiometer_gain: "Radiometer gain (as displayed)",
  total_frames: "Total frames (as displayed)",
  observations: "Observations (free text)",
  flex_test_number: "FLEX test number",
  test_date: "Test date",
  flex_identifier: "FLEX identifier",
  test_gmt: "Test GMT",
  ambient_pressure_mm_hg: "Ambient pressure (mmHg)",
  o2_initial_mole_fraction: "Initial oxygen mole fraction",
  n2_initial_mole_fraction: "Initial nitrogen mole fraction",
  co_initial_mole_fraction: "Initial CO mole fraction",
  he_initial_mole_fraction: "Initial helium mole fraction",
  droplet_initial_diameter_mm: "Initial droplet diameter (mm)",
  visible_flame_extinction_diameter_mm: "Visible flame extinction diameter (mm)",
  burning_rate_mm_as_labeled: "Burning rate, as labeled (mm)",
  test_end: "Test end",
  as_run_test_no: "As-run test number",
  test_no: "Test number",
  sample_no: "Sample number",
  gmt_day: "GMT day",
  record_type: "Record type",
};

export function fieldLabel(field: string): string {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field];
  return field
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export const FAMILY_LABELS: Record<string, string> = {
  gas_flame: "Gas flame",
  material: "Material",
  droplet: "Droplet",
  telemetry: "Telemetry",
  smoke: "Smoke / aerosol",
  smoke_log: "Smoke event log",
  metadata: "Metadata only",
};

export function familyLabel(family: string | null | undefined): string {
  if (!family) return "Unknown family";
  return FAMILY_LABELS[family] ?? family.replace(/_/g, " ");
}

export const ROLE_LABELS: Record<string, string> = {
  primary: "Primary evidence",
  supporting: "Supporting",
  context: "Context",
  future: "Future scope",
};

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "Unclassified";
  return ROLE_LABELS[role] ?? role;
}

export const USE_LABELS: Record<string, string> = {
  exploration: "Exploration",
  quantitative_comparison: "Quantitative comparison",
  time_series: "Time series",
  provenance: "Provenance",
};

export function labelForUse(use: string): string {
  return USE_LABELS[use] ?? use.replace(/_/g, " ");
}

export const STATE_LABELS: Record<string, string> = {
  available: "Available",
  available_with_warnings: "Available with warnings",
  restricted: "Restricted",
  blocked: "Blocked",
  metadata_only: "Metadata only",
};

export const COMPARISON_LABELS: Record<string, string> = {
  comparable: "Comparable",
  conditionally_comparable: "Conditionally comparable",
  not_comparable: "Not comparable",
  blocked: "Blocked",
  insufficient_metadata: "Insufficient metadata",
};

export const QUALITY_LABELS: Record<string, string> = {
  verified: "Verified",
  partial: "Partial",
  blocked: "Blocked",
  experimental_table_only: "Experimental table only",
  not_available: "Not available",
};

export const VALUE_KIND_LABELS: Record<string, string> = {
  measured: "Measured",
  computed: "Computed",
  raw: "Raw signal",
  categorical: "Categorical",
  derived: "Derived",
  not_applicable: "Not applicable",
};

export function valueKindLabel(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return VALUE_KIND_LABELS[value] ?? value;
}
