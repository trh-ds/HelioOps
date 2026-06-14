"""
GenAI advisory and verification adapters.

Wraps the genai.orchestrator and genai.verifier behind port interfaces.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

from backend.logging import get_logger
from backend.ports.advisory import AdvisoryPort, VerificationPort

log = get_logger("backend.adapters.advisory")


class GenAIAdvisoryAdapter(AdvisoryPort):
    async def generate(self, storm: Any) -> list[Any]:
        from genai import run_pipeline
        log.info("advisory_generation_started", storm_id=storm.alert_id)
        try:
            advisories = await run_pipeline(storm)
            log.info("advisory_generation_completed", count=len(advisories))
            return advisories
        except Exception as exc:
            log.error("advisory_generation_failed", error=str(exc))
            raise

    async def stream(self, storm: Any) -> AsyncGenerator[dict, None]:
        from genai import stream_pipeline
        async for event in stream_pipeline(storm):
            yield event


class GenAIVerificationAdapter(VerificationPort):
    def verify(self, advisory: Any, storm_event: dict, impact: dict | None = None) -> tuple[Any, Any]:
        from genai.verifier import verify_advisory
        log.info("verification_started", advisory_id=advisory.advisory_id)
        result = verify_advisory(advisory, storm_event, impact)
        verified, provenance = result
        log.info(
            "verification_completed",
            advisory_id=verified.advisory_id,
            status=verified.verifier.status,
        )
        return result