"""
SchemaAdapter — bridges cv.fusion.StormEvent → genai.models.StormEvent.

This is the Anti-Corruption Layer between the CV and GenAI bounded contexts.
Both use StormEvent but with incompatible field sets; this adapter translates.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.logging import get_logger

log = get_logger("backend.adapters.schema")

_G_TO_KP: dict[int, float] = {0: 0.0, 1: 5.0, 2: 6.0, 3: 7.0, 4: 8.3, 5: 9.0}


def _parse_kp_from_alert(alert_text: str) -> Optional[float]:
    match = re.search(r"[Kk][Pp]\s*[=:]?\s*([\d.]+)", alert_text)
    if match:
        kp = float(match.group(1))
        if 0.0 <= kp <= 9.0:
            return kp
    return None


def _safe_datetime(iso_str: str) -> Optional[datetime]:
    if not iso_str or not iso_str.strip():
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def adapt_storm_event(cv_event) -> Any:
    from genai.models import GScale, StormEvent as GenaiStormEvent

    scales = cv_event.scales
    g_int = int(scales.get("G", 0))
    g_clamped = max(1, min(5, g_int)) if g_int > 0 else 1
    g_scale = GScale(f"G{g_clamped}")

    s_int = int(scales.get("S", 0))
    r_int = int(scales.get("R", 0))
    s_scale = f"S{s_int}" if s_int > 0 else None
    r_scale = f"R{r_int}" if r_int > 0 else None

    kp = _parse_kp_from_alert(cv_event.noaa_alert_raw)
    if kp is None:
        kp = _G_TO_KP.get(g_int, _G_TO_KP.get(g_clamped, 5.0))

    arrival = _safe_datetime(cv_event.cme.get("arrival_estimate", ""))
    onset_entry = next(
        (t for t in cv_event.timeline if t.get("horizon") == "onset"),
        None,
    )
    peak_start = _safe_datetime(onset_entry["t"]) if onset_entry else arrival
    peak_end = peak_start + timedelta(hours=6) if peak_start else None

    raw_text = cv_event.noaa_alert_raw
    if not raw_text.strip():
        raw_text = (
            f"G{g_clamped} geomagnetic storm detected. "
            f"CME speed {cv_event.cme.get('speed_km_s', 'unknown')} km/s. "
            f"Confidence {cv_event.confidence:.2f}."
        )

    log.info("schema_adapted", storm_id=cv_event.storm_id, g_scale=g_scale.value, kp=kp)

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