"""
LangGraph orchestration for HelioOps advisory generation.

Graph topology:
  START
    │
    ▼
  classify_route           (deterministic — no LLM)
    │
    ▼ (parallel Send per triggered industry)
  run_agent × N            (async — RAG + Groq + guardrails)
    │ (fan-in via operator.add reducer)
    ▼
  compile_advisories
    │
    ▼
  END

Usage:
  # Streaming (for WebSocket events):
  async for event in stream_pipeline(storm):
      await ws_manager.broadcast_all(event)

  # Batch (for replay / testing):
  advisories = await run_pipeline(storm)
"""

from __future__ import annotations

import asyncio
import operator
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator

# Ensure project root is on sys.path so embeddings/ is importable
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

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
from genai.impact_router import route_storm
from genai.models import (
    ActionItem,
    AdvisoryOutput,
    Industry,
    SafetyFlag,
    SeverityTier,
    StormEvent,
)
from genai.prompts.aviation import AVIATION_KB_QUERY, AVIATION_SYSTEM_PROMPT
from genai.prompts.base import format_advisory_prompt
from genai.prompts.grid import GRID_KB_QUERY, GRID_SYSTEM_PROMPT
from genai.prompts.maritime import MARITIME_KB_QUERY, MARITIME_SYSTEM_PROMPT
from genai.prompts.telecom import TELECOM_KB_QUERY, TELECOM_SYSTEM_PROMPT
from genai.retriever import compute_context_quality, retrieve_chunks

# ── Industry prompt registry ──────────────────────────────────────────────────

_INDUSTRY_PROMPTS: dict[str, tuple[str, str]] = {
    "aviation": (AVIATION_SYSTEM_PROMPT, AVIATION_KB_QUERY),
    "grid":     (GRID_SYSTEM_PROMPT,     GRID_KB_QUERY),
    "maritime": (MARITIME_SYSTEM_PROMPT, MARITIME_KB_QUERY),
    "telecom":  (TELECOM_SYSTEM_PROMPT,  TELECOM_KB_QUERY),
}


# ── LangGraph State ───────────────────────────────────────────────────────────

class GraphState(TypedDict):
    """
    Shared state for the HelioOps advisory pipeline.

    operator.add reducers on agent_results and stream_log allow parallel
    run_agent nodes to safely append without overwriting each other.
    """
    storm_event:          dict                                   # StormEvent serialised
    impacted_industries:  list                                   # List[IndustryImpact] serialised
    current_industry:     str                                    # set per-agent via Send
    current_severity:     str                                    # set per-agent via Send
    agent_results:        Annotated[list, operator.add]          # accumulates AdvisoryOutput dicts
    stream_log:           Annotated[list, operator.add]          # accumulates StreamEvent dicts


# ── LLM factory ──────────────────────────────────────────────────────────────

def _make_llm(json_mode: bool = True) -> ChatGroq:
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


# ── Graph Nodes ───────────────────────────────────────────────────────────────

