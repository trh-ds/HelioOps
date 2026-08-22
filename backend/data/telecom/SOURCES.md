# Telecom knowledge base — sources

Ingested by `backend/embeddings/ingest_telecom.py` into `telecom_kb`.

## Why this directory did not exist before

`telecom_kb` was declared in `backend/embeddings/config.py` from the start but
had no ingest script and no source documents, so it sat at **0 chunks**.
Telecom advisories were grounded only by the two generic impact-matrix chunks
every industry receives, which is why they carried `LOW_COVERAGE` on every run
and cited nothing but `noaa_space_weather_scales.txt`.

## What is used

ITU-R P-series Recommendations: free, and the governing references for what a
geomagnetic storm actually does to a radio link. Downloaded 2026-08-21,
in-force versions.

| File | Rec | Covers | Why it matters for space weather |
|---|---|---|---|
| `itu_r_p531_ionospheric_propagation.pdf` | P.531-16 (2025-09) | Ionospheric propagation data and prediction methods | TEC, scintillation and group delay — the mechanism behind GNSS position error |
| `itu_r_p533_hf_propagation_prediction.pdf` | P.533-14 (2019-08) | HF circuit performance prediction | MUF collapse and absorption, i.e. why HF links fail during a storm |
| `itu_r_p372_radio_noise.pdf` | P.372-17 (2024-08) | Radio noise | Noise-floor rise that erodes link margin |
| `itu_r_p618_earth_space_propagation.pdf` | P.618-14 (2023-08) | Earth-space path propagation | Ionospheric scintillation on satellite links |

These four map onto the three subsystems a telecom operator has to make
decisions about during a storm: HF links, satellite links, and GNSS-derived
timing.

## Re-downloading

ITU-R Recommendations resolve by in-force version string. To find the current
one, read `https://www.itu.int/rec/R-REC-<REC>/en` and take the version tagged
`-I` (in force) rather than `-S` (superseded), then:

```
https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-<REC>-<ver>-<YYYYMM>-I!!PDF-E.pdf
```

Note the `/p/` path segment for P-series (`/m/` for M-series). Downloads are
slow (1–3 min each); set a generous timeout.

After adding or replacing a file:

```
python -m backend.embeddings.ingest_telecom
python -m backend.embeddings.rebuild_kb --verify
```

## Worth adding later

- **ITU-R P.834** — tropospheric/ionospheric path delay, for timing budgets.
- **3GPP TS 38.331 / timing-sync specs** — free from 3GPP, and the concrete
  link between GNSS holdover and mobile-network timing drift, which is the
  telecom impact operators care most about and which none of the above covers
  directly.
