# Phase 4 Contracts

**Project:** Flame in Freefall
**Team:** AFAQ
**Status:** Implemented and tested (2026-11-10)
**API version:** `v1`
**Scope:** Citations, curated dataset files, field metadata, limitations, publications, gas-flame facets, comparison integrity, and paired-value eligibility.

This document records the Phase 4 response contracts with examples captured from the running service and the canonical data. It complements `API_DOCUMENTATION.md` (the broader contract) and `docs/api-implementation.md` (the running service). The comparison methodology is in `docs/comparison-alignment.md`.

Phase 4 does not add scientific values. Every new field is derived from one of:

- the curated download manifest (`data/registry/mvp_download_manifest.json`);
- the acquisition report (`data/reports/acquisition_report.json`);
- the canonical Parquet tables in `data/processed`;
- the comparability and serving registries in `data/metadata`;
- the NASA PSI investigation registry snapshot;
- `DATA_DICTIONARY.md` and verified parser constants.

---

## 1. Common envelope

Every success response has the same shape:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_46a81...",
    "registry_snapshot": "2026-11-08",
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "registry_version": "1.0.0",
    "retrieved_at": null,
    "generated_at": "2026-11-10T14:21:06.227612Z",
    "page": null
  },
  "provenance": [],
  "quality": {
    "status": "verified",
    "flags": [],
    "warnings": []
  }
}
```

List responses add `meta.page`:

```json
{
  "limit": 50,
  "offset": 0,
  "total": 74,
  "has_more": true
}
```

`meta.generated_at` and `meta.request_id` are volatile. The ETag is computed over a stable representation that excludes them, so a repeated request can return `304` without the body changing.

---

## 2. Citations

### 2.1 Architecture

Citations identify an exact source file or an exact source row. They are generated at request time from the curated manifest, the acquisition report, and canonical provenance; they are not stored as a new Parquet table.

| Kind | ID shape | Scope |
|---|---|---|
| File | `cit_f_<16 hex>` | One curated manifest file. |
| Row | `cit_r_<base64url>` | One accession, file, sheet, and 1-based row. |

Row IDs decode to a small JSON object, but clients treat them as opaque. The row locator is verified against canonical tables before the citation is returned.

### 2.2 List

```text
GET /api/v1/citations?accession=PSI-10&limit=2
```

```json
{
  "data": [
    {
      "citation_id": "cit_f_21df4ec92db1eca0",
      "kind": "file",
      "accession": "PSI-10",
      "dataset_ids": ["psi-10-gas-flame"],
      "file": {
        "name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "kind": "experimental_table",
        "manifest_dataset": "gas_flame_test",
        "priority": "primary",
        "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
        "in_added": true
      },
      "locator": {"type": "file", "sheet": null, "row": null},
      "source": {
        "kind": "nasa_psi_file",
        "accession": "PSI-10",
        "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
      },
      "retrieval": {
        "retrieved_at": "2026-11-08T22:14:49Z",
        "http_status": null,
        "download_status": "already_present",
        "bytes": 17314,
        "expected_bytes": 17314,
        "checksum_expected": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "checksum_actual": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "checksum_match": true
      },
      "verification": {
        "status": "verified",
        "checks": [
          "manifest_checksum_recorded",
          "retrieved_checksum_recorded",
          "checksum_matches_manifest",
          "acquisition_status_confirmed"
        ]
      },
      "availability": {
        "status": "available",
        "downloadable": true,
        "reason": null
      },
      "provenance": [
        {
          "kind": "nasa_psi_file",
          "accession": "PSI-10",
          "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
          "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
          "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
        }
      ]
    }
  ],
  "meta": {
    "page": {"limit": 2, "offset": 0, "total": 74, "has_more": true}
  }
}
```

The list contains **74 file-level citations** for the curated manifest. Filters include `accession`, `dataset_id`, `kind`, and `availability`.

### 2.3 Row citation detail

```text
GET /api/v1/citations/cit_r_eyJhIjoiUFNJLTEwIiwiZiI6IlBTSS0xMF9FeHBlcmltZW50YWwgdGFibGVfRmxhbWUgRGVzaWduX0ludmVyc2UgRmxhbWUuY3N2IiwiciI6MSwicyI6bnVsbH0
```

```json
{
  "data": {
    "citation_id": "cit_r_eyJhIjoiUFNJLTEwIiwiZiI6IlBTSS0xMF9FeHBlcmltZW50YWwgdGFibGVfRmxhbWUgRGVzaWduX0ludmVyc2UgRmxhbWUuY3N2IiwiciI6MSwicyI6bnVsbH0",
    "kind": "row",
    "accession": "PSI-10",
    "dataset_ids": ["psi-10-gas-flame"],
    "file": {
      "name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
      "kind": "experimental_table",
      "manifest_dataset": "gas_flame_test",
      "priority": "primary",
      "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
      "in_added": true
    },
    "locator": {"type": "row", "sheet": null, "row": 1, "row_range": [1, 1]},
    "source": {
      "kind": "nasa_psi_file",
      "accession": "PSI-10",
      "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
      "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
    },
    "retrieval": {
      "retrieved_at": "2026-11-08T22:14:49Z",
      "http_status": null,
      "download_status": "already_present",
      "bytes": 17314,
      "expected_bytes": 17314,
      "checksum_expected": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "checksum_actual": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "checksum_match": true
    },
    "verification": {"status": "verified", "checks": ["canonical_row_located"]},
    "availability": {"status": "available", "downloadable": true, "reason": null},
    "row_verification": {
      "row_verified": true,
      "row_tables": ["gas_flame_test", "experimental_table_cell", "source_row"],
      "warnings": []
    },
    "provenance": [
      {
        "kind": "nasa_psi_file",
        "accession": "PSI-10",
        "file": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "sheet": null,
        "rows": [1],
        "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "retrieved_at": "2026-11-08T22:14:49Z",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
      }
    ]
  }
}
```

Rules:

- A file citation is available only when the manifest and acquisition records verify it.
- A row citation is returned only when the exact row is located in a canonical table. Unknown rows return `404 citation_not_found`.
- A known 404 file has `availability.status: "unavailable"`, `downloadable: false`, `retrieval.http_status: 404`, and `source.sha256: null`. No checksum is invented.
- Row-level responses (`gas-flame`, material, droplet) and `/provenance` include `citation_id`; provenance entries include `file_citation_id` and `row_citation_ids`.

---

## 3. Dataset files

### 3.1 Scope

The file browser uses the curated download manifest, not the full public archive inventory. It lists selected files and documented known-unavailable files. It does not expose unselected archive files or filesystem paths.

```text
GET /api/v1/datasets/psi-10-gas-flame/files
```

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "files": [
      {
        "file_id": "cit_f_21df4ec92db1eca0",
        "citation_id": "cit_f_21df4ec92db1eca0",
        "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "accession": "PSI-10",
        "dataset_ids": ["psi-10-gas-flame"],
        "kind": "experimental_table",
        "priority": "primary",
        "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv",
        "availability": "available",
        "downloadable": true,
        "availability_reason": null,
        "download": {
          "status": "already_present",
          "http_status": null,
          "bytes": 17314,
          "retrieved_at": "2026-11-08T22:14:49Z",
          "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
          "checksum_match": true
        },
        "verification": {
          "status": "verified",
          "checks": [
            "manifest_checksum_recorded",
            "retrieved_checksum_recorded",
            "checksum_matches_manifest",
            "acquisition_status_confirmed"
          ]
        },
        "provenance": [
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
            "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
          }
        ]
      }
    ],
    "summary": {
      "curated_files": 2,
      "available_files": 2,
      "unavailable_files": 0,
      "downloadable_files": 2,
      "known_unavailable_files": 0,
      "experimental_tables": 2
    },
    "inventory": {
      "public_inventory_file_count": 74,
      "curated_file_count": 2,
      "not_selected_file_count": 72,
      "public_experimental_table_count": 2,
      "archive_status": "available",
      "note": "Only curated files are listed. The public inventory count is shown for context; unselected archive files are not exposed."
    }
  }
}
```

