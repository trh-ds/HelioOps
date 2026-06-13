"""
backend/adapter.py — Bridge cv.fusion.StormEvent → genai.models.StormEvent.

These two classes share the same name but have incompatible field sets.
This adapter translates the raw sensor-fusion output into the alert-based
schema the GenAI advisory agents expect.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from cv.fusion import StormEvent as CvStormEvent
from genai.models import GScale, StormEvent as GenaiStormEvent

# G-scale int → Kp index (NOAA Space Weather Scales)
_G_TO_KP: dict[int, float] = {0: 0.0, 1: 5.0, 2: 6.0, 3: 7.0, 4: 8.3, 5: 9.0}


def _parse_kp_from_alert(alert_text: str) -> Optional[float]:
    """Try to extract Kp value from raw NOAA alert text."""
    match = re.search(r"[Kk][Pp]\s*[=:]?\s*([\d.]+)", alert_text)
    if match:
        kp = float(match.group(1))
        if 0.0 <= kp <= 9.0:
            return kp
    return None


def _safe_datetime(iso_str: str) -> Optional[datetime]:
    """Parse ISO 8601 string, return None on failure or empty string."""
    if not iso_str or not iso_str.strip():
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def adapt_storm_event(cv_event: CvStormEvent) -> GenaiStormEvent:
    """
    Convert cv.fusion.StormEvent → genai.models.StormEvent.

    Handles:
      - G-scale int → GScale enum (clamped to [1,5])
      - S/R scale int → "S1"/"R1" string or None
      - Kp index from alert text or G-scale lookup
      - Arrival estimate → datetime or None
      - Onset timeline entry → peak impact window
    """
    scales = cv_event.scales
    g_int = int(scales.get("G", 0))
    g_clamped = max(1, min(5, g_int)) if g_int > 0 else 1
    g_scale = GScale(f"G{g_clamped}")

    s_int = int(scales.get("S", 0))
    r_int = int(scales.get("R", 0))
    s_scale = f"S{s_int}" if s_int > 0 else None
    r_scale = f"R{r_int}" if r_int > 0 else None

    # Kp: try parsing from alert text first, fall back to G-scale map
    kp = _parse_kp_from_alert(cv_event.noaa_alert_raw)
    if kp is None:
        kp = _G_TO_KP.get(g_int, _G_TO_KP.get(g_clamped, 5.0))

    # Arrival estimate
    arrival = _safe_datetime(cv_event.cme.get("arrival_estimate", ""))

    # Peak impact window from onset timeline entry
    onset_entry = next(
        (t for t in cv_event.timeline if t.get("horizon") == "onset"),
        None,
    )
    peak_start = _safe_datetime(onset_entry["t"]) if onset_entry else arrival
    peak_end = peak_start + timedelta(hours=6) if peak_start else None

    # Build raw alert text — enrich with storm data if original is sparse
    raw_text = cv_event.noaa_alert_raw
    if not raw_text.strip():
        raw_text = (
            f"G{g_clamped} geomagnetic storm detected. "
            f"CME speed {cv_event.cme.get('speed_km_s', 'unknown')} km/s. "
            f"Confidence {cv_event.confidence:.2f}."
        )

    return GenaiStormEvent(
        alert_id=cv_event.storm_id,
        g_scale=g_scale,
        s_scale=s_scale,
        r_scale=r_scale,
        kp_index=kp,
        estimated_arrival_utc=arrival,
        peak_impact_window_start=peak_start,
        peak_impact_window_end=peak_end,
        raw_alert_text=raw_text,
        source_url=None,
    )
