"""
CVDetectionAdapter — wraps cv.detect behind the DetectionPort interface.

Decouples the pipeline from the cv module's internal structure.
If cv.detect.detect() changes signature, only this adapter needs updating.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.logging import get_logger
from backend.ports.detection import DetectionPort

log = get_logger("backend.adapters.detection")


class CVDetectionAdapter(DetectionPort):
    def __init__(self, available_storm_ids: list[str] | None = None):
        self._storm_ids = available_storm_ids or ["2024-10-G4", "2024-05-G5"]

    def detect(self, storm_id: str, base_dir: str = ".") -> Any:
        from cv.detect import detect
        log.info("detection_started", storm_id=storm_id)
        try:
            result = detect(storm_id, base_dir)
            log.info("detection_completed", storm_id=storm_id, confidence=result.confidence)
            return result
        except Exception as exc:
            log.error("detection_failed", storm_id=storm_id, error=str(exc))
            raise

    async def detect_async(self, storm_id: str, base_dir: str = ".") -> Any:
        return await asyncio.to_thread(self.detect, storm_id, base_dir)

    def available_storm_ids(self) -> list[str]:
        return list(self._storm_ids)