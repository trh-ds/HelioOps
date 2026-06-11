"""
Deterministic verifier gate — pure Python, zero LLM calls.

Checks every operational number in an advisory against authoritative rulebooks
before dispatch. This is WOW #2 in the demo: the 21 MHz block.

Usage:
    from genai.verifier import verify_advisory
    verified, provenance = verify_advisory(advisory, storm_event, impact_assessment)

Verifier behavior:
  - "pass"    → value exists in authoritative source → keep
  - "blocked" → value invalid, nearest valid substitute found → correct + log
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from genai.contracts import (
    ProvenanceStep,
    ProvenanceTrace,
    VerifiedAdvisory,
    VerifierCheck,
    VerifierResult,
)
from genai.models import AdvisoryOutput


# ── Authoritative Rule Tables ────────────────────────────────────────────────

# ICAO NAT Doc 007 — valid HF frequencies for North Atlantic operations
ICAO_NAT_HF_BANDS_MHZ = {3, 5, 8, 11, 17}

# Rerouting latitude thresholds by G-scale
# G3+: below 78°N, G4+: below 70°N, G5: below 60°N
REROUTE_LAT_THRESHOLDS: dict[int, int] = {3: 78, 4: 70, 5: 60}

# NERC TPL-007-4 Appendix B — valid GIC operating steps
NERC_GIC_STEPS = {
    "operating procedure",
    "gmd operating procedure",
    "real-time assessment",
    "thermal monitoring",
    "reactive power monitoring",
    "load shedding",
    "transformer protection",
    "voltage reduction",
    "controlled separation",
}

# GMDSS valid distress/working frequencies (kHz)
GMDSS_VALID_FREQUENCIES_KHZ = {
    2182,     # MF distress
    4125,     # HF distress
    6215,     # HF distress
    8291,     # HF distress
    12290,    # HF distress
    16420,    # HF distress
    156800,   # VHF Ch.16 (156.8 MHz = 156800 kHz)
    2187.5,   # MF DSC
    8414.5,   # HF DSC
}

# Valid GMDSS channel names
GMDSS_VALID_CHANNELS = {
    "ch 16", "channel 16", "ch16",
    "2182 khz", "2187.5 khz",
    "4125 khz", "6215 khz", "8291 khz",
    "inmarsat", "inmarsat-c", "inmarsat-b",
    "navtex", "epirb", "sart",
    "dsc", "nbdp",
}


# ── HF Frequency Check ──────────────────────────────────────────────────────

def _check_hf_frequencies(action: str, g_scale: int) -> list[tuple[VerifierCheck, str]]:
    """Check HF frequencies mentioned in an action string against ICAO valid set."""
    checks: list[tuple[VerifierCheck, str]] = []

    # Match patterns like "21 MHz", "5MHz", "8 mhz"
    for match in re.finditer(r"(\d+)\s*MHz", action, re.IGNORECASE):
        freq = int(match.group(1))

        if freq in ICAO_NAT_HF_BANDS_MHZ:
            checks.append((
                VerifierCheck(field="hf_band", proposed=freq, status="pass"),
                action,
            ))
        else:
            # For G4+ storms, correct to 5 MHz (ICAO default backup band)
            # Otherwise, correct to nearest valid frequency
            if g_scale >= 4:
                corrected = 5
            else:
                corrected = min(ICAO_NAT_HF_BANDS_MHZ, key=lambda b: abs(b - freq))

            reason = f"{freq} MHz not in ICAO NAT valid set {sorted(ICAO_NAT_HF_BANDS_MHZ)}"
            corrected_action = action.replace(f"{freq} MHz", f"{corrected} MHz")
            corrected_action = corrected_action.replace(f"{freq}MHz", f"{corrected} MHz")

            checks.append((
                VerifierCheck(
                    field="hf_band",
                    proposed=freq,
                    status="blocked",
                    corrected_to=corrected,
                    reason=reason,
                ),
                corrected_action,
            ))

    return checks


# ── Rerouting Latitude Check ────────────────────────────────────────────────

def _check_reroute_latitude(action: str, g_scale: int) -> list[tuple[VerifierCheck, str]]:
    """Check rerouting latitude thresholds in action text."""
    checks: list[tuple[VerifierCheck, str]] = []
    threshold = REROUTE_LAT_THRESHOLDS.get(g_scale)

    if threshold is None:
        return checks

    # Match patterns like "70°N", "78 N", "70N"
    for match in re.finditer(r"(\d+)\s*°?\s*N", action):
        lat = int(match.group(1))
        # Ignore numbers that are clearly not latitudes (< 30 or > 90)
        if lat < 30 or lat > 90:
            continue

        if lat <= threshold:
            checks.append((
                VerifierCheck(field="reroute_latitude", proposed=lat, status="pass"),
                action,
            ))
        else:
            reason = (
                f"Reroute latitude {lat}°N exceeds G{g_scale} threshold of {threshold}°N. "
                f"ICAO requires routes below {threshold}°N for G{g_scale}+ storms."
            )
            corrected_action = action.replace(
                match.group(0), f"{threshold}°N"
            )
            checks.append((
                VerifierCheck(
                    field="reroute_latitude",
                    proposed=lat,
                    status="blocked",
                    corrected_to=threshold,
                    reason=reason,
                ),
                corrected_action,
            ))

    return checks


# ── GIC Operating Step Check ─────────────────────────────────────────────────

def _check_gic_steps(action: str) -> list[tuple[VerifierCheck, str]]:
    """Check that grid actions reference valid NERC GIC operating steps."""
    checks: list[tuple[VerifierCheck, str]] = []
    action_lower = action.lower()

    # Check if the action references any known NERC step
    for step in NERC_GIC_STEPS:
        if step in action_lower:
            checks.append((
                VerifierCheck(field="gic_step", proposed=step, status="pass"),
                action,
            ))
            return checks  # found a valid step

    # No valid step referenced — not necessarily blocked, just no check
    return checks


# ── GMDSS Channel Check ─────────────────────────────────────────────────────

def _check_gmdss_channels(action: str) -> list[tuple[VerifierCheck, str]]:
    """Check that maritime actions reference valid GMDSS channels/frequencies."""
    checks: list[tuple[VerifierCheck, str]] = []
    action_lower = action.lower()

    for channel in GMDSS_VALID_CHANNELS:
        if channel in action_lower:
            checks.append((
                VerifierCheck(field="gmdss_channel", proposed=channel, status="pass"),
                action,
            ))

    return checks


# ── Main Verifier Entry Point ────────────────────────────────────────────────

def verify_advisory(
    advisory: AdvisoryOutput,
    storm_event: dict,
    impact_assessment: dict | None = None,
) -> tuple[VerifiedAdvisory, ProvenanceTrace]:
    """
    Run all applicable rule checks on an advisory and produce
    VerifiedAdvisory + ProvenanceTrace.

    Args:
        advisory:           AdvisoryOutput from an industry agent
        storm_event:        Full StormEvent dict
        impact_assessment:  Optional ImpactAssessment dict from Neal

    Returns:
        (VerifiedAdvisory, ProvenanceTrace) — ready for Tirth's Layer ④
    """
    g_scale = storm_event.get("scales", {}).get("G", 0)
    # Fallback: parse from g_scale string like "G4"
    if g_scale == 0:
        g_str = storm_event.get("g_scale", "")
        if isinstance(g_str, str) and g_str.startswith("G"):
            g_scale = int(g_str[1:])

    industry = advisory.industry.value if hasattr(advisory.industry, "value") else str(advisory.industry)
    all_checks: list[VerifierCheck] = []
    corrected_actions: list[str] = []

    # Process each action through applicable rule checks
    for item in advisory.action_items:
        action_text = item.action
        action_checks: list[VerifierCheck] = []

        if industry in ("aviation", "maritime"):
            hf_results = _check_hf_frequencies(action_text, g_scale)
            for check, corrected in hf_results:
                action_checks.append(check)
                action_text = corrected

        if industry == "aviation":
            lat_results = _check_reroute_latitude(action_text, g_scale)
            for check, corrected in lat_results:
                action_checks.append(check)
                action_text = corrected

        if industry == "grid":
            gic_results = _check_gic_steps(action_text)
            for check, _ in gic_results:
                action_checks.append(check)

        if industry == "maritime":
            gmdss_results = _check_gmdss_channels(action_text)
            for check, _ in gmdss_results:
                action_checks.append(check)

        all_checks.extend(action_checks)
        corrected_actions.append(action_text)

    # Determine overall verifier status
    has_blocked = any(c.status == "blocked" for c in all_checks)
    if not all_checks:
        status = "passed"
    elif has_blocked:
        status = "passed_with_corrections"
    else:
        status = "passed"

    verifier_result = VerifierResult(status=status, checks=all_checks)

    # Build advisory ID and provenance refs
    advisory_id = f"adv_{storm_event.get('storm_id', 'unknown')}_{industry}_{uuid.uuid4().hex[:8]}"
    trace_id = f"trace_{advisory_id}"

    # Determine timing window from storm data
    timeline = storm_event.get("timeline", [])
    onset_entry = next((t for t in timeline if t.get("horizon") == "onset"), None)
    timing_window = {
        "opens": onset_entry["t"] if onset_entry else datetime.now(timezone.utc).isoformat(),
        "duration_min": 50,  # default estimate
    }

    # Extract cited procedure from advisory
    sources = advisory.sources_cited if advisory.sources_cited else []
    cited_procedure = {
        "source": sources[0] if sources else "UNKNOWN",
        "ref": advisory.action_items[0].source_ref if advisory.action_items else "N/A",
    }

    # Build technical details
    technical_details = advisory.summary

    # Determine if human review needed
    requires_human = (
        has_blocked
        or advisory.confidence_score < 0.5
        or any(f.value == "GENERATION_FAILED" for f in advisory.safety_flags)
    )

    verified = VerifiedAdvisory(
        advisory_id=advisory_id,
        storm_id=storm_event.get("storm_id", "unknown"),
        industry=industry,
        severity=advisory.severity.value.lower(),
        numbered_actions=corrected_actions,
        timing_window=timing_window,
        technical_details=technical_details,
        cited_procedure=cited_procedure,
        verifier=verifier_result,
        provenance_ref=trace_id,
        requires_human=requires_human,
    )

    # Build provenance trace — 6-step chain
    provenance = ProvenanceTrace(
        trace_id=trace_id,
        advisory_id=advisory_id,
        chain=[
            ProvenanceStep(
                step="raw_data",
                ref=storm_event.get("noaa_alert_raw", "NOAA SWPC alert"),
            ),
            ProvenanceStep(
                step="detection",
                ref=f"StormEvent:{storm_event.get('storm_id', 'unknown')}",
                confidence=storm_event.get("confidence"),
            ),
            ProvenanceStep(
                step="impact",
                ref=f"ImpactAssessment:{storm_event.get('storm_id', 'unknown')}",
                ci_level=0.95 if impact_assessment else None,
            ),
            ProvenanceStep(
                step="retrieval",
                ref=f"{cited_procedure['source']} :: {cited_procedure['ref']}",
            ),
            ProvenanceStep(
                step="verifier",
                ref=_verifier_summary(all_checks),
            ),
            ProvenanceStep(
                step="output",
                ref=f"VerifiedAdvisory:{advisory_id}",
            ),
        ],
    )

    return verified, provenance


def _verifier_summary(checks: list[VerifierCheck]) -> str:
    """One-line summary of verifier results for provenance."""
    if not checks:
        return "no verifiable values found"

    blocked = [c for c in checks if c.status == "blocked"]
    passed = [c for c in checks if c.status == "pass"]

    parts = []
    if passed:
        parts.append(f"{len(passed)} passed")
    if blocked:
        corrections = [f"{c.proposed} -> {c.corrected_to}" for c in blocked]
        parts.append(f"{len(blocked)} blocked ({', '.join(corrections)})")

    return "; ".join(parts)


# ── Stream event helpers ─────────────────────────────────────────────────────

def verifier_stream_events(checks: list[VerifierCheck], industry: str) -> list[dict]:
    """Generate WebSocket stream events for each verifier check."""
    events = []
    for check in checks:
        event = {
            "event": "verifier.check",
            "industry": industry,
            "field": check.field,
            "proposed": check.proposed,
            "status": check.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if check.status == "blocked":
            event["corrected_to"] = check.corrected_to
            event["reason"] = check.reason
        events.append(event)
    return events
