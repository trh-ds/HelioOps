"""
Concrete adapter implementations for HelioOps ports.

Adapters wrap external systems (cv.detect, ML_after_CV, genai) behind
the port interfaces, keeping the domain layer clean of infrastructure details.
"""

from backend.adapters.detection_adapter import CVDetectionAdapter
from backend.adapters.prediction_adapter import (
    MLPredictionAdapter,
    FallbackPredictionAdapter,
)
from backend.adapters.advisory_adapter import (
    GenAIAdvisoryAdapter,
    GenAIVerificationAdapter,
)
from backend.adapters.repository_adapter import InMemoryResultRepository, SupabaseResultRepository
from backend.adapters.schema_adapter import adapt_storm_event

__all__ = [
    "CVDetectionAdapter",
    "MLPredictionAdapter",
    "FallbackPredictionAdapter",
    "GenAIAdvisoryAdapter",
    "GenAIVerificationAdapter",
    "InMemoryResultRepository",
    "SupabaseResultRepository",
    "adapt_storm_event",
]
