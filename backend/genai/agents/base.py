"""
Base industry agent using AgentScope's message protocol.

Each industry agent subclasses IndustryAgentBase and provides:
  - system_prompt: industry-specific persona + rules
  - kb_query_template: ChromaDB query template with {g_scale}, {kp_index}, etc.

Orchestration (parallel fan-out) is done via asyncio.gather in orchestrator.py.

The full per-industry pipeline runs inside run_async():
  1. Build KB query from storm parameters
  2. Retrieve from industry KB + impact_matrix_kb
  3. Format context for LLM
  4. Generate advisory (Groq + JSON mode)
  5. Validate schema, severity, citations
  6. LLM self-check for hallucinations
  7. Compute confidence score
  8. Apply safety flags
  9. Retry loop (up to MAX_RETRY_ATTEMPTS)
  10. Safe fallback if all retries exhausted
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from backend.genai.config import (
    GROQ_MODEL,
    IMPACT_MATRIX_KB,
    INDUSTRY_KB_MAP,
    MAX_RETRY_ATTEMPTS,
    RAG_IMPACT_MATRIX_TOP_K,
    RAG_TOP_K,
    SELF_CHECK_BLOCKING,
    SELF_CHECK_CONFIDENCE_PENALTY,
    SELF_CHECK_ENABLED,
)
from backend.genai.guardrails import (
    apply_safety_flags,
    check_severity_consistency,
    compute_confidence_score,
    self_check_hallucination,
    validate_advisory_schema,
)
from backend.genai.models import (
    ActionItem,
    AdvisoryOutput,
    Industry,
    SafetyFlag,
    SeverityTier,
    StormEvent,
)
from backend.genai.llm import complete_json
from backend.genai.prompts.base import format_advisory_prompt
from backend.genai.retriever import compute_context_quality, retrieve_chunks


class IndustryAgentBase:
    """
    Base agent for per-industry advisory generation.

    Subclasses provide: industry, system_prompt, kb_query_template.
    """

    def __init__(
        self,
        name: str,
        industry: str,
        system_prompt: str,
        kb_query_template: str,
        stream_callback: Optional[Callable[[dict], None]] = None,
    ):
        self.name = name
        self.industry = industry
        self.system_prompt = system_prompt
        self.kb_query_template = kb_query_template
        self.stream_callback = stream_callback

    def _emit(self, step: str, message: str) -> dict:
        """Emit a stream event for WebSocket forwarding."""
        event = {
            "event": "agent.thinking",
            "industry": self.industry,
            "step": step,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.stream_callback:
            self.stream_callback(event)
        return event

    async def run_async(self, storm: StormEvent, severity: str = "HIGH") -> dict:
        """
        Async entry point — called by orchestrator via asyncio.gather.
        Returns {"advisory": AdvisoryOutput, "stream_log": list[dict]}.
        """
        stream_log: list[dict] = []
        advisory: AdvisoryOutput | None = None
        errors: list[str] = []

        def _log(step: str, msg: str) -> None:
            event = self._emit(step, msg)
            stream_log.append(event)

        _log("start", f"Starting {self.industry} advisory for {storm.g_scale.value} (Kp={storm.kp_index})")

        # ── RAG Retrieval ─────────────────────────────────────────────────
        kb_query = self.kb_query_template.format(
            g_scale=storm.g_scale.value,
            kp_index=storm.kp_index,
            s_scale=storm.s_scale or "N/A",
            r_scale=storm.r_scale or "N/A",
        )
        impact_query = f"{storm.g_scale.value} storm severity impact {self.industry} operations"

        _log("rag_start", f"Retrieving {self.industry} KB + impact matrix context")

        industry_chunks, impact_chunks = await asyncio.gather(
            asyncio.to_thread(retrieve_chunks, INDUSTRY_KB_MAP[self.industry], kb_query, RAG_TOP_K),
            asyncio.to_thread(retrieve_chunks, IMPACT_MATRIX_KB, impact_query, RAG_IMPACT_MATRIX_TOP_K),
        )
        all_chunks = industry_chunks + impact_chunks
        context_quality = compute_context_quality(all_chunks)

        _log(
            "rag_done",
            f"Retrieved {len(industry_chunks)} industry + {len(impact_chunks)} impact chunks "
            f"(avg_similarity={context_quality:.2f})",
        )

        # ── Generation + Validation Loop ──────────────────────────────────
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            _log(f"gen_attempt_{attempt}", f"Generating advisory (attempt {attempt}/{MAX_RETRY_ATTEMPTS})")

            prompt = format_advisory_prompt(
                storm=storm,
                industry=self.industry,
                severity=severity,
                chunks=all_chunks,
                previous_errors=errors if errors else None,
            )

            try:
                raw = await complete_json(self.system_prompt, prompt)
            except Exception as exc:
                err = f"LLM call failed: {exc}"
                errors.append(err)
                _log("llm_error", err[:120])
                continue

            parsed, val_errors = validate_advisory_schema(
                raw_json=raw,
                industry=self.industry,
                storm_event_id=storm.alert_id,
                expected_severity=severity,
            )
            if val_errors:
                errors.extend(val_errors)
                _log("validation_fail", f"Schema errors: {'; '.join(val_errors[:2])}")
                continue

            consistent, sev_note = check_severity_consistency(parsed, severity)
            if not consistent:
                # Clamp up to the deterministic floor, keep the flag.
                #
                # This used to flag and publish the model's lower value. The
                # G-scale matrix in impact_router.py is the authoritative source
                # for how bad a storm is for an industry — it comes from the NOAA
                # scales, not from a language model — so a model that reads a G5
                # as MEDIUM is simply wrong, and shipping MEDIUM means an
                # operator can read "moderate" for an extreme storm. The flag
                # alone is not enough: it is one entry in a safety_flags list
                # that a dashboard may not surface at all.
                #
                # Under-reporting is the dangerous direction. Over-reporting is
                # left alone: the model may raise severity above the floor, since
                # it can see storm specifics the matrix cannot.
                original = parsed.severity.value
                parsed.severity = SeverityTier(severity)
                parsed.safety_flags.append(SafetyFlag.SEVERITY_MISMATCH)
                parsed.generation_errors.append(
                    f"Severity raised from LLM value '{original}' to matrix floor "
                    f"'{severity}'"
                )
                _log(
                    "severity_override",
                    f"{sev_note} Severity raised {original} -> {severity}.",
                )

            self_check_flagged = False
            if SELF_CHECK_ENABLED:
                _log("self_check", "Running hallucination self-check")
                halluc_free, halluc_note = await self_check_hallucination(
                    advisory=parsed,
                    context_chunks=all_chunks,
                )
                if not halluc_free:
                    self_check_flagged = True
                    errors.append(f"Self-check: {halluc_note}")
                    parsed.safety_flags.append(SafetyFlag.HALLUCINATION_DETECTED)
                    _log("self_check_fail", f"Hallucination detected: {halluc_note[:80]}")
                    # Regenerating costs a full prompt+completion and usually
                    # reproduces the same flagged numerics. Off by default —
                    # see SELF_CHECK_BLOCKING in genai/config.py.
                    if SELF_CHECK_BLOCKING and attempt < MAX_RETRY_ATTEMPTS:
                        continue

            parsed.confidence_score = compute_confidence_score(parsed, all_chunks, context_quality)
            if self_check_flagged:
                # The flag has to cost something, or a flagged advisory can
                # still surface with a 0.96 confidence score next to a clean one.
                parsed.confidence_score = round(
                    max(0.0, parsed.confidence_score - SELF_CHECK_CONFIDENCE_PENALTY), 4
                )
            parsed.model_used = GROQ_MODEL
            parsed = apply_safety_flags(
                parsed,
                all_chunks,
                context_quality,
                industry_chunk_count=len(industry_chunks),
            )

            advisory = parsed
            _log(
                "advisory_ready",
                f"Advisory generated — severity={advisory.severity.value} "
                f"confidence={advisory.confidence_score:.2f} "
                f"flags={[f.value for f in advisory.safety_flags]}",
            )
            break

        # Safe fallback
        if advisory is None:
            advisory = self._safe_escalation(storm, severity, errors)
            _log("fallback", "All attempts failed — emitting ESCALATE_TO_SPECIALIST advisory")

        stream_log.append({
            "event": "advisory.ready",
            "industry": self.industry,
            "advisory_id": advisory.advisory_id,
            "severity": advisory.severity.value,
            "confidence": advisory.confidence_score,
            "flags": [f.value for f in advisory.safety_flags],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {"advisory": advisory, "stream_log": stream_log}

    def _safe_escalation(
        self,
        storm: StormEvent,
        severity: str,
        errors: list[str],
    ) -> AdvisoryOutput:
        """Safe fallback advisory when all generation retries are exhausted."""
        return AdvisoryOutput(
            advisory_id=str(uuid.uuid4()),
            storm_event_id=storm.alert_id,
            industry=Industry(self.industry),
            severity=SeverityTier(severity),
            confidence_score=0.0,
            summary=(
                f"AUTOMATED ADVISORY UNAVAILABLE. A {storm.g_scale.value} geomagnetic storm "
                f"(Kp={storm.kp_index}) is active with {severity} impact severity on "
                f"{self.industry} operations. Manual expert review is required immediately."
            ),
            action_items=[
                ActionItem(
                    step=1,
                    action=(
                        "ESCALATE TO SPECIALIST — Contact your space weather operations specialist "
                        "immediately. Automated advisory generation failed after all retry attempts."
                    ),
                    rationale="System could not produce a validated, hallucination-free advisory.",
                    source_ref=None,
                    time_window="IMMEDIATE",
                )
            ],
            estimated_impact_window=None,
            sources_cited=[],
            validation_passed=False,
            generated_at=datetime.now(timezone.utc),
            model_used=GROQ_MODEL,
            safety_flags=[SafetyFlag.GENERATION_FAILED],
            generation_errors=errors[:5],
        )
