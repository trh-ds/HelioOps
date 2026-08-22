"""
Tests for the deterministic verifier gate.

verifier.py had no tests at all. It is the last thing between a generated
advisory and an operator, it can **rewrite** an instruction, and every rule
table in it is a hand-written constant. A wrong constant or a broken correction
path silently turns good advice into bad advice, which is the one failure this
layer exists to prevent.

Scope: these tests check that the rules are *applied* correctly. They
deliberately do not assert that the published values themselves are right —
that is a domain question, and the tables are taken from the published
standards as-is.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.genai.models import ActionItem, AdvisoryOutput, Industry, SeverityTier
from backend.genai.verifier import (
    GMDSS_VALID_FREQUENCIES_KHZ,
    ICAO_NAT_HF_BANDS_MHZ,
    REROUTE_LAT_THRESHOLDS,
    _check_gic_steps,
    _check_gmdss_channels,
    _check_hf_frequencies,
    _check_reroute_latitude,
    verify_advisory,
)


def _advisory(industry: str, actions: list[str], severity: str = "CRITICAL"):
    return AdvisoryOutput(
        advisory_id="a-1",
        storm_event_id="2024-05-G5",
        industry=Industry(industry),
        severity=SeverityTier(severity),
        confidence_score=0.9,
        summary="Test advisory for verifier coverage.",
        action_items=[
            ActionItem(
                step=i + 1,
                action=a,
                rationale="Rationale long enough to satisfy the schema.",
                source_ref="nat_doc_007_2025.pdf",
                time_window="T+0 immediately",
            )
            for i, a in enumerate(actions)
        ],
        sources_cited=["nat_doc_007_2025.pdf"],
        validation_passed=True,
        generated_at=datetime.now(timezone.utc),
        model_used="test",
    )


def _storm(g: int = 5):
    return {"storm_id": "2024-05-G5", "scales": {"G": g}, "timeline": []}


# ── HF frequency rule ────────────────────────────────────────────────────────

@pytest.mark.parametrize("freq", sorted(ICAO_NAT_HF_BANDS_MHZ))
def test_valid_icao_hf_bands_pass(freq):
    checks = _check_hf_frequencies(f"Switch HF to {freq} MHz.", g_scale=4)
    assert [c.status for c, _ in checks] == ["pass"]


def test_invalid_hf_band_is_blocked_and_corrected():
    """The demo case: 21 MHz is not an ICAO NAT band."""
    checks = _check_hf_frequencies("Switch HF to 21 MHz.", g_scale=4)
    assert len(checks) == 1
    check, corrected = checks[0]
    assert check.status == "blocked"
    assert check.proposed == 21
    assert check.corrected_to in ICAO_NAT_HF_BANDS_MHZ
    assert "21 MHz" not in corrected
    assert f"{check.corrected_to} MHz" in corrected


def test_hf_correction_is_cumulative_across_multiple_bad_values():
    """
    Corrections used to each be computed from the original text while
    verify_advisory kept only the last one, so an action naming two invalid
    frequencies shipped with the first bad value still in it.
    """
    checks = _check_hf_frequencies("Try 21 MHz then fall back to 25 MHz.", g_scale=4)
    assert len(checks) == 2
    _, final = checks[-1]
    assert "21 MHz" not in final, f"first correction was lost: {final!r}"
    assert "25 MHz" not in final, f"second correction was lost: {final!r}"


def test_hf_check_is_case_insensitive_and_handles_missing_space():
    assert _check_hf_frequencies("use 8mhz now", g_scale=3)[0][0].status == "pass"


def test_hf_check_ignores_actions_with_no_frequency():
    assert _check_hf_frequencies("Brief the crew before departure.", g_scale=5) == []


# ── Reroute latitude rule ────────────────────────────────────────────────────

@pytest.mark.parametrize("g_scale,threshold", sorted(REROUTE_LAT_THRESHOLDS.items()))
def test_latitude_at_the_threshold_passes(g_scale, threshold):
    checks = _check_reroute_latitude(f"Reroute below {threshold}°N.", g_scale)
    assert [c.status for c, _ in checks] == ["pass"]


def test_latitude_above_threshold_is_blocked_and_corrected():
    checks = _check_reroute_latitude("Divert flights north of 78°N.", g_scale=5)
    check, corrected = checks[0]
    assert check.status == "blocked"
    assert check.corrected_to == REROUTE_LAT_THRESHOLDS[5]
    assert "78" not in corrected


def test_latitude_rule_is_stricter_as_the_storm_worsens():
    """G3 allows 78N; the same text must be blocked at G5."""
    assert _check_reroute_latitude("route below 78°N", 3)[0][0].status == "pass"
    assert _check_reroute_latitude("route below 78°N", 5)[0][0].status == "blocked"


def test_non_latitude_numbers_are_ignored():
    """Guarded to 30-90 so counts and identifiers are not read as latitudes."""
    assert _check_reroute_latitude("Notify 12 N-registered carriers.", g_scale=5) == []


def test_unknown_g_scale_produces_no_latitude_checks():
    assert _check_reroute_latitude("route below 78°N", g_scale=1) == []


# ── GMDSS rules ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("freq", sorted(GMDSS_VALID_FREQUENCIES_KHZ))
def test_valid_gmdss_frequencies_pass(freq):
    freq_str = f"{freq:g}"
    checks = _check_gmdss_channels(f"Guard the distress watch on {freq_str} kHz.")
    statuses = [c.status for c, _ in checks if c.field == "gmdss_frequency"]
    assert statuses == ["pass"], f"{freq_str} kHz should be recognised"


def test_invalid_gmdss_frequency_is_blocked_and_corrected():
    """
    GMDSS_VALID_FREQUENCIES_KHZ was declared and never read, so a distress
    frequency that does not exist produced no check at all and the advisory
    came back "passed".
    """
    checks = _check_gmdss_channels("Maintain distress watch on 9999 kHz.")
    blocked = [(c, t) for c, t in checks if c.status == "blocked"]
    assert blocked, "an invalid distress frequency must be blocked"
    check, corrected = blocked[0]
    assert check.field == "gmdss_frequency"
    assert check.corrected_to in GMDSS_VALID_FREQUENCIES_KHZ
    assert "9999" not in corrected


def test_named_gmdss_channels_are_recognised():
    checks = _check_gmdss_channels("Switch to NAVTEX and monitor Ch 16.")
    fields = {c.field for c, _ in checks}
    assert "gmdss_channel" in fields


# ── GIC rule ─────────────────────────────────────────────────────────────────

def test_recognised_nerc_step_passes():
    checks = _check_gic_steps("Initiate the GMD operating procedure immediately.")
    assert [c.status for c, _ in checks] == ["pass"]


def test_unrecognised_grid_action_produces_no_check():
    """
    Documents current behaviour, which is weaker than it looks: the GIC rule
    can only ever confirm, never block. An action referencing no NERC step at
    all is silently unverified. See IMPROVEMENTS.md.
    """
    assert _check_gic_steps("Do something clever with the transformers.") == []


# ── End to end ───────────────────────────────────────────────────────────────

def test_clean_aviation_advisory_passes():
    advisory = _advisory("aviation", ["Switch HF to 5 MHz and reroute below 60°N."])
    verified, trace = verify_advisory(advisory, _storm(5))
    assert verified.verifier.status == "passed"
    assert trace.trace_id


def test_bad_values_are_corrected_in_the_dispatched_actions():
    advisory = _advisory("aviation", ["Switch HF to 21 MHz and divert north of 78°N."])
    verified, _ = verify_advisory(advisory, _storm(5))
    assert verified.verifier.status == "passed_with_corrections"
    dispatched = " ".join(verified.numbered_actions)
    assert "21 MHz" not in dispatched
    assert "78" not in dispatched


def test_telecom_reports_not_applicable_rather_than_passed():
    """
    No rule set covers telecom. Reporting "passed" claimed a verification that
    never happened; the status must say so.
    """
    advisory = _advisory("telecom", ["Switch timing reference to internal holdover."])
    verified, _ = verify_advisory(advisory, _storm(5))
    assert verified.verifier.status == "not_applicable"
    assert verified.verifier.checks == []


def test_blocked_advisory_requires_human_review():
    advisory = _advisory("aviation", ["Switch HF to 21 MHz."])
    verified, _ = verify_advisory(advisory, _storm(5))
    assert verified.requires_human is True


def test_provenance_trace_is_linked_to_the_advisory():
    advisory = _advisory("maritime", ["Maintain distress watch on 2182 kHz."])
    verified, trace = verify_advisory(advisory, _storm(4))
    assert verified.provenance_ref == trace.trace_id


# ── Severity floor enforcement ───────────────────────────────────────────────

def test_severity_floor_is_enforced_not_just_flagged(monkeypatch):
    """
    The agent used to flag SEVERITY_MISMATCH and publish the model's lower
    value, so a G5 storm could reach an operator labelled MEDIUM. The G-scale
    matrix comes from the NOAA scales, not from a language model, so the model
    is simply wrong when it reads below the floor — and a flag buried in a
    safety_flags list is not a substitute for the severity field being right.
    """
    import asyncio
    import json

    from backend.genai.agents import aviation
    from backend.genai.models import RetrievedChunk, SafetyFlag

    under_reported = {
        "storm_event_id": "2024-05-G5",
        "industry": "aviation",
        "severity": "MEDIUM",  # matrix floor for a G5 is CRITICAL
        "summary": "Storm affects HF communications across the North Atlantic.",
        "action_items": [
            {
                "step": i,
                "action": f"Take documented mitigation step number {i} now.",
                "rationale": "Grounded in the retrieved procedure text.",
                "source_ref": "nat_doc_007_2025.pdf",
                "time_window": "T+0 immediately",
            }
            for i in (1, 2, 3)
        ],
        "estimated_impact_window": "PT6H",
        "sources_cited": ["nat_doc_007_2025.pdf"],
    }

    chunk = RetrievedChunk(
        chunk_id="c1", text="HF procedure text.", source="nat_doc_007_2025.pdf",
        similarity=0.8, metadata={},
    )

    monkeypatch.setattr(
        "backend.genai.agents.base.retrieve_chunks", lambda *a, **k: [chunk]
    )

    async def fake_complete(system, user, **kw):
        return json.dumps(under_reported)

    monkeypatch.setattr("backend.genai.agents.base.complete_json", fake_complete)
    monkeypatch.setattr("backend.genai.agents.base.SELF_CHECK_ENABLED", False)

    from backend.genai.models import GScale, StormEvent

    storm = StormEvent(
        alert_id="2024-05-G5", g_scale=GScale("G5"), kp_index=9.0,
        raw_alert_text="G5 extreme geomagnetic storm in progress.",
    )

    result = asyncio.run(aviation.AviationAgent().run_async(storm, "CRITICAL"))
    advisory = result["advisory"]

    assert advisory.severity == SeverityTier.CRITICAL, (
        f"severity must be raised to the matrix floor, got {advisory.severity}"
    )
    assert SafetyFlag.SEVERITY_MISMATCH in advisory.safety_flags, (
        "the disagreement must still be visible"
    )
    assert any("MEDIUM" in e for e in advisory.generation_errors), (
        "the original model value must be recorded"
    )


class TestPageSuffix:
    """Citations now carry a page (`file.pdf p.42`) because retrieved chunks
    advertise one. If the matcher does not tolerate that, EVERY advisory gains
    a CITATION_GAP flag and loses confidence through CITATION_PENALTY - a
    silent, total regression. These pin the tolerance."""

    def test_exact_name_with_page_matches(self):
        from backend.genai.guardrails import citation_matches

        assert citation_matches("x.pdf p.4", "x.pdf")

    def test_page_forms_all_match(self):
        from backend.genai.guardrails import citation_matches

        for ref in (
            "nat_doc_007_2025.pdf p.42",
            "nat_doc_007_2025.pdf p. 42",
            "nat_doc_007_2025.pdf pp.10-12",
            "nat_doc_007_2025.pdf page 7",
            "nat_doc_007_2025.pdf, p.42",
        ):
            assert citation_matches(ref, "nat_doc_007_2025.pdf"), ref

    def test_page_suffix_does_not_make_wrong_doc_match(self):
        from backend.genai.guardrails import citation_matches

        assert not citation_matches("NERC TPL-999-9 p.4", "nerc_tpl007_4.pdf")

    def test_itu_designator_is_not_a_page(self):
        """ITU recommendations are named "P.618" / "P.531" / "M.493". A naive
        trailing-page pattern reads that as page 618 and mangles the ref down to
        "ITU-R", which stops it resolving to itu_r_p618_*.pdf."""
        from backend.genai.guardrails import citation_matches, strip_page_suffix

        assert strip_page_suffix("ITU-R P.618") == "ITU-R P.618"
        assert strip_page_suffix("ITU-R M.493") == "ITU-R M.493"
        assert citation_matches("ITU-R P.618", "itu_r_p618_earth_space_propagation.pdf")

    def test_strip_leaves_plain_refs_alone(self):
        from backend.genai.guardrails import strip_page_suffix

        assert strip_page_suffix("nat_doc_007_2025.pdf") == "nat_doc_007_2025.pdf"
        # A version number is not a page locator and must survive.
        assert strip_page_suffix("ICAO NAT Doc 007") == "ICAO NAT Doc 007"

    def test_grounded_against_retrieved_chunk_with_page(self):
        from backend.genai.guardrails import citation_is_grounded
        from backend.genai.models import RetrievedChunk

        chunk = RetrievedChunk(
            chunk_id="c1",
            text="...",
            source="nat_doc_007_2025.pdf",
            similarity=0.8,
            metadata={"page": 42},
        )
        assert citation_is_grounded("nat_doc_007_2025.pdf p.42", [chunk])
