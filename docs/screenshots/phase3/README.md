# Phase 3 Frontend Screenshots

Captured on 2026-11-09 from the running Next.js application at
`http://localhost:3000`, connected to the real FastAPI service at
`http://127.0.0.1:8000/api/v1` and the canonical NASA-derived data.

| File | Route |
|---|---|
| `01-overview.png` | `/` |
| `02-investigations.png` | `/investigations` |
| `03-datasets.png` | `/datasets` |
| `04-dataset-detail.png` | `/datasets/psi-100-telemetry` |
| `05-gas-flame.png` | `/experiments/gas-flame` |
| `06-materials.png` | `/experiments/materials` |
| `07-droplets.png` | `/experiments/droplets` |
| `08-telemetry.png` | `/telemetry` with the first PSI-100 run and `pcm_air_temp_c` |
| `09-smoke.png` | `/smoke` with `HKPData_gmt211_2` and `gas_plume_temp_c` |
| `10-compare-conditional.png` | `/compare` with the PSI-10/PSI-159 oxygen conditional rule |
| `11-quality.png` | `/quality` |
| `12-provenance.png` | `/provenance` resolved for PSI-10 row 2 |
| `13-about.png` | `/about` |

The screenshots are full-page captures at a 1440 px viewport. They are
documentation artifacts, not fixtures. The values shown are live API responses
and can change if the canonical data or registries change.
