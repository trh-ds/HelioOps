"""
CVDetectionAdapter — wraps cv.storm_event_generator.detect behind a stable interface.

Decouples the pipeline from the cv module's internal structure.
If cv.storm_event_generator.detect.detect() changes signature, only this adapter needs updating.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.logging import get_logger

log = get_logger("backend.adapters.detection")


class CVDetectionAdapter:
    def __init__(self, available_storm_ids: list[str] | None = None):
        self._storm_ids = available_storm_ids or ["2024-10-G4", "2024-05-G5"]

    def detect(self, storm_id: str, base_dir: str | None = None) -> Any:
        from backend.cv.storm_event_generator.detect import detect

        log.info("detection_started", storm_id=storm_id)
        try:
            result = detect(storm_id, base_dir)
            log.info(
                "detection_completed", storm_id=storm_id, confidence=result.confidence
            )
            return result
        except Exception as exc:
            log.error("detection_failed", storm_id=storm_id, error=str(exc))
            raise

    async def detect_async(self, storm_id: str, base_dir: str | None = None) -> Any:
        return await asyncio.to_thread(self.detect, storm_id, base_dir)

    def available_storm_ids(self) -> list[str]:
        return list(self._storm_ids)
