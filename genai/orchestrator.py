"""
AgentScope orchestration for HelioOps advisory generation.

Replaces the LangGraph graph.py with AgentScope message protocol +
asyncio.gather for parallel fan-out.

Pipeline topology:
  1. RouterAgent     — deterministic G-scale routing (no LLM)
  2. IndustryAgents  — parallel fan-out to triggered industries
  3. CompilerAgent   — fan-in: collects all advisories
  4. VerifierAgent   — deterministic rule checks (Phase 5)

Uses agentscope.message.Msg + TextBlock for structured message passing.

Usage:
  # Streaming (for WebSocket events):
  async for event in stream_pipeline(storm):
      await ws_manager.broadcast_all(event)

  # Batch (for replay / testing):
  advisories = await run_pipeline(storm)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from agentscope.message import Msg, TextBlock

from genai.agents.aviation import AviationAgent
from genai.agents.grid import GridAgent
from genai.agents.maritime import MaritimeAgent
from genai.agents.telecom import TelecomAgent
from genai.impact_router import route_storm
from genai.models import AdvisoryOutput, StormEvent


def _prewarm_embedder() -> None:
    """Load BGE model once in the main thread before parallel asyncio.to_thread calls.
    Prevents race condition: multiple threads calling _get_model() simultaneously
    causes 'Cannot copy out of meta tensor' PyTorch error."""
    from embeddings.embedder import _get_model
    _get_model()

# ── Agent registry ────────────────────────────────────────────────────────────
# Maps industry name → agent class.

_AGENT_REGISTRY: dict[str, type] = {
    "aviation": AviationAgent,
    "grid":     GridAgent,
    "maritime": MaritimeAgent,
    "telecom":  TelecomAgent,
}


def _make_input_msg(storm: StormEvent, severity: str) -> Msg:
    """Build an AgentScope Msg carrying storm + severity for an industry agent."""
    payload = {
        "storm_event": storm.model_dump(mode="json"),
        "severity": severity,
    }
    return Msg(
        name="orchestrator",
        role="user",
        content=[TextBlock(text=json.dumps(payload))],
    )


def _extract_advisory(result_msg: Msg) -> dict | None:
    """Extract advisory dict from agent result Msg."""
    for block in result_msg.content:
        if hasattr(block, "text"):
            try:
                data = json.loads(block.text)
                return data.get("advisory")
            except (json.JSONDecodeError, AttributeError):
                pass
    return None


def _extract_stream_log(result_msg: Msg) -> list[dict]:
    """Extract stream_log list from agent result Msg."""
    for block in result_msg.content:
        if hasattr(block, "text"):
            try:
                data = json.loads(block.text)
                return data.get("stream_log", [])
            except (json.JSONDecodeError, AttributeError):
                pass
    return []


# ── Public API ────────────────────────────────────────────────────────────────

async def stream_pipeline(storm: StormEvent) -> AsyncGenerator[dict, None]:
    """
    Async generator yielding stream events as pipeline executes.

    Yields dicts with at minimum:
      {"event": "agent.thinking" | "advisory.ready" | "pipeline.complete", ...}

    Backend WebSocket handler forwards these directly to connected clients.
    """
    _prewarm_embedder()

    event_queue: asyncio.Queue[dict] = asyncio.Queue()

    def _stream_callback(event: dict) -> None:
        event_queue.put_nowait(event)

    # Step 1: Deterministic routing
    impacts = route_storm(storm)
    triggered = [i for i in impacts if i.triggered]

    yield {
        "event": "agent.thinking",
        "step": "routing_complete",
        "message": (
            f"Storm {storm.g_scale.value} (Kp={storm.kp_index}) routed. "
            f"Triggered industries: {[i.industry.value for i in triggered]}"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not triggered:
        yield {
            "event": "pipeline.complete",
            "total_advisories": 0,
            "industries": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return

    # Step 2: Build agents for triggered industries
    agent_tasks = []
    for impact in triggered:
        industry = impact.industry.value
        agent_cls = _AGENT_REGISTRY.get(industry)
        if agent_cls is None:
            yield {
                "event": "agent.thinking",
                "industry": industry,
                "step": "skipped",
                "message": f"No agent registered for {industry} — skipping",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            continue

        agent = agent_cls(stream_callback=_stream_callback)
        input_msg = _make_input_msg(storm, impact.severity.value)
        agent_tasks.append(asyncio.create_task(agent.run_async(input_msg)))

    # Step 3: Parallel fan-out — drain event queue while agents run
    while True:
        all_done = all(t.done() for t in agent_tasks)

        while not event_queue.empty():
            yield event_queue.get_nowait()

        if all_done:
            break
        await asyncio.sleep(0.05)

    # Final drain
    while not event_queue.empty():
        yield event_queue.get_nowait()

    # Step 4: Collect results
    advisories = []
    for task in agent_tasks:
        try:
            result_msg = task.result()
            adv_data = _extract_advisory(result_msg)
            if adv_data:
                advisories.append(adv_data)
                yield {
                    "event": "advisory.generated",
                    "industry": adv_data.get("industry"),
                    "advisory_id": adv_data.get("advisory_id"),
                    "severity": adv_data.get("severity"),
                    "confidence": adv_data.get("confidence_score"),
                    "data": adv_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as exc:
            yield {
                "event": "agent.error",
                "message": f"Agent task failed: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # Step 5: Pipeline complete
    yield {
        "event": "pipeline.complete",
        "total_advisories": len(advisories),
        "industries": [a.get("industry") for a in advisories],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def run_pipeline(storm: StormEvent) -> list[AdvisoryOutput]:
    """
    Run full pipeline, return all generated advisories.
    Suitable for replay endpoints and batch processing.
    """
    _prewarm_embedder()

    impacts = route_storm(storm)
    triggered = [i for i in impacts if i.triggered]

    if not triggered:
        return []

    agent_tasks = []
    for impact in triggered:
        industry = impact.industry.value
        agent_cls = _AGENT_REGISTRY.get(industry)
        if agent_cls is None:
            continue
        agent = agent_cls()
        input_msg = _make_input_msg(storm, impact.severity.value)
        agent_tasks.append(agent.run_async(input_msg))

    results = await asyncio.gather(*agent_tasks, return_exceptions=True)

    advisories: list[AdvisoryOutput] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        adv_data = _extract_advisory(r)
        if adv_data:
            try:
                advisories.append(AdvisoryOutput(**adv_data))
            except Exception:
                pass

    return advisories