### 3.2 PSI-98 known-unavailable files

PSI-98 has three curated files: one summary CSV and two telemetry/sensor XLSX files that are listed by NASA but return HTTP 404.

```text
GET /api/v1/datasets/psi-98-metadata/files
```

```json
{
  "summary": {
    "curated_files": 3,
    "available_files": 1,
    "unavailable_files": 2,
    "downloadable_files": 1,
    "known_unavailable_files": 2,
    "experimental_tables": 1
  },
  "inventory": {
    "public_inventory_file_count": 74,
    "curated_file_count": 3,
    "not_selected_file_count": 71,
    "public_experimental_table_count": 1,
    "archive_status": "available",
    "note": "Only curated files are listed. The public inventory count is shown for context; unselected archive files are not exposed."
  }
}
```

| File | Availability | Downloadable | HTTP status | SHA-256 |
|---|---|---|---|---|
| `PSI-98_Experimental table_SAFFIRE-1.csv` | `available` | `true` | `200` | `c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d` |
| `PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx` | `unavailable` | `false` | `404` | `null` |
| `PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx` | `unavailable` | `false` | `404` | `null` |

The unavailable files are never rendered as download links. Their `verification.status` is `unavailable`, and their reason records the 404.

---

## 4. Field metadata

### 4.1 Derivation

