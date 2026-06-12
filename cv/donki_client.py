"""
cv/donki_client.py — NASA DONKI CME Analysis API client

Endpoint: https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis
  ?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&mostAccurate=true

Cache-first: reads from disk on hit, writes on miss.
Falls back to cached file on network failure (demo-safe).

Usage:
  python -m cv.donki_client --prefetch --storm 2024-10-G4
  python -m cv.donki_client --prefetch --storm 2024-05-G5
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

DONKI_BASE = "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis"
REQUEST_TIMEOUT = 15  # seconds
AU_KM = 1.496e8
RSUN_KM = 695_700.0
START_RADIUS_KM = 21.5 * RSUN_KM   # DONKI reference point

STORM_DONKI_CONFIG = {
    "2024-10-G4": {
        "start_date": "2024-10-08",
        "end_date":   "2024-10-12",
        "storm_date": "2024-10-10T12:00:00Z",
    },
    "2024-05-G5": {
        "start_date": "2024-05-08",
        "end_date":   "2024-05-12",
        "storm_date": "2024-05-10T06:00:00Z",
    },
}


def _cache_path(start_date: str, end_date: str, cache_dir: str) -> Path:
    return Path(cache_dir) / f"cme_{start_date}_{end_date}.json"


def fetch_cme_analyses(
    start_date: str,
    end_date: str,
    cache_dir: str,
) -> list[dict]:
    """
    Return CMEAnalysis records from DONKI for the given date window.

    Cache-first: reads {cache_dir}/cme_{start}_{end}.json on hit.
    On miss: fetches from DONKI, writes cache, then returns.
    On network failure: returns cached file if available, else [].
    """
    path = _cache_path(start_date, end_date, cache_dir)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if path.exists():
        log.info("DONKI cache hit: %s", path)
        with open(path) as f:
            return json.load(f)

    log.info("DONKI cache miss — fetching %s → %s", start_date, end_date)
    try:
        resp = requests.get(
            DONKI_BASE,
            params={"startDate": start_date, "endDate": end_date, "mostAccurate": "true"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            log.warning("Unexpected DONKI response type: %s", type(data))
            data = []
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("DONKI: %d records cached to %s", len(data), path)
        return data
    except Exception as exc:
        log.error("DONKI fetch failed: %s", exc)
        if path.exists():
            log.warning("Falling back to stale cache: %s", path)
            with open(path) as f:
                return json.load(f)
        return []


def select_best_cme(
    analyses: list[dict],
    storm_date: str,
    window_hours: float = 12.0,
) -> Optional[dict]:
    """
    Pick the most accurate, fastest CME within window_hours of storm_date.

    Filters:
      - isMostAccurate == True (DONKI flag)
      - time21_5 within ±window_hours of storm_date

    Returns the highest-speed candidate, or None if no match.
    """
    if not analyses:
        return None

    try:
        storm_dt = datetime.fromisoformat(storm_date.replace("Z", "+00:00"))
    except ValueError:
        log.error("Cannot parse storm_date: %s", storm_date)
        return None

    cutoff_lo = storm_dt - timedelta(hours=window_hours)
    cutoff_hi = storm_dt + timedelta(hours=window_hours)

    candidates = []
    for rec in analyses:
        if not rec.get("isMostAccurate"):
            continue
        t_str = rec.get("time21_5") or rec.get("startTime", "")
        if not t_str:
            continue
        try:
            t = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if cutoff_lo <= t <= cutoff_hi:
            candidates.append(rec)

    if not candidates:
        log.warning("No isMostAccurate DONKI records within ±%.0fh of %s", window_hours, storm_date)
        # Relax: take any record in window
        for rec in analyses:
            t_str = rec.get("time21_5") or rec.get("startTime", "")
            if not t_str:
                continue
            try:
                t = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if cutoff_lo <= t <= cutoff_hi:
                candidates.append(rec)

    if not candidates:
        return None

    return max(candidates, key=lambda r: float(r.get("speed") or 0))


def _compute_arrival(time21_5_str: str, speed_km_s: float) -> str:
    """Straight-line travel time from 21.5 R☉ to 1 AU."""
    try:
        t0 = datetime.fromisoformat(time21_5_str.replace("Z", "+00:00"))
    except ValueError:
        t0 = datetime.now(timezone.utc)
    distance_km = AU_KM - START_RADIUS_KM
    transit_sec = distance_km / max(speed_km_s, 100.0)
    return (t0 + timedelta(seconds=transit_sec)).isoformat()


def _classify_direction(lat: Optional[float], lon: Optional[float]) -> str:
    if lat is None or lon is None:
        return "unknown"
    return "earth_directed" if abs(lat) < 25 and abs(lon) < 30 else "off_limb"


def cme_to_fields(analysis: dict) -> dict:
    """
    Extract the CME physics fields that enter StormEvent.cme from a DONKI record.

    Returns:
      speed_km_s, angular_width_deg, direction, arrival_estimate, donki_id
    """
    speed_km_s       = float(analysis.get("speed") or 500.0)
    half_angle        = float(analysis.get("halfAngle") or 30.0)
    angular_width_deg = half_angle * 2.0
    lat               = analysis.get("latitude")
    lon               = analysis.get("longitude")
    direction         = _classify_direction(
        float(lat) if lat is not None else None,
        float(lon) if lon is not None else None,
    )
    time21_5 = analysis.get("time21_5") or analysis.get("startTime", "")
    arrival  = _compute_arrival(time21_5, speed_km_s) if time21_5 else ""
    donki_id = analysis.get("activityID", "")

    return {
        "speed_km_s":         round(speed_km_s, 1),
        "angular_width_deg":  round(angular_width_deg, 1),
        "direction":          direction,
        "arrival_estimate":   arrival,
        "donki_id":           donki_id,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    p = argparse.ArgumentParser(description="Prefetch DONKI CME analyses to cache")
    p.add_argument("--prefetch", action="store_true")
    p.add_argument("--storm", choices=list(STORM_DONKI_CONFIG))
    p.add_argument("--cache-dir", default="data/cached/donki")
    args = p.parse_args()

    if args.prefetch and args.storm:
        cfg = STORM_DONKI_CONFIG[args.storm]
        analyses = fetch_cme_analyses(cfg["start_date"], cfg["end_date"], args.cache_dir)
        best = select_best_cme(analyses, cfg["storm_date"])
        if best:
            fields = cme_to_fields(best)
            print(f"Best CME for {args.storm}:")
            for k, v in fields.items():
                print(f"  {k}: {v}")
        else:
            print(f"No matching CME found in {len(analyses)} records")


if __name__ == "__main__":
    main()
