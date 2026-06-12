"""
cv/flare_classifier.py — GOES XRS flare detection + R-scale classification

R_SCALE_MAP and classify_flare() ported verbatim from imp.md §10 Layer ①.

Live endpoint: https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json
  Returns 1-minute GOES X-ray flux readings for the past 24h.
  No authentication required.

Cache-first. Falls back to cached JSON on network failure.

Usage:
  python -m cv.flare_classifier --prefetch --storm 2024-10-G4
  python -m cv.flare_classifier --prefetch --storm 2024-05-G5
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

GOES_XRS_URL  = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
REQUEST_TIMEOUT = 15

# ── R-scale map — verbatim from imp.md §10 ────────────────────────────────────
R_SCALE_MAP: dict[str, int] = {
    "M1": 1, "M2": 1, "M3": 1, "M4": 1,
    "M5": 2, "M6": 2, "M7": 2, "M8": 2, "M9": 2,
    "X1": 3, "X2": 3, "X3": 3, "X4": 3, "X5": 3,
    "X6": 3, "X7": 3, "X8": 3, "X9": 3,
    "X10": 4,
    "X20": 5,
}

STORM_FLARE_CONFIG = {
    "2024-10-G4": {
        "storm_date": "2024-10-10T12:00:00Z",
        "cache_file": "data/cached/xrs/2024-10-10.json",
    },
    "2024-05-G5": {
        "storm_date": "2024-05-10T09:00:00Z",
        "cache_file": "data/cached/xrs/2024-05-10.json",
    },
}


def classify_flare(peak_flux_wm2: float) -> tuple[str, int]:
    """
    Return (class_string, r_scale) from peak GOES XRS-B flux in W/m².

    NOAA flux thresholds:
      X-class : >= 1e-4 W/m²  (X1 = 1e-4, X5 = 5e-4, X10 = 1e-3)
      M-class : >= 1e-5 W/m²  (M1 = 1e-5, M5 = 5e-5)
      C-class : >= 1e-6 W/m²  (no operational R-scale)

    The class multiplier is flux / class_floor:
      X: flux / 1e-4  → X1.0 ... X9.9
      M: flux / 1e-5  → M1.0 ... M9.9
    """
    if peak_flux_wm2 >= 1e-3:
        # X10+ — R4 below 2e-3, R5 at or above (X20)
        r = 5 if peak_flux_wm2 >= 2e-3 else 4
        n = peak_flux_wm2 / 1e-4
        return f"X{n:.1f}", r
    if peak_flux_wm2 >= 1e-4:
        # X1–X9.9: divide by 1e-4 so X1.0→n=1, X5.8→n=5.8
        n   = peak_flux_wm2 / 1e-4
        key = f"X{int(n)}" if n >= 1.0 else "M9"
        return f"X{n:.1f}", R_SCALE_MAP.get(key, 3)
    if peak_flux_wm2 >= 1e-5:
        # M1–M9.9: divide by 1e-5 so M1.0→n=1, M5.0→n=5
        n   = peak_flux_wm2 / 1e-5
        key = f"M{int(n)}"
        return f"M{n:.1f}", R_SCALE_MAP.get(key, 1)
    return "C", 0


def _fetch_goes_json(cache_file: str) -> list[dict]:
    """Fetch GOES XRS data. Returns parsed JSON list."""
    path = Path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        log.info("GOES XRS cache hit: %s", path)
        with open(path) as f:
            return json.load(f)

    log.info("Fetching GOES XRS from %s", GOES_XRS_URL)
    try:
        resp = requests.get(GOES_XRS_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("GOES XRS: %d readings cached", len(data))
        return data
    except Exception as exc:
        log.error("GOES XRS fetch failed: %s", exc)
        if path.exists():
            log.warning("Falling back to stale cache: %s", path)
            with open(path) as f:
                return json.load(f)
        return []


def fetch_and_classify_flare(
    storm_date: str,
    cache_file: str,
    window_hours: float = 6.0,
) -> dict:
    """
    Fetch GOES XRS data, find peak flux in a ±window_hours window around
    storm_date, and return a classified flare result.

    Returns:
        {
          "detected": bool,
          "class": str,       e.g. "X1.8"
          "r_scale": int,
          "source": "GOES-XRS",
          "onset": str,       ISO timestamp of peak flux
          "peak_flux_wm2": float,
          "s_scale": int,     always 0 — S-scale requires proton data
        }
    """
    data = _fetch_goes_json(cache_file)
    if not data:
        return _no_flare()

    try:
        storm_dt = datetime.fromisoformat(storm_date.replace("Z", "+00:00"))
    except ValueError:
        return _no_flare()

    cutoff_lo = storm_dt - timedelta(hours=window_hours)
    cutoff_hi = storm_dt + timedelta(hours=window_hours)

    # GOES JSON has keys "time_tag" and "flux" (XRS-B 0.1–0.8 nm)
    peak_flux  = 0.0
    peak_time  = ""
    for reading in data:
        t_str = reading.get("time_tag", "")
        flux  = reading.get("flux") or reading.get("observed_flux")
        if not (t_str and flux is not None):
            continue
        try:
            t = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if cutoff_lo <= t <= cutoff_hi:
            if float(flux) > peak_flux:
                peak_flux = float(flux)
                peak_time = t_str

    if peak_flux < 1e-6:
        log.info("No significant flare found near %s (peak=%.2e)", storm_date, peak_flux)
        return _no_flare()

    flare_class, r_scale = classify_flare(peak_flux)
    log.info("Flare: %s  R-scale: %d  peak: %.2e  at %s", flare_class, r_scale, peak_flux, peak_time)
    return {
        "detected":      True,
        "class":         flare_class,
        "r_scale":       r_scale,
        "s_scale":       0,
        "source":        "GOES-XRS",
        "onset":         peak_time,
        "peak_flux_wm2": round(peak_flux, 2),
    }


def _no_flare() -> dict:
    return {
        "detected":      False,
        "class":         "C",
        "r_scale":       0,
        "s_scale":       0,
        "source":        "GOES-XRS",
        "onset":         "",
        "peak_flux_wm2": 0.0,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    p = argparse.ArgumentParser(description="Prefetch GOES XRS flare data")
    p.add_argument("--prefetch", action="store_true")
    p.add_argument("--storm", choices=list(STORM_FLARE_CONFIG))
    args = p.parse_args()

    if args.prefetch and args.storm:
        cfg = STORM_FLARE_CONFIG[args.storm]
        result = fetch_and_classify_flare(cfg["storm_date"], cfg["cache_file"])
        print(f"Flare result for {args.storm}:")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
