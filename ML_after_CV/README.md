# ML_after_CV/ — Impact Prediction Layer

LightGBM quantile regression models predicting GPS positioning error and HF radio blackout probability from storm features.

## Architecture

```
StormEvent (from cv/) → feature extraction → 6 LightGBM models → ImpactPrediction
                                              ├── gps_q025  (2.5th percentile)
                                              ├── gps_q500  (median)
                                              ├── gps_q975  (97.5th percentile)
                                              ├── hf_q025
                                              ├── hf_q500
                                              └── hf_q975
```

## Files

| File | Purpose |
|------|---------|
| `inference.py` | **Production** — loads checkpoints, extracts features, returns predictions with 95% CIs |
| `01_data_generation_eda.py` | Training — synthetic storm data generation + EDA |
| `02_train_and_tune.py` | Training — LightGBM hyperparameter tuning + model training |
| `03_anchor_test.py` | Validation — G5 anchor test (GPS >15m, HF >90%) |
| `checkpoints/` | 6 trained `.pkl` models (not tracked in git) |
| `data/synthetic_storms.csv` | Training dataset |
| `FINAL_RESULTS.md` | Model performance summary |
| `execution_report.md` | Full training execution log |

## Feature Extraction

From `cv.fusion.StormEvent`:

| Feature | Source | Transform |
|---------|--------|-----------|
| `g_scale` | `scales["G"]` | direct |
| `kp_index` | G→Kp map | `{0:0, 1:5, 2:6, 3:7, 4:8.3, 5:9}` |
| `bz_nt` | `l1_solar_wind["bz_nt"]` | direct |
| `wind_speed_km_s` | `l1_solar_wind["speed_km_s"]` | direct |
| `cme_speed_km_s` | `cme["speed_km_s"]` | direct |
| `cme_width_deg` | `cme["angular_width_deg"]` | direct |
| `r_scale` | `scales["R"]` | direct |
| `geomag_lat_bin` | default | 1 (mid-latitude) |
| `local_time_bin` | default | 1 (dayside) |

## Inference

```python
from ML_after_CV.inference import predict

result = predict(storm_event.model_dump())
# result.gps_error_m        → median GPS error (meters)
# result.gps_error_ci_low   → 2.5th percentile
# result.gps_error_ci_high  → 97.5th percentile
# result.hf_blackout_prob   → median HF blackout probability
# result.hf_blackout_ci_low / ci_high → 95% CI
```

Falls back to conservative defaults (GPS=20m, HF=85%) if checkpoints missing.

## Quantile Monotonicity

Independently trained quantile models can cross (e.g., q97.5 < q50). Enforced via `sorted()` post-prediction to guarantee `ci_low ≤ median ≤ ci_high`.
