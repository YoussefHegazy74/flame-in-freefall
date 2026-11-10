import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  citation,
  datasetField,
  datasetFile,
  envelope,
  limitation,
  pairedValues,
  publication,
} from "../fixtures";

vi.mock("next/link", async () => {
  const React = await import("react");
  return {
    default: ({
      href,
      children,
      ...props
    }: {
      href: string | { pathname?: string };
      children: React.ReactNode;
    }) =>
      React.createElement(
        "a",
        { href: typeof href === "string" ? href : href.pathname ?? "#", ...props },
        children,
      ),
  };
});

const hooks = vi.hoisted(() => ({
  useCitation: vi.fn(),
  useDatasetFiles: vi.fn(),
  useDatasetFields: vi.fn(),
  useDatasetLimitations: vi.fn(),
  usePublications: vi.fn(),
}));

vi.mock("@/lib/api/hooks", () => ({
  useCitation: hooks.useCitation,
  useDatasetFiles: hooks.useDatasetFiles,
  useDatasetFields: hooks.useDatasetFields,
  useDatasetLimitations: hooks.useDatasetLimitations,
  usePublications: hooks.usePublications,
}));

import { CitationDrawer } from "@/components/scientific/citation-drawer";
import { DatasetFilesPanel } from "@/components/scientific/dataset-files-panel";
import { DatasetFieldsPanel } from "@/components/scientific/dataset-fields-panel";
import { DatasetLimitationsPanel } from "@/components/scientific/dataset-limitations-panel";
import {
  DatasetPublicationsPanel,
  PublicationCard,
} from "@/components/scientific/publications-panel";
import {
  ComparisonIntegrityPanel,
  PairedValuesPanel,
  isChartReady,
} from "@/components/scientific/paired-values-panel";

function query<T>(data: T) {
  return {
    data,
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  };
}

const filesResponse = {
  dataset_id: "psi-98-metadata",
  accession: "PSI-98",
  display_name: "PSI-98 SAFFIRE-I metadata",
  files: [
    datasetFile(),
    datasetFile({
      file_id: "cit_f_unavailable",
      citation_id: "cit_f_unavailable",
      file_name: "PSI-98_Raw Data_Saffire-I Telemetry Data.xlsx",
      kind: "archive",
      availability: "unavailable",
      downloadable: false,
      availability_reason: "The NASA PSI source returned HTTP 404; the file is known unavailable.",
      source_url: null,
      download: {
        status: "known_unavailable",
        http_status: 404,
        bytes: null,
        retrieved_at: null,
        sha256: null,
        checksum_match: null,
      },
      verification: { status: "unavailable", checks: ["http_404"] },
    }),
  ],
  summary: {
    curated_files: 3,
    available_files: 1,
    unavailable_files: 2,
    downloadable_files: 1,
    known_unavailable_files: 2,
    experimental_tables: 1,
  },
  inventory: {
    public_inventory_file_count: 74,
    curated_file_count: 3,
    not_selected_file_count: 71,
    public_experimental_table_count: 1,
    archive_status: "partial",
    note: "Only curated files are listed.",
  },
  page: { limit: 200, offset: 0, total: 2, has_more: false },
};

const fieldsResponse = {
  dataset_id: "psi-10-gas-flame",
  accession: "PSI-10",
  display_name: "PSI-10 gas-flame tests",
  fields: [
    datasetField(),
    datasetField({
      field_id: "psi-10-gas-flame.pressure_approx_bar",
      measurement_id: "psi-10-gas-flame.pressure_approx_bar",
      canonical_name: "pressure_approx_bar",
      parameter: "pressure_approx_bar",
      physical_quantity: "pressure",
      unit: "bar",
      integrity: {
        ...datasetField().integrity,
        measurement_id: "psi-10-gas-flame.pressure_approx_bar",
        status: "missing",
        non_null_count: 0,
        total_rows: 327,
        alternatives: [
          {
            canonical_field: "pressure_initial_atm",
            unit: "atm",
            description: "Initial chamber pressure reported for the test.",
            evidence: { kind: "document", path: "DATA_DICTIONARY.md" },
          },
        ],
      },
      alternatives: [
        {
          canonical_field: "pressure_initial_atm",
          unit: "atm",
          description: "Initial chamber pressure reported for the test.",
          evidence: { kind: "document", path: "DATA_DICTIONARY.md" },
        },
      ],
    }),
  ],
  summary: {
    field_count: 2,
    with_verified_source_column: 1,
    with_canonical_values: 1,
    without_canonical_values: 1,
    presence_not_checked: 0,
    value_kinds: { measured: 2 },
    comparison_statuses: { conditionally_comparable: 2 },
  },
  page: { limit: 200, offset: 0, total: 2, has_more: false },
};

