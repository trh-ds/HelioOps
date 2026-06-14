"""
AdvisoryPort & VerificationPort — abstract interfaces for GenAI layer.

Implementations:
  - GenAIAdvisoryAdapter: wraps genai.orchestrator for full advisory generation
  - GenAIVerificationAdapter: wraps genai.verifier for deterministic rule checks
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class AdvisoryPort(ABC):
    @abstractmethod
    async def generate(self, storm: Any) -> list[Any]:
        """Generate advisories for all triggered industries."""

    @abstractmethod
    async def stream(self, storm: Any) -> AsyncGenerator[dict, None]:
        """Stream advisory generation events for WebSocket clients."""


class VerificationPort(ABC):
    @abstractmethod
    def verify(self, advisory: Any, storm_event: dict, impact: dict | None = None) -> tuple[Any, Any]:
        """Verify an advisory against deterministic rulebooks.

        Returns (VerifiedAdvisory, ProvenanceTrace).
        """