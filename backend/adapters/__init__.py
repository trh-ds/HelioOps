"""
Concrete adapter implementations for HelioOps ports.

Adapters wrap external systems (cv.detect, ML_after_CV, genai) behind
the port interfaces, keeping the domain layer clean of infrastructure details.
"""

from backend.adapters.detection_adapter import CVDetectionAdapter
from backend.adapters.prediction_adapter import MLPredictionAdapter, FallbackPredictionAdapter
from backend.adapters.advisory_adapter import GenAIAdvisoryAdapter, GenAIVerificationAdapter
from backend.adapters.repository_adapter import InMemoryResultRepository
from backend.adapters.schema_adapter import SchemaAdapter

__all__ = [
    "CVDetectionAdapter",
    "MLPredictionAdapter",
    "FallbackPredictionAdapter",
    "GenAIAdvisoryAdapter",
    "GenAIVerificationAdapter",
    "InMemoryResultRepository",
    "SchemaAdapter",
]