"""
Orchestration for HelioOps advisory generation.

Parallel fan-out via asyncio.gather.

Pipeline topology:
  1. RouterAgent     — deterministic G-scale routing (no LLM)
  2. IndustryAgents  — parallel fan-out to triggered industries
  3. CompilerAgent   — fan-in: collects all advisories
  4. VerifierAgent   — deterministic rule checks (Phase 5)

Usage:
  # Streaming (for WebSocket events):
  async for event in stream_pipeline(storm):
      await ws_manager.broadcast_all(event)

  # Batch (for replay / testing):
  advisories = await run_pipeline(storm)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from backend.genai.agents.aviation import AviationAgent
from backend.genai.agents.grid import GridAgent
from backend.genai.agents.maritime import MaritimeAgent
from backend.genai.agents.telecom import TelecomAgent
from backend.genai.config import GENAI_MAX_CONCURRENCY
from backend.genai.impact_router import route_storm
from backend.genai.models import AdvisoryOutput, StormEvent

log = logging.getLogger(__name__)


async def _run_bounded(agent, storm: StormEvent, severity: str, sem: asyncio.Semaphore) -> dict:
    """
    Run one agent while holding a slot in the concurrency semaphore.

    Firing all four industries at once put ~26k tokens into a 8k/min window in
    one burst, so the last agents in were guaranteed to hit a 429. The token
    bucket in genai/llm.py would absorb that by stalling, but bounding fan-out
    here keeps each burst small enough that it mostly never has to.
    """
    async with sem:
        return await agent.run_async(storm, severity)


def _prewarm_embedder() -> None:
    """Build the shared singletons once, on the main thread, before fan-out.

    Both are touched from worker threads via asyncio.to_thread, and both fail
    confusingly when several threads initialise them at once:
      - embedder: 'Cannot copy out of meta tensor' from PyTorch
      - chroma:   'Could not connect to tenant default_tenant', which surfaces
                  as an advisory with no retrieved context at all
    Each is also individually lock-guarded; this just keeps the happy path off
    the contended route.
    """
    from backend.embeddings.collections import get_client
    from backend.embeddings.embedder import _get_model

    _get_model()
    get_client()

# ── Agent registry ────────────────────────────────────────────────────────────
# Maps industry name → agent class.

_AGENT_REGISTRY: dict[str, type] = {
    "aviation": AviationAgent,
    "grid":     GridAgent,
    "maritime": MaritimeAgent,
    "telecom":  TelecomAgent,
}


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
    sem = asyncio.Semaphore(GENAI_MAX_CONCURRENCY)
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
        agent_tasks.append(
            asyncio.create_task(_run_bounded(agent, storm, impact.severity.value, sem))
        )

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
            advisory = task.result()["advisory"]
            adv_data = advisory.model_dump(mode="json")
            advisories.append(adv_data)
            yield {
                "event": "advisory.generated",
                "industry": adv_data["industry"],
                "advisory_id": adv_data["advisory_id"],
                "severity": adv_data["severity"],
                "confidence": adv_data["confidence_score"],
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

    sem = asyncio.Semaphore(GENAI_MAX_CONCURRENCY)
    agent_tasks = []
    for impact in triggered:
        industry = impact.industry.value
        agent_cls = _AGENT_REGISTRY.get(industry)
        if agent_cls is None:
            continue
        agent = agent_cls()
        agent_tasks.append(_run_bounded(agent, storm, impact.severity.value, sem))

    results = await asyncio.gather(*agent_tasks, return_exceptions=True)

    advisories: list[AdvisoryOutput] = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("Agent task failed: %s", r)
            continue
        advisories.append(r["advisory"])

    return advisories
