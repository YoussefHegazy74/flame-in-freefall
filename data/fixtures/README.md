# Authentic fixtures

These files are small, exact excerpts from the verified NASA PSI sources. They
are not synthetic data. Each fixture keeps the source header unchanged and
copies a small number of real rows without editing values.

`fixtures_manifest.json` records, for every fixture:

- the raw source path and its SHA-256;
- the 1-based source data-row numbers (after the header);
- the fixture SHA-256 and byte size;
- the source encoding and column count;
- why the excerpt exists.

Rebuild or check the fixtures from the downloaded raw files:

```bash
python scripts/build_fixtures.py
python scripts/build_fixtures.py --check
```

The check fails if the fixture manifest or a fixture checksum drifts. The
generator also refuses to build when a source checksum does not match the
acquisition manifest.

## Files

| Fixture | Source | Purpose |
|---|---|---|
| `csv/psi10_normal_sentinels.csv` | PSI-10 normal flame table | Normal row, `RAMPED` condition, missing final O2/pressure state. |
| `csv/psi159_normal_sample.csv` | PSI-159 normal flame table | CFI-G normal rows, categorical `TFP`, dash sentinels. |
| `csv/psi159_inverse_errors.csv` | PSI-159 inverse flame table | Dash sentinels, blank color, `#VALUE!` cells. |
| `csv/psi69_flex_cp1252.csv` | PSI-69 FLEX table | Windows-1252 text; `0x96` is an en dash, not a replacement character. |
| `csv/psi101_hkp_sentinel.csv` | PSI-101 HKP `gmt250_1` | Normal P-Trak value and `-999` instrument sentinel. |
| `csv/psi101_hkp_indefinite.csv` | PSI-101 HKP `gmt242_6_run89` | Windows indefinite token `-1.#IND`. |
| `csv/psi100_raw_sample.csv` | PSI-100 raw telemetry CSV | Valid time, negative sentinel time, scientific notation. |

The full raw files, interim Parquet, and processed Parquet remain outside Git.
These fixtures exist so parser behavior can be tested without committing a
NASA data archive.
