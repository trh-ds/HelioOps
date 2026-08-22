"""
tests/test_pipeline.py — Integration tests for the backend pipeline bridge.

Tests:
  - ML inference (with fallback when checkpoints missing)
  - Schema adapter (cv.storm_event_generator.fusion.StormEvent → genai.models.StormEvent)
  - Full pipeline (detect → adapt → predict → generate → verify)

Run:
    pytest tests/test_pipeline.py -v
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.cv.storm_event_generator.fusion import StormEvent as CvStormEvent, fuse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_cv_event() -> CvStormEvent:
    """Build a realistic cv.storm_event_generator.fusion.StormEvent matching the G4 stub shape."""
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
        from backend.ml.inference import predict, _MODELS
        _MODELS.clear()

        # Point to a non-existent dir so models can't load
        import backend.ml.inference as inf_mod
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
        from backend.ml.inference import _extract_features

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
        from backend.ml.inference import predict, _MODELS, _CHECKPOINT_DIR
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
        from backend.adapters.schema_adapter import adapt_storm_event
        from backend.genai.models import GScale

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
        from backend.adapters.schema_adapter import adapt_storm_event

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.estimated_arrival_utc is not None
        assert isinstance(genai_event.estimated_arrival_utc, datetime)

    def test_peak_window_set(self):
        """Peak impact window start/end are set from timeline."""
        from backend.adapters.schema_adapter import adapt_storm_event

        cv_event = _make_cv_event()
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.peak_impact_window_start is not None
        if genai_event.peak_impact_window_end is not None:
            delta = genai_event.peak_impact_window_end - genai_event.peak_impact_window_start
            assert delta.total_seconds() == 6 * 3600  # 6 hours

    def test_g_scale_clamping(self):
        """G=0 clamps to G1."""
        from backend.adapters.schema_adapter import adapt_storm_event
        from backend.genai.models import GScale

        cv_event = _make_cv_event()
        # Override scales to G=0
        cv_event.scales["G"] = 0
        genai_event = adapt_storm_event(cv_event)

        assert genai_event.g_scale == GScale.G1

    def test_empty_alert_text_enriched(self):
        """Empty alert text gets enriched with storm data."""
        from backend.adapters.schema_adapter import adapt_storm_event

        cv_event = _make_cv_event()
        cv_event.noaa_alert_raw = ""
        genai_event = adapt_storm_event(cv_event)

        assert "geomagnetic storm" in genai_event.raw_alert_text.lower()
        assert "km/s" in genai_event.raw_alert_text

    def test_kp_fallback_to_map(self):
        """When alert text has no Kp, fall back to G→Kp map."""
        from backend.adapters.schema_adapter import adapt_storm_event

        cv_event = _make_cv_event()
        cv_event.noaa_alert_raw = "Storm alert no kp info"
        genai_event = adapt_storm_event(cv_event)

        # G4 maps to Kp 8.3
        assert genai_event.kp_index == 8.3

    def test_genai_event_serializable(self):
        """Adapted event must be JSON-serializable."""
        from backend.adapters.schema_adapter import adapt_storm_event

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
        from backend.genai.models import (
            ActionItem, AdvisoryOutput, Industry, SeverityTier,
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

        with patch("backend.genai.run_pipeline", mock_run_pipeline), \
             patch("backend.genai.orchestrator.run_pipeline", mock_run_pipeline):
            result = await run_full_pipeline(
                "2024-10-G4",
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


# ─────────────────────────────────────────────────────────────────────────────
# Streaming contract — one terminal event, every stage closed
# ─────────────────────────────────────────────────────────────────────────────

class TestStreamEventContract:
    """
    genai.stream_pipeline() ends its own stream with "pipeline.complete".
    Forwarded verbatim it collides with stream_full_pipeline()'s terminal event:
    a client that stops on pipeline.complete (the frontend does) would never see
    verification, and would read storm_id/total_verified off the wrong event.
    """

    @pytest.mark.asyncio
    async def test_genai_complete_is_rescoped_to_its_stage(self):
        from backend.pipeline import stream_full_pipeline

        async def mock_stream(storm):
            yield {
                "event": "agent.thinking",
                "step": "routing_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            yield {  # genai's terminal event — must not reach the client as-is
                "event": "pipeline.complete",
                "total_advisories": 0,
                "industries": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        with patch(
            "backend.pipeline.advisory_adapter.stream", side_effect=mock_stream
        ):
            events = [
                e
                async for e in stream_full_pipeline("2024-10-G4")
            ]

        completes = [e for e in events if e["event"] == "pipeline.complete"]
        assert len(completes) == 1, (
            f"expected exactly 1 terminal pipeline.complete, got {len(completes)}: "
            f"{[e.get('total_advisories') for e in completes]}"
        )
        assert completes[0] is events[-1], "pipeline.complete must be the last event"
        assert completes[0]["storm_id"] == "2024-10-G4"
        assert "total_verified" in completes[0]

        # genai's event became this stage's completed marker, which the step
        # otherwise never emitted — the frontend's progress bar reads these.
        stages = {
            (e["stage"], e["status"])
            for e in events
            if e["event"] == "pipeline.stage"
        }
        for stage in ("detection", "impact_prediction", "adaptation", "advisory_generation"):
            assert (stage, "completed") in stages, f"{stage} never reported completed"


class TestNoCircularImports:
    """
    backend.pipeline imports the adapters; backend.adapters.repository_adapter
    needs PipelineResult back. A module-level import in either direction makes
    `import backend.pipeline` fail on its own — which only shows up when a
    process happens to import it first, not under the full suite.
    """

    @pytest.mark.parametrize(
        "module",
        [
            "backend.pipeline",
            "backend.app",
            "backend.adapters",
            "backend.adapters.repository_adapter",
            "backend.health",
            "backend.cv.storm_event_generator.detect",
        ],
    )
    def test_module_imports_standalone(self, module):
        import subprocess

        root = Path(__file__).resolve().parents[2]
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(root)},
        )
        assert proc.returncode == 0, (
            f"`import {module}` fails in a fresh process:\n{proc.stderr[-800:]}"
        )


class TestGuardrailsWiring:
    """
    self_check_hallucination() swallows every exception so a checker failure can
    never block an advisory. That also means a broken call site (a missing import,
    a renamed arg) degrades to "self-check skipped" and the hallucination guard is
    silently off for every advisory the system ever ships.
    """

    @pytest.mark.asyncio
    async def test_self_check_parses_a_verdict_instead_of_skipping(self):
        from backend.genai import guardrails
        from backend.genai.models import (
            ActionItem,
            AdvisoryOutput,
            Industry,
            RetrievedChunk,
            SeverityTier,
        )

        advisory = AdvisoryOutput(
            advisory_id="t1",
            storm_event_id="s1",
            industry=Industry("aviation"),
            severity=SeverityTier("HIGH"),
            confidence_score=0.8,
            summary="Reroute polar flights below 70N.",
            action_items=[
                ActionItem(
                    step=1,
                    action="Reroute polar flights below 70N.",
                    rationale="HF blackout risk.",
                    source_ref="NAT Doc 007 4.3",
                    time_window="T+0 to T+6h",
                )
            ],
            sources_cited=["NAT Doc 007"],
            validation_passed=True,
            generated_at=datetime.now(timezone.utc),
            model_used="test",
        )
        chunks = [
            RetrievedChunk(
                chunk_id="c1",
                text="NAT Doc 007 4.3: reroute polar flights below 70N.",
                source="NAT Doc 007",
                similarity=0.9,
                metadata={},
            )
        ]

        async def fake_complete_json(system, user, **kwargs):
            return json.dumps(
                {"hallucinations_found": True, "issues": ["invented altitude"], "verdict_confidence": 0.9}
            )

        with patch.object(guardrails, "complete_json", fake_complete_json):
            clean, note = await guardrails.self_check_hallucination(advisory, chunks)

        assert clean is False, "checker said hallucinations_found but result was clean"
        assert "invented altitude" in note
        assert "self-check skipped" not in note


class TestEnvLoading:
    """Importing any backend module must load .env, not just backend.app."""

    def test_dotenv_loaded_on_package_import(self):
        import subprocess

        root = Path(__file__).resolve().parents[2]
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import backend, os; print(bool(os.environ.get('GROQ_API_KEY')))",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(root)},
        )
        assert proc.returncode == 0, proc.stderr[-500:]
        assert proc.stdout.strip().endswith("True"), (
            "GROQ_API_KEY not present after `import backend` — .env is not being "
            f"loaded at package import.\n{proc.stdout}"
        )