Field records come from the 93 comparability measurements plus verified source-column mappings from parser constants, `experimental_table_schemas.json`, `DATA_DICTIONARY.md`, and `src/data_pipeline/channels.py`.

```text
GET /api/v1/datasets/psi-10-gas-flame/fields?limit=2
```

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "fields": [
      {
        "field_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
        "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
        "canonical_name": "adiabatic_flame_temp_k",
        "parameter": "adiabatic_flame_temp_k",
        "description": "Adiabatic flame temperature computed by the source.",
        "physical_quantity": "adiabatic_flame_temperature",
        "unit": "K",
        "unit_status": "stated",
        "value_kind": "computed",
        "measurement_method": "Source-computed field (Tad (K)).",
        "calibration": {"status": "not_applicable", "note": null},
        "missingness": {
          "availability": "available",
          "restrictions": [
            "computed_source_field",
            "method_not_documented",
            "ramped_condition_rows"
          ],
          "canonical_presence": {
            "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
            "checked": true,
            "status": "available",
            "reason": null,
            "table": "gas_flame_test",
            "field": "adiabatic_flame_temp_k",
            "accession": "PSI-10",
            "total_rows": 327,
            "non_null_count": 256,
            "alternatives": []
          },
          "policy": "Missing values are never zero; qualifiers and sentinels are preserved as documented in DATA_DICTIONARY.md."
        },
        "integrity": {
          "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
          "checked": true,
          "status": "available",
          "reason": null,
          "table": "gas_flame_test",
          "field": "adiabatic_flame_temp_k",
          "accession": "PSI-10",
          "total_rows": 327,
          "non_null_count": 256,
          "alternatives": []
        },
        "alternatives": [],
        "flags": ["computed_source_field", "method_not_documented", "ramped_condition_rows"],
        "comparability": {
          "status": "blocked",
          "compatible_datasets": [],
          "incompatible_datasets": ["psi-10-gas-flame", "psi-159-gas-flame"],
          "rules": [
            {
              "rule_id": "psi10-psi159-tad",
              "status": "insufficient_metadata",
              "scientific_justification": "Both columns are named Tad (K), but the selected files do not document the computation method. A matching column name is not a comparison basis."
            },
            {
              "rule_id": "psi10-tad-zst",
              "status": "not_comparable",
              "scientific_justification": "Adiabatic flame temperature and stoichiometric mixture fraction are different computed quantities."
            },
            {
              "rule_id": "psi159-peakc-tad",
              "status": "blocked",
              "scientific_justification": "Measured peak burner temperature and computed adiabatic flame temperature are different physical quantities and different value kinds. They must never be presented as the same temperature."
            }
          ]
        },
        "source_columns": [
          {
            "raw_column": "Tad (K)",
            "source_file": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            "applies_to": "Normal flame rows"
          },
          {
            "raw_column": "Tad (K)",
            "source_file": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
            "applies_to": "Inverse flame rows"
          }
        ],
        "source_references": [
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            "sha256": "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv"
          },
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
            "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
          },
          {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.1-4.2 PSI-10 ACME Flame Design"
          }
        ]
      }
    ],
    "summary": {
      "field_count": 11,
      "with_verified_source_column": 10,
      "with_canonical_values": 10,
      "without_canonical_values": 1,
      "presence_not_checked": 0,
      "value_kinds": {"categorical": 2, "computed": 4, "measured": 5},
      "comparison_statuses": {
        "blocked": 3,
        "conditionally_comparable": 4,
        "insufficient_metadata": 1,
        "not_comparable": 3
      }
    }
  }
}
```

### 4.2 Integrity statuses

| Status | Meaning |
|---|---|
| `available` | The registry field has canonical values. |
| `missing` | The registry marks the field available, but the canonical table has zero non-null values. |
| `not_checked` | Presence was not checked because the measurement is not a canonical table field. |
| `no_canonical_tables` | The dataset has no canonical tables, such as PSI-98 metadata-only. |

### 4.3 Real missing-field examples

PSI-159 `pressure_initial_atm` is registry-marked available but has zero values in the canonical table. The field endpoint returns:

```json
{
  "field_id": "psi-159-gas-flame.pressure_initial_atm",
  "unit": "atm",
  "integrity": {
    "measurement_id": "psi-159-gas-flame.pressure_initial_atm",
    "checked": true,
    "status": "missing",
    "reason": "no_non_null_values",
    "table": "gas_flame_test",
    "field": "pressure_initial_atm",
    "accession": "PSI-159",
    "total_rows": 333,
    "non_null_count": 0,
    "alternatives": [
      {
        "canonical_field": "pressure_approx_bar",
        "unit": "bar",
        "description": "PSI-159 reports approximate test pressure in bar. It is not an initial pressure in atm and is not interchangeable with one.",
        "evidence": {
          "kind": "document",
          "path": "DATA_DICTIONARY.md",
          "section": "4.3-4.4 PSI-159 ACME CFI-G"
        }
      }
    ]
  }
}
```

PSI-10 has the inverse problem: `pressure_approx_bar` is empty, and `pressure_initial_atm` carries 327 atm values. The API reports the alternative; it does not convert or merge the units.

### 4.4 PSI-98 metadata-only field

PSI-98 has one metadata-only measurement field, `psi-98-metadata.telemetry_sensor_data`. Its integrity status is `not_checked` with reason `no_canonical_tables`, not an empty field list.

---

## 5. Limitations

Limitations are stable, scoped records with evidence. The dataset endpoint returns dataset and measurement limitations with summary counts.

```text
GET /api/v1/datasets/psi-10-gas-flame/limitations?limit=2
```

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "limitations": [
      {
        "limitation_id": "lim_d_psi_10_gas_flame_computed_tad_zst",
        "scope": "dataset",
        "scope_id": "psi-10-gas-flame",
        "dataset_id": "psi-10-gas-flame",
        "accession": "PSI-10",
        "category": "value_kind",
        "severity": "warning",
        "code": "computed_tad_zst",
        "explanation": "Tad (K) and Zst are computed by the source, not measured.",
        "affected_operations": [
          "exploration",
          "quantitative_comparison",
          "time_series"
        ],
        "evidence": [
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            "sha256": "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv"
          },
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
            "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
          },
          {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.1-4.2 PSI-10 ACME Flame Design"
          },
          {
            "kind": "document",
            "path": "data/reports/dataset_quality_report.json",
            "section": "gas_flame_test"
          }
        ],
        "resolution_status": "documented",
        "resolution_note": "Recorded as a dataset-level serving limitation."
      }
    ],
    "summary": {
      "total": 65,
      "by_scope": {"dataset": 9, "measurement": 56},
      "by_severity": {"error": 1, "warning": 64},
      "by_status": {"documented": 63, "open": 2}
    }
  }
}
```

