"""
backend/pipeline.py — Unified pipeline chaining all 4 HelioOps layers.

Pipeline: detect → predict_impact → adapt → generate_advisories → verify

Usage:
    from backend.pipeline import run_full_pipeline, stream_full_pipeline

    # Batch mode
    result = await run_full_pipeline("2024-10-G4")

    # Streaming mode (for WebSocket)
    async for event in stream_full_pipeline("2024-10-G4"):
        print(event)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# The layers below the backend (cv, ML_after_CV, genai) are reached only through
# these adapters — never imported directly. app.py imports the same instances.
from backend.adapters.advisory_adapter import (
    GenAIAdvisoryAdapter,
    GenAIVerificationAdapter,
)
from backend.adapters.detection_adapter import CVDetectionAdapter
from backend.adapters.prediction_adapter import MLPredictionAdapter
from backend.adapters.schema_adapter import adapt_storm_event
from backend.config import settings

detection_adapter = CVDetectionAdapter(available_storm_ids=settings.AVAILABLE_STORM_IDS)
prediction_adapter = MLPredictionAdapter()
advisory_adapter = GenAIAdvisoryAdapter()
verification_adapter = GenAIVerificationAdapter()


class PipelineResult(BaseModel):
    """Complete output from one pipeline run."""

    storm_id: str
    cv_event: dict = Field(default_factory=dict)
    impact_prediction: dict | None = None
    genai_event: dict = Field(default_factory=dict)
    advisories: list[dict] = Field(default_factory=list)
    verified_advisories: list[dict] = Field(default_factory=list)
    provenance_traces: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    completed_at: str = ""


# In-memory result store (hackathon scope — no DB)
_RESULTS: dict[str, PipelineResult] = {}
_ADVISORY_INDEX: dict[str, dict] = {}  # advisory_id → {verified, provenance}


def get_result(storm_id: str) -> PipelineResult | None:
    return _RESULTS.get(storm_id)


def get_all_results() -> dict[str, PipelineResult]:
    return _RESULTS


def get_advisory(advisory_id: str) -> dict | None:
    return _ADVISORY_INDEX.get(advisory_id)


async def run_full_pipeline(storm_id: str, base_dir: str | None = None) -> PipelineResult:
    """
    Run the complete pipeline: detect → predict → adapt → generate → verify.
    Each step has try/except — errors logged but pipeline continues where possible.
    """
    result = PipelineResult(storm_id=storm_id)

    # ── Step 1: CV Detection ─────────────────────────────────────────────
    try:
        cv_event = await detection_adapter.detect_async(storm_id, base_dir)
        result.cv_event = cv_event.model_dump()
        log.info(
            "Detection complete: %s (confidence=%.3f)", storm_id, cv_event.confidence
        )
    except Exception as exc:
        err = f"Detection failed: {exc}"
        log.error(err)
        result.errors.append(err)
        result.completed_at = datetime.now(timezone.utc).isoformat()
        _RESULTS[storm_id] = result
        return result

    # ── Step 2: ML Impact Prediction ─────────────────────────────────────
    try:
        impact = await prediction_adapter.predict_async(result.cv_event)
        result.impact_prediction = impact.model_dump()
        log.info(
            "Impact prediction: GPS=%.2fm [%.2f–%.2f], HF=%.2f%% [%.2f–%.2f]",
            impact.gps_error_m,
            impact.gps_error_ci_low,
            impact.gps_error_ci_high,
            impact.hf_blackout_prob * 100,
            impact.hf_blackout_ci_low * 100,
            impact.hf_blackout_ci_high * 100,
        )
    except Exception as exc:
        err = f"Impact prediction failed (non-fatal): {exc}"
        log.warning(err)
        result.errors.append(err)

    # ── Step 3: Schema Adaptation ────────────────────────────────────────
    try:
        genai_event = adapt_storm_event(cv_event)
        result.genai_event = genai_event.model_dump(mode="json")
        log.info(
            "Adapted to GenAI schema: %s Kp=%.1f",
            genai_event.g_scale.value,
            genai_event.kp_index,
        )
    except Exception as exc:
        err = f"Schema adaptation failed: {exc}"
        log.error(err)
        result.errors.append(err)
        result.completed_at = datetime.now(timezone.utc).isoformat()
        _RESULTS[storm_id] = result
        return result

    # ── Step 4: GenAI Advisory Generation ────────────────────────────────
    try:
        advisories = await advisory_adapter.generate(genai_event)
        result.advisories = [a.model_dump(mode="json") for a in advisories]
        log.info("Generated %d advisories", len(advisories))
    except Exception as exc:
        err = f"Advisory generation failed: {exc}"
        log.error(err)
        result.errors.append(err)
        advisories = []

    # ── Step 5: Verification ─────────────────────────────────────────────
    if advisories:
        for advisory in advisories:
            try:
                verified, provenance = verification_adapter.verify(
                    advisory,
                    result.cv_event,
                    result.impact_prediction,
                )
                v_dict = verified.model_dump()
                p_dict = provenance.model_dump()
                result.verified_advisories.append(v_dict)
                result.provenance_traces.append(p_dict)

                _ADVISORY_INDEX[verified.advisory_id] = {
                    "verified_advisory": v_dict,
                    "provenance_trace": p_dict,
                }

                log.info(
                    "Verified advisory %s: %s/%s [%s]",
                    verified.advisory_id,
                    verified.industry,
                    verified.severity,
                    verified.verifier.status,
                )
            except Exception as exc:
                err = f"Verification failed for {advisory.advisory_id}: {exc}"
                log.warning(err)
                result.errors.append(err)

    result.completed_at = datetime.now(timezone.utc).isoformat()
    _RESULTS[storm_id] = result
    return result


async def stream_full_pipeline(
    storm_id: str, base_dir: str | None = None
) -> AsyncGenerator[dict, None]:
    """
    Streaming variant — yields events at each pipeline stage.
    Uses genai.stream_pipeline() for real-time advisory generation events.
    """
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    errors: list[str] = []

    # ── Step 1: Detection ────────────────────────────────────────────────
    yield {
        "event": "pipeline.stage",
        "stage": "detection",
        "status": "started",
        "timestamp": now(),
    }

    try:
        cv_event = await detection_adapter.detect_async(storm_id, base_dir)
        cv_dict = cv_event.model_dump()
        yield {
            "event": "pipeline.stage",
            "stage": "detection",
            "status": "completed",
            "data": {
                "storm_id": storm_id,
                "confidence": cv_event.confidence,
                "scales": cv_event.scales,
            },
            "timestamp": now(),
        }
    except Exception as exc:
        yield {
            "event": "pipeline.error",
            "stage": "detection",
            "error": str(exc),
            "timestamp": now(),
        }
        return

    # ── Step 2: Impact Prediction ────────────────────────────────────────
    yield {
        "event": "pipeline.stage",
        "stage": "impact_prediction",
        "status": "started",
        "timestamp": now(),
    }

    impact_dict = None
    try:
        impact = await prediction_adapter.predict_async(cv_dict)
        impact_dict = impact.model_dump()
        yield {
            "event": "pipeline.stage",
            "stage": "impact_prediction",
            "status": "completed",
            "data": impact_dict,
            "timestamp": now(),
        }
    except Exception as exc:
        errors.append(f"Impact prediction failed (non-fatal): {exc}")
        yield {
            "event": "pipeline.stage",
            "stage": "impact_prediction",
            "status": "failed",
            "error": str(exc),
            "timestamp": now(),
        }

    # ── Step 3: Schema Adaptation ────────────────────────────────────────
    yield {
        "event": "pipeline.stage",
        "stage": "adaptation",
        "status": "started",
        "timestamp": now(),
    }

    try:
        genai_event = adapt_storm_event(cv_event)
        yield {
            "event": "pipeline.stage",
            "stage": "adaptation",
            "status": "completed",
            "data": {
                "g_scale": genai_event.g_scale.value,
                "kp_index": genai_event.kp_index,
            },
            "timestamp": now(),
        }
    except Exception as exc:
        yield {
            "event": "pipeline.error",
            "stage": "adaptation",
            "error": str(exc),
            "timestamp": now(),
        }
        return

    # ── Step 4: GenAI Advisory Generation (streaming) ────────────────────
    yield {
        "event": "pipeline.stage",
        "stage": "advisory_generation",
        "status": "started",
        "timestamp": now(),
    }

    advisories = []
    try:
        async for event in advisory_adapter.stream(genai_event):
            # genai ends its own stream with "pipeline.complete". Forwarded as-is it
            # collides with this function's terminal event, so a client that stops on
            # pipeline.complete never sees verification. Re-emit it as the stage-completed
            # event this step otherwise never sends.
            if event.get("event") == "pipeline.complete":
                event = {
                    "event": "pipeline.stage",
                    "stage": "advisory_generation",
                    "status": "completed",
                    "data": {"total_advisories": event.get("total_advisories", 0)},
                    "timestamp": event.get("timestamp", now()),
                }
            yield event
            if event.get("event") == "advisory.generated":
                from backend.genai.models import AdvisoryOutput

                try:
                    adv = AdvisoryOutput(**event["data"])
                    advisories.append(adv)
                except Exception:
                    pass
    except Exception as exc:
        errors.append(f"Advisory generation failed: {exc}")
        yield {
            "event": "pipeline.stage",
            "stage": "advisory_generation",
            "status": "failed",
            "error": str(exc),
            "timestamp": now(),
        }

    # ── Step 5: Verification ─────────────────────────────────────────────
    if advisories:
        yield {
            "event": "pipeline.stage",
            "stage": "verification",
            "status": "started",
            "timestamp": now(),
        }

        from backend.genai.verifier import verifier_stream_events

        verified_list = []
        for advisory in advisories:
            try:
                verified, provenance = verification_adapter.verify(
                    advisory, cv_dict, impact_dict
                )
                verified_list.append(verified)

                # Emit verifier check events
                for check_event in verifier_stream_events(
                    verified.verifier.checks, verified.industry
                ):
                    yield check_event

                yield {
                    "event": "advisory.verified",
                    "advisory_id": verified.advisory_id,
                    "industry": verified.industry,
                    "severity": verified.severity,
                    "verifier_status": verified.verifier.status,
                    "requires_human": verified.requires_human,
                    "timestamp": now(),
                }

                _ADVISORY_INDEX[verified.advisory_id] = {
                    "verified_advisory": verified.model_dump(),
                    "provenance_trace": provenance.model_dump(),
                }
            except Exception as exc:
                errors.append(f"Verification failed for {advisory.advisory_id}: {exc}")
                yield {
                    "event": "verifier.error",
                    "advisory_id": advisory.advisory_id,
                    "error": str(exc),
                    "timestamp": now(),
                }

        yield {
            "event": "pipeline.stage",
            "stage": "verification",
            "status": "completed",
            "data": {"verified_count": len(verified_list)},
            "timestamp": now(),
        }

    # Store result
    result = PipelineResult(
        storm_id=storm_id,
        cv_event=cv_dict,
        impact_prediction=impact_dict,
        genai_event=genai_event.model_dump(mode="json"),
        advisories=[a.model_dump(mode="json") for a in advisories],
        verified_advisories=[
            _ADVISORY_INDEX[v.advisory_id]["verified_advisory"]
            for v in (verified_list if advisories else [])
        ],
        provenance_traces=[
            _ADVISORY_INDEX[v.advisory_id]["provenance_trace"]
            for v in (verified_list if advisories else [])
        ],
        errors=errors,
        completed_at=now(),
    )
    _RESULTS[storm_id] = result

    yield {
        "event": "pipeline.complete",
        "storm_id": storm_id,
        "total_advisories": len(advisories),
        "total_verified": len(verified_list) if advisories else 0,
        "errors": result.errors,
        "timestamp": now(),
    }
