"""
ML_after_CV/inference.py — LightGBM quantile regression inference.

Loads 6 trained checkpoints (GPS + HF, each with q0.025/q0.500/q0.975)
and predicts impact metrics from a cv.fusion.StormEvent dict.

Usage:
    from ML_after_CV.inference import predict
    result = predict(cv_event.model_dump())
    print(result.gps_error_m, result.hf_blackout_prob)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

log = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"

# G-scale → Kp index mapping (NOAA Space Weather Scales)
_G_TO_KP: dict[int, float] = {0: 0.0, 1: 5.0, 2: 6.0, 3: 7.0, 4: 8.3, 5: 9.0}

_FEATURE_COLS = [
    "g_scale", "kp_index", "bz_nt", "wind_speed_km_s",
    "cme_speed_km_s", "cme_width_deg", "r_scale",
    "geomag_lat_bin", "local_time_bin",
]

_MODELS: dict[str, Any] = {}


class ImpactPrediction(BaseModel):
    """Quantile regression predictions for GPS error and HF blackout."""
    gps_error_m: float
    gps_error_ci_low: float
    gps_error_ci_high: float
    hf_blackout_prob: float
    hf_blackout_ci_low: float
    hf_blackout_ci_high: float


def _load_models() -> None:
    """Load all 6 quantile models into the singleton cache."""
    if _MODELS:
        return

    try:
        import joblib
    except ImportError:
        log.warning("joblib not installed — ML inference disabled")
        return

    model_files = {
        "gps_q025": "gps_q025.pkl",
        "gps_q500": "gps_q500.pkl",
        "gps_q975": "gps_q975.pkl",
        "hf_q025":  "hf_q025.pkl",
        "hf_q500":  "hf_q500.pkl",
        "hf_q975":  "hf_q975.pkl",
    }

    for key, filename in model_files.items():
        path = _CHECKPOINT_DIR / filename
        if not path.exists():
            log.warning("Checkpoint missing: %s", path)
            return
        _MODELS[key] = joblib.load(path)

    log.info("Loaded %d ML checkpoints from %s", len(_MODELS), _CHECKPOINT_DIR)


def _extract_features(storm_dict: dict) -> pd.DataFrame:
    """Extract the 9 features LightGBM expects from a cv.fusion.StormEvent dict."""
    scales = storm_dict.get("scales", {})
    cme = storm_dict.get("cme", {})
    l1 = storm_dict.get("l1_solar_wind", {})

    g = int(scales.get("G", 0))

    features = {
        "g_scale":         g,
        "kp_index":        _G_TO_KP.get(g, 0.0),
        "bz_nt":           float(l1.get("bz_nt", 0.0)),
        "wind_speed_km_s": float(l1.get("speed_km_s", 400.0)),
        "cme_speed_km_s":  float(cme.get("speed_km_s", 500.0)),
        "cme_width_deg":   float(cme.get("angular_width_deg", 90.0)),
        "r_scale":         int(scales.get("R", 0)),
        "geomag_lat_bin":  1,  # default mid-latitude
        "local_time_bin":  1,  # default dayside
    }

    return pd.DataFrame([features], columns=_FEATURE_COLS)


def predict(storm_dict: dict) -> ImpactPrediction:
    """
    Run quantile regression inference on a cv.fusion.StormEvent dict.

    Returns ImpactPrediction with median + 95% CI for GPS error and HF blackout.
    Falls back to conservative defaults if models unavailable.
    """
    _load_models()

    if len(_MODELS) < 6:
        log.warning("ML models unavailable — returning conservative fallback predictions")
        return ImpactPrediction(
            gps_error_m=20.0,
            gps_error_ci_low=8.0,
            gps_error_ci_high=35.0,
            hf_blackout_prob=0.85,
            hf_blackout_ci_low=0.60,
            hf_blackout_ci_high=0.95,
        )

    df = _extract_features(storm_dict)

    gps_low = float(_MODELS["gps_q025"].predict(df)[0])
    gps_med = float(_MODELS["gps_q500"].predict(df)[0])
    gps_high = float(_MODELS["gps_q975"].predict(df)[0])

    hf_low = float(_MODELS["hf_q025"].predict(df)[0])
    hf_med = float(_MODELS["hf_q500"].predict(df)[0])
    hf_high = float(_MODELS["hf_q975"].predict(df)[0])

    # Enforce monotonicity (quantile crossing can happen with independent models)
    gps_low, gps_med, gps_high = sorted([gps_low, gps_med, gps_high])
    hf_low, hf_med, hf_high = sorted([hf_low, hf_med, hf_high])

    return ImpactPrediction(
        gps_error_m=max(0.0, gps_med),
        gps_error_ci_low=max(0.0, gps_low),
        gps_error_ci_high=max(0.0, gps_high),
        hf_blackout_prob=float(np.clip(hf_med, 0.0, 1.0)),
        hf_blackout_ci_low=float(np.clip(hf_low, 0.0, 1.0)),
        hf_blackout_ci_high=float(np.clip(hf_high, 0.0, 1.0)),
    )
