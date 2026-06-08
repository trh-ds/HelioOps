"""
Deterministic G-scale → industry severity routing matrix.

No LLM is involved here. This is the authoritative source for which industries
are impacted at each storm level. Matches the NOAA space weather scales data
stored in data/impact_matrix/noaa_space_weather_scales.txt.

Reference:
  - G1 (Kp=5):  Minor geomagnetic storm
  - G2 (Kp=6):  Moderate
  - G3 (Kp=7):  Strong
  - G4 (Kp=8):  Severe
  - G5 (Kp=9+): Extreme
"""

from __future__ import annotations

from genai.models import GScale, Industry, IndustryImpact, SeverityTier, StormEvent

# ── Impact Matrix ─────────────────────────────────────────────────────────────
# Source: NOAA Space Weather Scales + NESDIS industry impact briefings
# Format: {g_scale: {industry: severity_tier}}

_MATRIX: dict[str, dict[str, str]] = {
    "G1": {
        "aviation": "LOW",
        "grid":     "LOW",
        "maritime": "NONE",
        "telecom":  "NONE",
    },
    "G2": {
        "aviation": "MEDIUM",
        "grid":     "MEDIUM",
        "maritime": "LOW",
        "telecom":  "LOW",
    },
    "G3": {
        "aviation": "HIGH",
        "grid":     "HIGH",
        "maritime": "MEDIUM",
        "telecom":  "MEDIUM",
    },
    "G4": {
        "aviation": "CRITICAL",
        "grid":     "CRITICAL",
        "maritime": "HIGH",
        "telecom":  "HIGH",
    },
    "G5": {
        "aviation": "CRITICAL",
        "grid":     "CRITICAL",
        "maritime": "CRITICAL",
        "telecom":  "CRITICAL",
    },
}

# Industries that generate an advisory only at or above these tiers
_TRIGGER_TIERS: set[str] = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def route_storm(storm: StormEvent) -> list[IndustryImpact]:
    """
    Map a StormEvent to a list of IndustryImpact objects.

    Returns all four industries; `triggered=False` means no advisory needed.
    The genai graph filters to triggered=True before spawning agents.
    """
    row = _MATRIX.get(storm.g_scale.value, {})
    impacts: list[IndustryImpact] = []

    for industry in Industry:
        severity_str = row.get(industry.value, "NONE")
        severity = SeverityTier(severity_str)
        impacts.append(IndustryImpact(
            industry=industry,
            severity=severity,
            triggered=severity_str in _TRIGGER_TIERS,
        ))

    return impacts


def get_minimum_severity(industry: Industry, g_scale: GScale) -> SeverityTier:
    """
    Return the authoritative minimum severity for a given industry + G-scale.
    Used by guardrails to detect if the LLM under-reported severity.
    """
    severity_str = _MATRIX.get(g_scale.value, {}).get(industry.value, "NONE")
    return SeverityTier(severity_str)
