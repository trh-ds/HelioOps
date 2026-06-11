"""Power grid industry advisory agent."""

from __future__ import annotations

from typing import Callable, Optional

from genai.agents.base import IndustryAgentBase
from genai.prompts.grid import GRID_KB_QUERY, GRID_SYSTEM_PROMPT


class GridAgent(IndustryAgentBase):
    """
    Power grid operations advisory agent.

    Generates advisories grounded in NERC GMD standards (TPL-007-4):
    GIC monitoring, transformer thermal protection, reactive power reserves.
    """

    def __init__(self, stream_callback: Optional[Callable[[dict], None]] = None):
        super().__init__(
            name="grid_agent",
            industry="grid",
            system_prompt=GRID_SYSTEM_PROMPT,
            kb_query_template=GRID_KB_QUERY,
            stream_callback=stream_callback,
        )
