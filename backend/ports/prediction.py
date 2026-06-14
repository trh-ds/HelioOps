"""
PredictionPort — abstract interface for ML impact prediction.

Implementations:
  - MLPredictionAdapter: wraps ML_after_CV.inference for LightGBM quantile regression
  - FallbackPredictionAdapter: returns conservative defaults when models unavailable
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PredictionPort(ABC):
    @abstractmethod
    def predict(self, storm_dict: dict) -> Any:
        """Return an ImpactPrediction from storm event features."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if model checkpoints are loaded and ready."""