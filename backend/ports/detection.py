"""
DetectionPort — abstract interface for storm detection.

Implementations:
  - CVDetectionAdapter: wraps cv.detect for cached/stub replay
  - LiveDetectionAdapter: wraps cv.detect_live for real-time API mode
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DetectionPort(ABC):
    @abstractmethod
    def detect(self, storm_id: str, base_dir: str = ".") -> Any:
        """Return a StormEvent model for the given storm ID."""

    @abstractmethod
    def available_storm_ids(self) -> list[str]:
        """Return the list of discoverable storm IDs."""