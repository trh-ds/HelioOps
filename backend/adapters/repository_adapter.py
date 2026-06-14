"""
InMemoryResultRepository — dict-based result store for hackathon scope.

Future: swap this for PostgresResultRepository or RedisResultRepository
without changing any pipeline or API code.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.ports.repository import ResultRepository


class InMemoryResultRepository(ResultRepository):
    def __init__(self):
        self._results: dict[str, Any] = {}
        self._advisory_index: dict[str, dict] = {}

    def save(self, storm_id: str, result: Any) -> None:
        self._results[storm_id] = result

    def get(self, storm_id: str) -> Optional[Any]:
        return self._results.get(storm_id)

    def get_all(self) -> dict[str, Any]:
        return dict(self._results)

    def save_advisory(self, advisory_id: str, data: dict) -> None:
        self._advisory_index[advisory_id] = data

    def get_advisory(self, advisory_id: str) -> Optional[dict]:
        return self._advisory_index.get(advisory_id)