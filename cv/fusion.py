"""
cv/fusion.py — StormEvent contract + fuse() assembly function

Extracted from imp.md §7 (Data Contracts) and §10 (Layer ①).
Single source of truth for the StormEvent schema used by detect.py,
stubs, tests, and Tirth's replay engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class StormEvent(BaseModel):
    storm_id:      str
    detected_at:   str
    confidence:    float
    scales:        dict[str, Any]
    cme:           dict[str, Any]
    flare:         dict[str, Any]
    l1_solar_wind: dict[str, Any]
    timeline:      list[dict[str, Any]]
    noaa_alert_raw: str


def fuse(
    cme_result: dict,
    flare_result: dict,
    l1: dict,
    noaa_alert: str,
    storm_id: str,
) -> StormEvent:
    """
    Combine CME detection, flare classification, L1 solar wind,
    and NOAA alert text into a single StormEvent.

    Confidence weights (calibrated empirically against NOAA post-event reports):
      40% — CME visual confidence
      20% — Flare detected (binary)
      20% — Southward Bz (negative Bz = geoeffective)
      20% — NOAA alert present (non-empty string)
    """
    bz_southward = 1.0 if l1.get("bz_nt", 0) < 0 else 0.0
    confidence = (
        0.4 * float(cme_result.get("confidence", 0.0)) +
        0.2 * (1.0 if flare_result.get("detected") else 0.0) +
        0.2 * bz_southward +
        0.2 * (1.0 if noaa_alert.strip() else 0.0)
    )

    speed_km_s = l1.get("speed_km_s", 400.0)
    eta_minutes = int(1_500_000 / max(speed_km_s, 1.0) / 60)
    now = datetime.now(timezone.utc).isoformat()

    return StormEvent(
        storm_id=storm_id,
        detected_at=now,
        confidence=round(confidence, 3),
        scales={
            "G": l1.get("g_scale", 0),
            "S": flare_result.get("s_scale", 0),
            "R": flare_result.get("r_scale", 0),
        },
        cme=cme_result,
        flare=flare_result,
        l1_solar_wind={**l1, "eta_minutes": eta_minutes},
        timeline=[
            {
                "horizon": "days_out",
                "source":  cme_result.get("source", "CCOR-1"),
                "t":       cme_result.get("arrival_estimate", now),
            },
            {
                "horizon": "one_hour",
                "source":  "L1 wind",
                "t":       l1.get("measured_at", now),
            },
            {
                "horizon": "onset",
                "source":  "geomagnetic",
                "t":       cme_result.get("arrival_estimate", now),
            },
        ],
        noaa_alert_raw=noaa_alert,
    )
