"""
ResultRepository — abstract interface for pipeline result storage.

Implementations:
  - InMemoryResultRepository: dict-based store (current default, hackathon scope)
  - PostgresResultRepository: future production implementation
  - RedisResultRepository: future caching layer
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class ResultRepository(ABC):
    @abstractmethod
    def save(self, storm_id: str, result: Any) -> None:
        """Persist a pipeline result."""

    @abstractmethod
    def get(self, storm_id: str) -> Optional[Any]:
        """Retrieve a pipeline result by storm ID, or None."""

    @abstractmethod
    def get_all(self) -> dict[str, Any]:
        """Return all stored pipeline results."""

    @abstractmethod
    def save_advisory(self, advisory_id: str, data: dict) -> None:
        """Index an advisory by its ID for fast lookup."""

    @abstractmethod
    def get_advisory(self, advisory_id: str) -> Optional[dict]:
        """Retrieve an advisory by its ID, or None."""