def classify_route(state: GraphState) -> dict:
    """
    Node 1: Deterministic routing — no LLM involved.

    Reads the StormEvent from state, runs the G-scale impact matrix,
    writes impacted_industries back to state, and emits a routing log entry.
    """
    storm = StormEvent(**state["storm_event"])
    impacts = route_storm(storm)
    triggered = [i for i in impacts if i.triggered]

    log_entry = {
        "event": "agent.thinking",
        "step": "routing_complete",
        "message": (
            f"Storm {storm.g_scale.value} (Kp={storm.kp_index}) routed. "
            f"Triggered industries: {[i.industry.value for i in triggered]}"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "impacted_industries": [i.model_dump() for i in impacts],
        "stream_log": [log_entry],
    }


def _route_to_agents(state: GraphState) -> list[Send]:
    """
    Conditional edge function after classify_route.

    Always returns a list[Send] — LangGraph executes them in parallel.
    If no industries were triggered, sends a single no-op to compile_advisories.
    """
    triggered = [i for i in state["impacted_industries"] if i["triggered"]]
    if not triggered:
        # No advisory needed — skip directly to fan-in node
        return [Send("compile_advisories", state)]

    return [
        Send(
            "run_agent",
            {
                **state,
                "current_industry": i["industry"],
                "current_severity": i["severity"],
                "agent_results": [],
                "stream_log": [],
            },
        )
        for i in triggered
    ]


async def run_agent(state: GraphState) -> dict:
    """
    Node 2 (parallel): Full advisory generation pipeline for one industry.

    Steps per agent:
      1. Build KB query from storm parameters
      2. Retrieve from industry KB (async thread pool — ChromaDB is sync)
      3. Retrieve from impact_matrix_kb
      4. Format context for LLM
      5. Generate advisory (Groq + JSON mode)
      6. Validate schema (Pydantic)
      7. Check severity consistency vs deterministic matrix
      8. LLM self-check for hallucinations (optional, SELF_CHECK_ENABLED)
      9. Compute confidence score
     10. Apply safety flags
     11. Retry on failure (up to MAX_RETRY_ATTEMPTS)
     12. Safe fallback if all retries exhausted
    """
    storm    = StormEvent(**state["storm_event"])
    industry = state["current_industry"]
    severity = state["current_severity"]

    stream_log: list[dict] = []
    advisory:   AdvisoryOutput | None = None
    errors:     list[str] = []

    def _log(step: str, msg: str) -> None:
        stream_log.append({
            "event": "agent.thinking",
            "industry": industry,
            "step": step,
            "message": msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    _log("start", f"Starting {industry} advisory for {storm.g_scale.value} (Kp={storm.kp_index})")

    # ── Step 1-4: RAG Retrieval ───────────────────────────────────────────────
    system_prompt, kb_query_tpl = _INDUSTRY_PROMPTS[industry]
    kb_query = kb_query_tpl.format(
        g_scale=storm.g_scale.value,
        kp_index=storm.kp_index,
        s_scale=storm.s_scale or "N/A",
        r_scale=storm.r_scale or "N/A",
    )
    impact_query = f"{storm.g_scale.value} storm severity impact {industry} operations"

    _log("rag_start", f"Retrieving {industry} KB + impact matrix context")

    # ChromaDB is synchronous; run in thread pool to avoid blocking the event loop
    industry_chunks, impact_chunks = await asyncio.gather(
        asyncio.to_thread(retrieve_chunks, INDUSTRY_KB_MAP[industry], kb_query, RAG_TOP_K),
        asyncio.to_thread(retrieve_chunks, IMPACT_MATRIX_KB, impact_query, RAG_IMPACT_MATRIX_TOP_K),
    )
    all_chunks = industry_chunks + impact_chunks
    context_quality = compute_context_quality(all_chunks)

    _log(
        "rag_done",
        f"Retrieved {len(industry_chunks)} industry chunks + "
        f"{len(impact_chunks)} impact matrix chunks (avg_similarity={context_quality:.2f})",
    )

    # ── Steps 5-10: Generation + Validation Loop ──────────────────────────────
    llm = _make_llm(json_mode=True)

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        _log(
            f"gen_attempt_{attempt}",
            f"Generating advisory (attempt {attempt}/{MAX_RETRY_ATTEMPTS})",
        )

        prompt = format_advisory_prompt(
            storm=storm,
            industry=industry,
            severity=severity,
            chunks=all_chunks,
            previous_errors=errors if errors else None,
        )

        # ── LLM call ──
        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ])
            raw = response.content
        except Exception as exc:
            err = f"LLM call failed: {exc}"
            errors.append(err)
            _log("llm_error", err[:120])
            continue

        # ── Schema validation ──
        parsed, val_errors = validate_advisory_schema(
            raw_json=raw,
            industry=industry,
            storm_event_id=storm.alert_id,
            expected_severity=severity,
        )
        if val_errors:
            errors.extend(val_errors)
            _log("validation_fail", f"Schema errors: {'; '.join(val_errors[:2])}")
            continue  # retry with error feedback in prompt

        # ── Severity consistency ──
        consistent, sev_note = check_severity_consistency(parsed, severity)
        if not consistent:
            parsed.safety_flags.append(SafetyFlag.SEVERITY_MISMATCH)
            _log("severity_flag", sev_note)

        # ── LLM self-check ──
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
                # Final attempt — keep advisory but flag is already set

        # ── Confidence score ──
        parsed.confidence_score = compute_confidence_score(parsed, all_chunks, context_quality)
        parsed.model_used = GROQ_MODEL

        # ── Safety flags ──
        parsed = apply_safety_flags(parsed, all_chunks, context_quality)

        advisory = parsed
        _log(
            "advisory_ready",
            f"Advisory generated — severity={advisory.severity.value} "
            f"confidence={advisory.confidence_score:.2f} "
            f"flags={[f.value for f in advisory.safety_flags]}",
        )
        break

    # ── Step 12: Safe fallback ────────────────────────────────────────────────
    if advisory is None:
        advisory = _safe_escalation(storm, industry, severity, errors)
        _log("fallback", "All attempts failed — emitting ESCALATE_TO_SPECIALIST advisory")

    stream_log.append({
        "event": "advisory.ready",
        "industry": industry,
        "advisory_id": advisory.advisory_id,
        "severity": advisory.severity.value,
        "confidence": advisory.confidence_score,
        "flags": [f.value for f in advisory.safety_flags],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "agent_results": [advisory.model_dump(mode="json")],
        "stream_log": stream_log,
    }


def compile_advisories(state: GraphState) -> dict:
    """
    Node 3 (fan-in): Collects all parallel agent results and emits pipeline.complete.
    """
    industries = [r.get("industry") for r in state.get("agent_results", [])]
    return {
        "stream_log": [{
            "event": "pipeline.complete",
            "total_advisories": len(state.get("agent_results", [])),
            "industries": industries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }


# ── Safe fallback factory ─────────────────────────────────────────────────────

def _safe_escalation(
    storm: StormEvent,
    industry: str,
    severity: str,
    errors: list[str],
) -> AdvisoryOutput:
    """
    Returns a minimal, safe advisory that instructs operators to escalate manually.
    Used when all generation retries are exhausted.
    """
    return AdvisoryOutput(
        advisory_id=str(uuid.uuid4()),
        storm_event_id=storm.alert_id,
        industry=Industry(industry),
        severity=SeverityTier(severity),
        confidence_score=0.0,
        summary=(
            f"AUTOMATED ADVISORY UNAVAILABLE. A {storm.g_scale.value} geomagnetic storm "
            f"(Kp={storm.kp_index}) is active with {severity} impact severity on "
            f"{industry} operations. Manual expert review is required immediately."
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


# ── Graph compilation ─────────────────────────────────────────────────────────

def build_graph():
    """Compile the LangGraph StateGraph. Called once; result is cached."""
    graph = StateGraph(GraphState)

    graph.add_node("classify_route",     classify_route)
    graph.add_node("run_agent",          run_agent)
    graph.add_node("compile_advisories", compile_advisories)

    graph.add_edge(START, "classify_route")
    graph.add_conditional_edges(
        "classify_route",
        _route_to_agents,
        ["run_agent", "compile_advisories"],
    )
    graph.add_edge("run_agent",          "compile_advisories")
    graph.add_edge("compile_advisories", END)

    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ── Public API ────────────────────────────────────────────────────────────────

def _initial_state(storm: StormEvent) -> GraphState:
    return {
        "storm_event":         storm.model_dump(mode="json"),
        "impacted_industries": [],
        "current_industry":    "",
        "current_severity":    "",
        "agent_results":       [],
        "stream_log":          [],
    }


async def stream_pipeline(storm: StormEvent) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields stream events as the pipeline executes.

    Yields dicts with at minimum:
      {"event": "agent.thinking" | "advisory.ready" | "pipeline.complete", ...}

    The backend WebSocket handler should forward these directly to connected clients.

    Example:
        async for event in stream_pipeline(storm):
            await ws_manager.broadcast_all(make_ws_event(event["event"], event))
    """
    graph = _get_graph()
    async for update in graph.astream(_initial_state(storm), stream_mode="updates"):
        for _node, node_output in update.items():
            for log_entry in node_output.get("stream_log", []):
                yield log_entry
            # advisory.ready events are embedded in stream_log by run_agent
            # but also expose agent_results directly for convenience
            for result in node_output.get("agent_results", []):
                yield {
                    "event":      "advisory.generated",
                    "industry":   result.get("industry"),
                    "advisory_id": result.get("advisory_id"),
                    "severity":   result.get("severity"),
                    "confidence": result.get("confidence_score"),
                    "data":       result,
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                }


async def run_pipeline(storm: StormEvent) -> list[AdvisoryOutput]:
    """
    Run the full pipeline and return all generated advisories.

    Suitable for replay endpoints and batch processing.
    Does not stream — waits for complete graph execution.
    """
    graph = _get_graph()
    result = await graph.ainvoke(_initial_state(storm))
    advisories: list[AdvisoryOutput] = []
    for r in result.get("agent_results", []):
        try:
            advisories.append(AdvisoryOutput(**r))
        except Exception:
            pass
    return advisories
