"""
Base industry agent using AgentScope's message protocol.

Each industry agent subclasses IndustryAgentBase and provides:
  - system_prompt: industry-specific persona + rules
  - kb_query_template: ChromaDB query template with {g_scale}, {kp_index}, etc.

Uses agentscope.message.Msg for structured message passing between agents.
Orchestration (parallel fan-out) done via asyncio.gather in orchestrator.py.

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
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from agentscope.message import Msg, TextBlock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from genai.config import (
    GROQ_API_KEY,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    IMPACT_MATRIX_KB,
    INDUSTRY_KB_MAP,
    MAX_RETRY_ATTEMPTS,
    RAG_IMPACT_MATRIX_TOP_K,
    RAG_TOP_K,
    SELF_CHECK_ENABLED,
)
from genai.guardrails import (
    apply_safety_flags,
    check_severity_consistency,
    compute_confidence_score,
    self_check_hallucination,
    validate_advisory_schema,
)
from genai.models import (
    ActionItem,
    AdvisoryOutput,
    Industry,
    SafetyFlag,
    SeverityTier,
    StormEvent,
)
from genai.prompts.base import format_advisory_prompt
from genai.retriever import compute_context_quality, retrieve_chunks


def _make_llm(json_mode: bool = True) -> ChatGroq:
    """Create a Groq LLM instance."""
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
        **kwargs,
    )


def _msg_payload(msg: Msg) -> dict:
    """Extract JSON payload from an AgentScope Msg (content is list[TextBlock])."""
    for block in msg.content:
        if hasattr(block, "text"):
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                pass
    return {}


def _make_msg(name: str, role: str, payload: dict) -> Msg:
    """Create an AgentScope Msg with a JSON payload in a TextBlock."""
    return Msg(
        name=name,
        role=role,
        content=[TextBlock(text=json.dumps(payload))],
    )


class IndustryAgentBase:
    """
    Base agent for per-industry advisory generation.
    Uses AgentScope's Msg protocol for input/output.

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

    async def run_async(self, x: Msg) -> Msg:
        """
        Async entry point — called by orchestrator via asyncio.gather.
        Input Msg carries storm_event + severity in a TextBlock JSON payload.
        """
        payload = _msg_payload(x)
        storm = StormEvent(**payload["storm_event"])
        severity = payload.get("severity", "HIGH")

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
        llm = _make_llm(json_mode=True)

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
                response = await llm.ainvoke([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=prompt),
                ])
                raw = response.content
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
                parsed.safety_flags.append(SafetyFlag.SEVERITY_MISMATCH)
                _log("severity_flag", sev_note)

            if SELF_CHECK_ENABLED:
                _log("self_check", "Running hallucination self-check")
                halluc_free, halluc_note = await self_check_hallucination(
                    advisory=parsed,
                    context_chunks=all_chunks,
                    llm=_make_llm(json_mode=True),
                )
                if not halluc_free:
                    errors.append(f"Self-check: {halluc_note}")
                    parsed.safety_flags.append(SafetyFlag.HALLUCINATION_DETECTED)
                    _log("self_check_fail", f"Hallucination detected: {halluc_note[:80]}")
                    if attempt < MAX_RETRY_ATTEMPTS:
                        continue

            parsed.confidence_score = compute_confidence_score(parsed, all_chunks, context_quality)
            parsed.model_used = GROQ_MODEL
            parsed = apply_safety_flags(parsed, all_chunks, context_quality)

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

        return _make_msg(
            name=self.name,
            role="assistant",
            payload={
                "advisory": advisory.model_dump(mode="json"),
                "stream_log": stream_log,
            },
        )

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