Limitation categories are `data_quality`, `availability`, `value_kind`, `calibration`, `unit`, `serving`, `provenance`, and `integrity`. Full-sentence serving restrictions are normalized to stable `serving_restriction_<hash>` codes with the sentence preserved as the explanation. Fields already marked `missing` in the registry are not duplicated as integrity limitations.

---

## 6. Publications

### 6.1 Deduplication

The source registry has 352 publication records. Deduplication by DOI when present, otherwise normalized title, produces **299 unique publications**; **235 have a DOI** and **64 do not**. All records have `status: "published"`. Year and venue are not present in the registry snapshot and are returned as `null`.

```text
GET /api/v1/publications?limit=2
```

```json
{
  "data": {
    "publications": [
      {
        "publication_id": "pub_0c1b7d7e064074d9",
        "title": "A  Mechanistic Study of Soret Diffusion in Hydrogen-Air Flames",
        "title_variants": [],
        "authors": ["Yang Fan", "Law C.K", "Sung C.J", "Zhang Huiqiang"],
        "authors_raw": "Yang Fan, Law C.K., Sung C.J., Zhang Huiqiang",
        "authors_raw_variants": [],
        "author_parse": "source_comma_or_and_delimited",
        "doi": "10.2514/6.2009-988",
        "doi_url": "https://doi.org/10.2514/6.2009-988",
        "year": null,
        "venue": null,
        "status": "published",
        "related_investigations": [
          {
            "accession": "PSI-23",
            "title": "Advanced Combustion via Microgravity Experiments-Structure and Response of Spherical Diffusion Flames",
            "doi": "10.60555/k57n-p030",
            "acronym": "ACME s-Flame"
          }
        ],
        "source_references": [
          {
            "kind": "psi_investigation_registry",
            "path": "data/registry/psi_combustion_investigations.json",
            "accession": "PSI-23",
            "field": "publications"
          }
        ],
        "verification": {
          "status": "registry_verified",
          "source": "data/registry/psi_combustion_investigations.json",
          "snapshot_date": "2026-11-08",
          "verified_fields": ["title", "authors", "doi", "status"],
          "unavailable_fields": ["year", "venue"],
          "conflicts": {"title_variants": [], "authors_raw_variants": []}
        },
        "field_status": {
          "title": "source_provided",
          "authors": "source_provided",
          "doi": "source_provided",
          "year": "not_available_in_registry",
          "venue": "not_available_in_registry",
          "status": "source_provided"
        }
      }
    ],
    "summary": {
      "publication_count": 299,
      "with_doi": 235,
      "without_doi": 64,
      "year_available": false,
      "venue_available": false,
      "note": "Year and venue are not present in the NASA PSI registry and are returned as unavailable."
    }
  }
}
```