const limitationsResponse = {
  dataset_id: "psi-10-gas-flame",
  accession: "PSI-10",
  display_name: "PSI-10 gas-flame tests",
  limitations: [
    limitation(),
    limitation({
      limitation_id: "lim_m_test",
      scope: "measurement",
      scope_id: "psi-10-gas-flame.pressure_approx_bar",
      category: "measurement_integrity",
      severity: "error",
      code: "no_canonical_values",
      explanation: "The registry marks this field available, but canonical data contains no values.",
      affected_operations: ["quantitative_comparison"],
    }),
  ],
  summary: {
    total: 2,
    by_scope: { dataset: 1, measurement: 1 },
    by_severity: { warning: 1, error: 1 },
    by_status: { open: 2 },
  },
  page: { limit: 200, offset: 0, total: 2, has_more: false },
};

const publicationsResponse = {
  publications: [publication()],
  page: { limit: 6, offset: 0, total: 1, has_more: false },
  summary: {
    publication_count: 1,
    with_doi: 1,
    without_doi: 0,
    year_available: false,
    venue_available: false,
    note: "Year and venue are unavailable in the registry.",
  },
};

beforeEach(() => {
  hooks.useCitation.mockReset();
  hooks.useDatasetFiles.mockReset();
  hooks.useDatasetFields.mockReset();
  hooks.useDatasetLimitations.mockReset();
  hooks.usePublications.mockReset();

  hooks.useCitation.mockReturnValue(query(envelope(citation())));
  hooks.useDatasetFiles.mockReturnValue(query(envelope(filesResponse)));
  hooks.useDatasetFields.mockReturnValue(query(envelope(fieldsResponse)));
  hooks.useDatasetLimitations.mockReturnValue(query(envelope(limitationsResponse)));
  hooks.usePublications.mockReturnValue(query(envelope(publicationsResponse)));
});

