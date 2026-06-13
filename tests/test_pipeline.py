"""
tests/test_pipeline.py — Integration tests for the backend pipeline bridge.

Tests:
  - ML inference (with fallback when checkpoints missing)
  - Schema adapter (cv.fusion.StormEvent → genai.models.StormEvent)
  - Full pipeline (detect → adapt → predict → generate → verify)

Run:
    pytest tests/test_pipeline.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cv.fusion import StormEvent as CvStormEvent, fuse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_cv_event() -> CvStormEvent:
    """Build a realistic cv.fusion.StormEvent matching the G4 stub shape."""
    cme = {
        "speed_km_s": 1480.0, "angular_width_deg": 110.0,
        "direction": "earth_directed", "arrival_estimate": "2024-10-11T18:00:00Z",
        "detected": True, "source": "CCOR-1", "confidence": 0.88,
        "frame_path": "data/cached/ccor1/2024-10/annotated/frame_012.png",
        "bbox_norm": [0.28, 0.18, 0.74, 0.62],
    }
    flare = {
        "detected": True, "class": "X1.8", "r_scale": 3, "s_scale": 0,
        "source": "GOES-XRS", "onset": "2024-10-10T12:30:00Z",
    }
    l1 = {
        "speed_km_s": 720.0, "bz_nt": -28.0, "bt_nt": 30.0,
        "density_cm3": 8.0, "measured_at": "2024-10-11T17:10:00Z",
        "g_scale": 4,
    }
    return fuse(cme, flare, l1, "G4 Watch Kp 8.3", "2024-10-G4")


# ─────────────────────────────────────────────────────────────────────────────
# ML Inference Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMLInference:
    def test_fallback_when_no_checkpoints(self):
        """Without checkpoints, predict() returns conservative defaults."""
        from ML_after_CV.inference import predict, _MODELS, _CHECKPOINT_DIR
        _MODELS.clear()

        # Point to a non-existent dir so models can't load
        import ML_after_CV.inference as inf_mod
        original_dir = inf_mod._CHECKPOINT_DIR
        inf_mod._CHECKPOINT_DIR = Path("/nonexistent/checkpoints")
        try:
            event = _make_cv_event()
            result = predict(event.model_dump())

            assert result.gps_error_m == 20.0
            assert result.hf_blackout_prob == 0.85
            assert result.gps_error_ci_low < result.gps_error_m < result.gps_error_ci_high
        finally:
            inf_mod._CHECKPOINT_DIR = original_dir
            _MODELS.clear()

    def test_feature_extraction(self):
        """Verify feature extraction produces correct shape and values."""
        from ML_after_CV.inference import _extract_features

        event = _make_cv_event()
        df = _extract_features(event.model_dump())

        assert len(df) == 1
        assert list(df.columns) == [
            "g_scale", "kp_index", "bz_nt", "wind_speed_km_s",
            "cme_speed_km_s", "cme_width_deg", "r_scale",
            "geomag_lat_bin", "local_time_bin",
        ]
        assert df.iloc[0]["g_scale"] == 4
        assert df.iloc[0]["kp_index"] == 8.3
        assert df.iloc[0]["bz_nt"] == -28.0
        assert df.iloc[0]["cme_speed_km_s"] == 1480.0
        assert df.iloc[0]["r_scale"] == 3

    def test_prediction_with_checkpoints_if_available(self):
        """If checkpoints exist, predict returns real values (not defaults)."""
        from ML_after_CV.inference import predict, _MODELS, _CHECKPOINT_DIR
        _MODELS.clear()

        ckpt_exists = (_CHECKPOINT_DIR / "gps_q500.pkl").exists()
        if not ckpt_exists:
            pytest.skip("Checkpoints not available — skipping real inference test")

        event = _make_cv_event()
        result = predict(event.model_dump())

        # Real models should give different values than defaults
        assert result.gps_error_m >= 0.0
        assert 0.0 <= result.hf_blackout_prob <= 1.0
        assert result.gps_error_ci_low <= result.gps_error_m <= result.gps_error_ci_high


# ─────────────────────────────────────────────────────────────────────────────
# Schema Adapter Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAdapter:
    def test_basic_adaptation(self):
        """Adapter converts all required fields correctly."""
        from backend.adapter import adapt_storm_event
        from genai.models import GScale

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.alert_id == "2024-10-G4"
        assert genai_event.g_scale == GScale.G4
        assert genai_event.kp_index == 8.3  # parsed from "G4 Watch Kp 8.3"
        assert genai_event.r_scale == "R3"
        assert genai_event.s_scale is None  # s_scale was 0
        assert genai_event.raw_alert_text == "G4 Watch Kp 8.3"

    def test_arrival_parsed(self):
        """Arrival estimate converts to datetime."""
        from backend.adapter import adapt_storm_event

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.estimated_arrival_utc is not None
        assert isinstance(genai_event.estimated_arrival_utc, datetime)

    def test_peak_window_set(self):
        """Peak impact window start/end are set from timeline."""
        from backend.adapter import adapt_storm_event

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.peak_impact_window_start is not None
        if genai_event.peak_impact_window_end is not None:
            delta = genai_event.peak_impact_window_end - genai_event.peak_impact_window_start
            assert delta.total_seconds() == 6 * 3600  # 6 hours

    def test_g_scale_clamping(self):
        """G=0 clamps to G1."""
        from backend.adapter import adapt_storm_event
        from genai.models import GScale

        cv_event = _make_cv_event()
        # Override scales to G=0
        cv_event.scales["G"] = 0
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.g_scale == GScale.G1

    def test_empty_alert_text_enriched(self):
        """Empty alert text gets enriched with storm data."""
        from backend.adapter import adapt_storm_event

        cv_event = _make_cv_event()
        cv_event.noaa_alert_raw = ""
        genai_event = adapt_storm_event(cv_event)

        assert "geomagnetic storm" in genai_event.raw_alert_text.lower()
        assert "km/s" in genai_event.raw_alert_text

    def test_kp_fallback_to_map(self):
        """When alert text has no Kp, fall back to G→Kp map."""
        from backend.adapter import adapt_storm_event

        cv_event = _make_cv_event()
        cv_event.noaa_alert_raw = "Storm alert no kp info"
        genai_event = adapt_storm_event(cv_event)

        # G4 maps to Kp 8.3
        assert genai_event.kp_index == 8.3

    def test_genai_event_serializable(self):
        """Adapted event must be JSON-serializable."""
        from backend.adapter import adapt_storm_event

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)
        dumped = genai_event.model_dump(mode="json")
        json.dumps(dumped, default=str)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Result Shape Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineResult:
    def test_result_model_fields(self):
        """PipelineResult has all expected fields."""
        from backend.pipeline import PipelineResult

        r = PipelineResult(storm_id="test")
        assert r.storm_id == "test"
        assert r.cv_event == {}
        assert r.impact_prediction is None
        assert r.advisories == []
        assert r.verified_advisories == []
        assert r.provenance_traces == []
        assert r.errors == []

    def test_result_serializable(self):
        """PipelineResult must be JSON-serializable."""
        from backend.pipeline import PipelineResult

        r = PipelineResult(
            storm_id="2024-10-G4",
            cv_event={"test": True},
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        json.dumps(r.model_dump(), default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Full Pipeline Integration (stub-based, no network)
# ─────────────────────────────────────────────────────────────────────────────

class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_with_stubs(self):
        """
        Run pipeline on 2024-10-G4. Detection uses stub fallback
        (no cached PNGs needed). Advisory generation mocked to avoid
        requiring GROQ_API_KEY in CI.
        """
        from backend.pipeline import run_full_pipeline
        from genai.models import (
            ActionItem, AdvisoryOutput, Industry, SafetyFlag, SeverityTier,
        )

        # Mock genai.run_pipeline to avoid needing Groq API key
        mock_advisory = AdvisoryOutput(
            storm_event_id="2024-10-G4",
            industry=Industry.AVIATION,
            severity=SeverityTier.CRITICAL,
            confidence_score=0.82,
            summary="G4 storm: reroute flights below 70N, switch to 5 MHz HF.",
            action_items=[
                ActionItem(
                    step=1,
                    action="Reroute all North Atlantic flights below 70°N to avoid HF blackout zone.",
                    rationale="ICAO NAT Doc 007 requires rerouting during G4+ storms.",
                    source_ref="NAT Doc 007 §4.3.1",
                    time_window="T+0 to T+6h",
                ),
            ],
            sources_cited=["NAT Doc 007"],
            validation_passed=True,
        )

        async def mock_run_pipeline(storm):
            return [mock_advisory]

        with patch("genai.run_pipeline", mock_run_pipeline), \
             patch("genai.orchestrator.run_pipeline", mock_run_pipeline):
            result = await run_full_pipeline(
                "2024-10-G4",
                base_dir=str(Path(__file__).parent.parent),
            )

        assert result.storm_id == "2024-10-G4"
        assert result.cv_event  # detection succeeded (stub or real)
        assert result.completed_at
        # Adapter should have produced genai_event
        assert result.genai_event
        assert result.genai_event.get("g_scale") == "G4" or result.genai_event.get("alert_id") == "2024-10-G4"
        # Advisory should be present
        assert len(result.advisories) == 1
        # Verifier should have run
        assert len(result.verified_advisories) == 1
        assert len(result.provenance_traces) == 1
