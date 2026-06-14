"""
Port definitions — abstract interfaces that the domain layer depends on.

Each port defines a contract. Adapters provide concrete implementations.
The pipeline and API layer depend on these ports, never on adapters directly.
"""

from backend.ports.detection import DetectionPort
from backend.ports.prediction import PredictionPort
from backend.advisory import AdvisoryPort, VerificationPort
from backend.ports.repository import ResultRepository

__all__ = [
    "DetectionPort",
    "PredictionPort",
    "AdvisoryPort",
    "VerificationPort",
    "ResultRepository",
]