describe("Phase 4 scientific metadata panels", () => {
  it("renders a citation drawer with checksum, verification, and a real source link", () => {
    render(<CitationDrawer citationId="cit_f_test" onClose={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Citation record" })).toBeInTheDocument();
    expect(screen.getByText("PSI-10_Experimental table_Flame Design_Normal Flame.csv")).toBeInTheDocument();
    expect(screen.getByText("SHA-256 (actual)")).toBeInTheDocument();
    expect(screen.getAllByText("abc123").length).toBeGreaterThan(0);
    expect(screen.getByText("verified match")).toBeInTheDocument();
    expect(screen.getByText("sha256_match")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Download NASA source file/ })).toHaveAttribute(
      "href",
      "https://psi.nasa.gov/example",
    );
  });

  it("shows unavailable citations without a download link", () => {
    hooks.useCitation.mockReturnValue(
      query(
        envelope(
          citation({
            availability: {
              status: "unavailable",
              downloadable: false,
              reason: "The NASA PSI source returned HTTP 404.",
            },
            retrieval: {
              ...citation().retrieval,
              http_status: 404,
              download_status: "known_unavailable",
              bytes: null,
              checksum_actual: null,
              checksum_match: null,
            },
          }),
        ),
      ),
    );

    render(<CitationDrawer citationId="cit_f_unavailable" onClose={vi.fn()} />);

    expect(screen.getByText("The NASA PSI source returned HTTP 404.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download NASA source file/ })).not.toBeInTheDocument();
    expect(screen.getByText(/no downloadable file/)).toBeInTheDocument();
  });

  it("renders curated files and never gives the known-404 file a download link", () => {
    render(<DatasetFilesPanel datasetId="psi-98-metadata" onOpenCitation={vi.fn()} />);

    expect(screen.getAllByText(/3 curated/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not downloadable/).length).toBe(1);
    expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "https://psi.nasa.gov/example",
    );
    expect(screen.getByText(/Only curated files are listed/)).toBeInTheDocument();
  });

  it("opens a citation from a file card", async () => {
    const user = userEvent.setup();
    const onOpenCitation = vi.fn();
    render(<DatasetFilesPanel datasetId="psi-98-metadata" onOpenCitation={onOpenCitation} />);

    await user.click(screen.getAllByRole("button", { name: /Cite this source/ })[0]);
    expect(onOpenCitation).toHaveBeenCalledWith("cit_f_test");
  });

  it("renders field metadata and flags missing canonical values without substitution", () => {
    render(<DatasetFieldsPanel datasetId="psi-10-gas-flame" />);

    expect(screen.getByRole("heading", { name: "Field dictionary" })).toBeInTheDocument();
    expect(screen.getByText("Oxygen mole fraction")).toBeInTheDocument();
    expect(screen.getAllByText("ramped_condition_rows").length).toBeGreaterThan(0);
    expect(screen.getAllByText("missing").length).toBeGreaterThan(0);
    expect(screen.getByText(/Documented alternative, not an automatic substitute/)).toBeInTheDocument();
    expect(screen.getByText(/pressure_initial_atm/)).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 fields have a verified source-column mapping/)).toBeInTheDocument();
  });

  it("renders dataset and measurement limitations with scopes and evidence", () => {
    render(<DatasetLimitationsPanel datasetId="psi-10-gas-flame" />);

    expect(screen.getByRole("heading", { name: "Limitations and restrictions" })).toBeInTheDocument();
    expect(screen.getByText("Tad and Zst are computed by the source, not measured.")).toBeInTheDocument();
    expect(screen.getByText(/dataset-scoped and/)).toBeInTheDocument();
    expect(screen.getAllByText(/measurement-scoped limitations/).length).toBeGreaterThan(0);
    expect(screen.getByText(/remain open/)).toBeInTheDocument();
  });

  it("renders publication metadata without inventing year or venue", () => {
    render(<PublicationCard publication={publication()} />);

    expect(screen.getByText("A Mechanistic Study of Soret Diffusion")).toBeInTheDocument();
    expect(screen.getByText(/Yang Fan, Law C.K./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /10.2514\/6.2009-988/ })).toHaveAttribute(
      "href",
      "https://doi.org/10.2514/6.2009-988",
    );
    expect(screen.getByText(/year unavailable · venue unavailable/)).toBeInTheDocument();
  });

  it("renders a dataset publication panel with an explicit bibliographic-gap note", () => {
    render(<DatasetPublicationsPanel datasetId="psi-10-gas-flame" />);

    expect(screen.getByRole("heading", { name: "Related publications" })).toBeInTheDocument();
    expect(screen.getByText(/Year and venue are not present in the source/)).toBeInTheDocument();
    expect(screen.getByText("A Mechanistic Study of Soret Diffusion")).toBeInTheDocument();
  });

  it("withholds the paired chart when no verified alignment exists", () => {
    render(
      <PairedValuesPanel
        paired={pairedValues()}
        leftLabel="PSI-10 oxygen"
        rightLabel="PSI-159 oxygen"
      />,
    );

    expect(screen.getByText("No chart is rendered for this comparison.")).toBeInTheDocument();
    expect(screen.getByText(/No verified record-level alignment method/)).toBeInTheDocument();
    expect(screen.queryByTestId("paired-scatter-chart")).not.toBeInTheDocument();
    expect(isChartReady(pairedValues())).toBe(false);
  });

  it("renders the chart only when alignment is verified and numeric pairs exist", async () => {
    const valid = pairedValues({
      available: true,
      status: "available",
      alignment: {
        method_id: "method-test",
        verified: true,
        keys: ["test_code"],
        value_fields: { left: "left_value", right: "right_value" },
        unit_policy: "Identical units only.",
      },
      observations: [
        {
          pair_id: "pair-1",
          left: { value: 0.21, unit: "mole fraction", source_row: 2 },
          right: { value: 0.22, unit: "mole fraction", source_row: 3 },
        },
        {
          pair_id: "pair-2",
          left: { value: 0.23, unit: "mole fraction", source_row: 4 },
          right: { value: 0.24, unit: "mole fraction", source_row: 5 },
        },
      ],
      series: [
        {
          series_id: "series-test",
          label: "Verified pairs",
          x_unit: "mole fraction",
          y_unit: "mole fraction",
          points: [
            { x: 0.21, y: 0.22, pair_id: "pair-1" },
            { x: 0.23, y: 0.24, pair_id: "pair-2" },
          ],
        },
      ],
      reason: null,
    });

    expect(isChartReady(valid)).toBe(true);
    render(
      <PairedValuesPanel
        paired={valid}
        leftLabel="PSI-10 oxygen"
        rightLabel="PSI-159 oxygen"
      />,
    );

    expect(
      await screen.findByTestId("paired-scatter-chart", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Verified pairs/).length).toBeGreaterThan(0);
  });

  it("does not chart verified pairs that use different units", () => {
    const mixed = pairedValues({
      available: true,
      status: "available",
      alignment: {
        method_id: "method-test",
        verified: true,
        keys: ["test_code"],
        value_fields: {},
        unit_policy: null,
      },
      observations: [
        {
          pair_id: "pair-1",
          left: { value: 1, unit: "atm", source_row: 2 },
          right: { value: 1.01325, unit: "bar", source_row: 3 },
        },
      ],
    });

    expect(isChartReady(mixed)).toBe(false);
  });

  it("renders comparison integrity failures explicitly", () => {
    const check = datasetField().integrity;
    render(
      <ComparisonIntegrityPanel
        integrity={{
          status: "missing",
          checks: [check],
          failures: [{ ...check, measurement_id: "psi-159.pressure_initial_atm", status: "missing" }],
          not_checked: [],
          messages: ["Canonical values are missing for a registry measurement."],
        }}
      />,
    );

    expect(screen.getByText("Canonical measurement integrity")).toBeInTheDocument();
    expect(screen.getByText("Canonical values are missing for a registry measurement.")).toBeInTheDocument();
    expect(screen.getByText("1 failed check")).toBeInTheDocument();
    expect(screen.getByText("psi-159.pressure_initial_atm")).toBeInTheDocument();
  });
});
