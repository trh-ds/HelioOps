"""
cv/l1_client.py — DSCOVR L1 solar wind client

Live endpoint: https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json
  Real-time solar wind from DSCOVR at L1. 1-minute cadence. No auth.

Cache-first. Falls back to cached JSON on network failure.

ETA formula: 1,500,000 km (L1→Earth) / speed_km_s / 60 → eta_minutes.
This matches imp.md §10 fuse() convention.

Usage:
  python -m cv.l1_client --prefetch --storm 2024-10-G4
  python -m cv.l1_client --prefetch --storm 2024-05-G5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

DSCOVR_URL     = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
REQUEST_TIMEOUT = 15
L1_EARTH_KM    = 1_500_000.0  # approximate L1 to Earth distance

STORM_L1_CONFIG = {
    "2024-10-G4": {"cache_file": "data/cached/l1/2024-10-11.json"},
    "2024-05-G5": {"cache_file": "data/cached/l1/2024-05-11.json"},
}


def fetch_l1_wind(cache_file: str) -> dict:
    """
    Fetch the most recent DSCOVR L1 solar wind reading.

    Returns:
        {
          "speed_km_s":  float,
          "bz_nt":       float,   Bz component of IMF in nT (negative = southward = geoeffective)
          "bt_nt":       float,   Total field magnitude
          "density_cm3": float,   Proton density
          "measured_at": str,     ISO timestamp of reading
          "eta_minutes": int,     L1 → Earth transit estimate
          "source":      "DSCOVR",
        }
    """
    path = Path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _load_or_fetch(path)
    if not data:
        return _fallback_l1()

    # DSCOVR JSON: list of readings, most recent last
    # Key names may vary — handle both RTSW and archive format
    reading = _pick_latest(data)
    if reading is None:
        return _fallback_l1()

    speed    = _safe_float(reading, ("proton_speed", "speed", "v_bulk"))
    bz       = _safe_float(reading, ("bz_gsm", "bz"))
    bt       = _safe_float(reading, ("bt", "b_total"))
    density  = _safe_float(reading, ("proton_density", "density"))
    time_tag = reading.get("time_tag", reading.get("propagated_time_tag", ""))

    speed = max(speed, 200.0)  # floor to avoid division issues
    eta_minutes = int(L1_EARTH_KM / speed / 60.0)

    return {
        "speed_km_s":  round(speed, 1),
        "bz_nt":       round(bz, 2),
        "bt_nt":       round(bt, 2),
        "density_cm3": round(density, 2),
        "measured_at": time_tag,
        "eta_minutes": eta_minutes,
        "source":      "DSCOVR",
    }


def _load_or_fetch(path: Path) -> list[dict]:
    if path.exists():
        log.info("L1 cache hit: %s", path)
        with open(path) as f:
            return json.load(f)

    log.info("Fetching DSCOVR L1 from %s", DSCOVR_URL)
    try:
        resp = requests.get(DSCOVR_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("DSCOVR: %d readings cached", len(data))
        return data
    except Exception as exc:
        log.error("DSCOVR fetch failed: %s", exc)
        if path.exists():
            log.warning("Falling back to stale cache: %s", path)
            with open(path) as f:
                return json.load(f)
        return []


def _pick_latest(data: list[dict]) -> dict | None:
    """Return the last non-null reading."""
    for reading in reversed(data):
        speed = _safe_float(reading, ("proton_speed", "speed", "v_bulk"))
        if speed > 0:
            return reading
    return data[-1] if data else None


def _safe_float(d: dict, keys: tuple[str, ...], default: float = 0.0) -> float:
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _fallback_l1() -> dict:
    return {
        "speed_km_s":  400.0,
        "bz_nt":       0.0,
        "bt_nt":       0.0,
        "density_cm3": 5.0,
        "measured_at": "",
        "eta_minutes": int(L1_EARTH_KM / 400.0 / 60.0),
        "source":      "DSCOVR (fallback defaults)",
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    p = argparse.ArgumentParser(description="Prefetch DSCOVR L1 solar wind data")
    p.add_argument("--prefetch", action="store_true")
    p.add_argument("--storm", choices=list(STORM_L1_CONFIG))
    args = p.parse_args()

    if args.prefetch and args.storm:
        cfg = STORM_L1_CONFIG[args.storm]
        result = fetch_l1_wind(cfg["cache_file"])
        print(f"L1 wind for {args.storm}:")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