Conflicting titles and author strings are preserved as `title_variants` and `authors_raw_variants`; they are not silently resolved. Filters include `accession`, `dataset_id`, `q`, `doi`, and pagination. A conflicting `accession` and `dataset_id` returns `400 conflicting_filters`.

---

## 7. Gas-flame facets

Facets are computed from canonical `gas_flame_test` rows. Default behavior matches the list endpoint: rows carrying ramped-condition or low-oxygen qualifiers are excluded, and the excluded count is reported.

```text
GET /api/v1/gas-flame/facets
```

```json
{
  "data": {
    "accessions": [
      {"accession": "PSI-10", "total_rows": 327, "included_rows": 256, "excluded_qualified_rows": 71},
      {"accession": "PSI-159", "total_rows": 333, "included_rows": 333, "excluded_qualified_rows": 0}
    ],
    "include_qualified": false,
    "excluded_qualified_rows": 71,
    "pressure": {
      "by_accession": [
        {
          "accession": "PSI-10",
          "field": "pressure_initial_atm",
          "unit": "atm",
          "count": 256,
          "missing_count": 0,
          "min": 0.42460704,
          "max": 3.0076332,
          "histogram": [
            {"min": 0.42460704, "max": 0.74748531, "count": 23},
            {"min": 0.74748531, "max": 1.07036358, "count": 169},
            {"min": 1.07036358, "max": 1.39324185, "count": 42}
          ]
        },
        {
          "accession": "PSI-159",
          "field": "pressure_approx_bar",
          "unit": "bar",
          "count": 333,
          "missing_count": 0,
          "min": 0.4953817,
          "max": 3.3099,
          "histogram": [
            {"min": 0.4953817, "max": 0.8471964875, "count": 65},
            {"min": 0.8471964875, "max": 1.199011275, "count": 147},
            {"min": 1.199011275, "max": 1.5508260625, "count": 0}
          ]
        }
      ],
      "note": "PSI-10 pressure_initial_atm is in atm; PSI-159 pressure_approx_bar is in bar. The values are not converted or merged."
    },
    "notes": [
      "Facet counts are computed from the canonical gas-flame rows.",
      "Pressure is reported per accession and is never combined: PSI-10 uses atm and PSI-159 uses bar.",
      "Case variants are preserved exactly as published.",
      "Blank and sentinel values are missing, not zero.",
      "Rows carrying ramped-condition or low-oxygen qualifiers are excluded by default, matching the list endpoint.",
      "Excluded qualified-row counts are reported per accession in the accessions facet.",
      "The oxygen facet uses oxygen_mole_fraction. PSI-10 normal rows and PSI-159 normal rows carry their oxygen in initial/before columns; those are reported separately."
    ]
  }
}
```

Facet values preserve source case. For example, `flame_type` includes `Normal`, `Inverse`, and `inverse`; `hot_ignition` includes `Yes`, `No`, `yes`, `no`, and `flash`. The API does not normalize them.

---

## 8. Comparison integrity and paired values

`GET /api/v1/compare` adds two controls to the Phase 2 decision:

- `integrity` reports canonical-data presence for both measurements.
- `paired_values` reports eligibility, conditions, alignment, observations, series, exclusions, dataset version, provenance, and a withholding reason.

A clean integrity example for PSI-10/PSI-159 oxygen:

```json
{
  "integrity": {
    "status": "passed",
    "checks": [
      {
        "measurement_id": "psi-10-gas-flame.oxygen_mole_fraction",
        "checked": true,
        "status": "available",
        "reason": null,
        "table": "gas_flame_test",
        "field": "oxygen_mole_fraction",
        "accession": "PSI-10",
        "total_rows": 327,
        "non_null_count": 109,
        "alternatives": []
      },
      {
        "measurement_id": "psi-159-gas-flame.oxygen_mole_fraction",
        "checked": true,
        "status": "available",
        "reason": null,
        "table": "gas_flame_test",
        "field": "oxygen_mole_fraction",
        "accession": "PSI-159",
        "total_rows": 333,
        "non_null_count": 154,
        "alternatives": []
      }
    ],
    "failures": [],
    "not_checked": [],
    "messages": []
  }
}
```

With no conditions supplied, the decision is `conditionally_comparable` and paired values are withheld:

```json
{
  "paired_values": {
    "available": false,
    "status": "unavailable",
    "alignment": {
      "method_id": null,
      "verified": false,
      "keys": [],
      "value_fields": {},
      "unit_policy": null
    },
    "conditions": {
      "supplied": {},
      "required": [
        {"key": "same_oxygen_basis", "satisfied": null},
        {"key": "flame_configuration_documented", "satisfied": null}
      ]
    },
    "observations": [],
    "series": [],
    "exclusions": [],
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "reason": {
      "code": "conditions_not_verified",
      "message": "Required comparison conditions are not verified, so no paired values are returned.",
      "missing_conditions": ["same_oxygen_basis", "flame_configuration_documented"]
    }
  }
}
```

With both conditions supplied, the decision becomes `comparable`, but paired values remain unavailable because no alignment method is registered:

```json
{
  "paired_values": {
    "available": false,
    "status": "unavailable",
    "reason": {
      "code": "no_verified_alignment",
      "message": "The comparison is approved, but no verified record-level alignment method is registered for this rule. The API does not pair by row number, interpolate, normalize silently, or convert ambiguous units.",
      "rule_id": "psi10-psi159-oxygen",
      "required_alignment": {
        "keys": [],
        "note": "A committed method must name exact alignment keys and value fields."
      }
    }
  }
}
```

The methodology and reason codes are documented in `docs/comparison-alignment.md`.

---

## 9. Cache, rate limiting, and request identity

| Concern | Behavior |
|---|---|
| `ETag` | Stable hash over the success representation, excluding `meta.request_id` and `meta.generated_at`. |
| `If-None-Match` | Returns `304` when the representation is unchanged. |
| `Cache-Control` | Default `public, max-age=60, must-revalidate`; errors use `no-store`; health is excluded. |
| Rate limit | Default 600 requests per 60 seconds per client, process-local fixed window. |
| `429` | Includes `Retry-After`. |
| Request ID | `X-Request-ID` is exposed and echoed in `meta.request_id` and error envelopes. |
| Logs | Structured fields: `request_id`, `method`, `path`, `status`, `duration_ms`. |
| Authentication | None. The API is public and read-only; rate limiting is an abuse control. |

Environment settings:

```text
FLAME_CACHE_ENABLED
FLAME_CACHE_MAX_AGE
FLAME_CACHE_CONTROL
FLAME_RATE_LIMIT_ENABLED
FLAME_RATE_LIMIT_REQUESTS
FLAME_RATE_LIMIT_WINDOW_SECONDS
FLAME_TRUST_PROXY
```

---

## 10. Verification commands

```bash
# Citations
curl -s 'http://127.0.0.1:8000/api/v1/citations?accession=PSI-10&limit=2'

# PSI-98 known-unavailable files
curl -s 'http://127.0.0.1:8000/api/v1/datasets/psi-98-metadata/files'

# Missing PSI-159 pressure field with alternative
curl -s 'http://127.0.0.1:8000/api/v1/datasets/psi-159-gas-flame/fields?physical_quantity=pressure'

# Facets
curl -s 'http://127.0.0.1:8000/api/v1/gas-flame/facets'

# Paired values withheld
curl -s 'http://127.0.0.1:8000/api/v1/compare?left=psi-10-gas-flame.oxygen_mole_fraction&right=psi-159-gas-flame.oxygen_mole_fraction'

# Conditional request
curl -sI 'http://127.0.0.1:8000/api/v1/citations?limit=2' | grep -i etag
```

The automated coverage is in `tests/test_phase4_api.py` and `tests/test_operations.py`. The full backend suite is **297 passing tests**; frontend coverage is **54 unit/component tests** and **24 Playwright flows** with **6 axe scans**.
