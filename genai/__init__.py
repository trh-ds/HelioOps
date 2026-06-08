"""
HelioOps GenAI layer.

Public API:
    stream_pipeline(storm: StormEvent) -> AsyncGenerator[dict, None]
    run_pipeline(storm: StormEvent) -> list[AdvisoryOutput]
"""

from genai.graph import run_pipeline, stream_pipeline
from genai.models import AdvisoryOutput, StormEvent

__all__ = ["run_pipeline", "stream_pipeline", "StormEvent", "AdvisoryOutput"]
