"""Aviation industry advisory agent."""

from __future__ import annotations

from typing import Callable, Optional

from genai.agents.base import IndustryAgentBase
from genai.prompts.aviation import AVIATION_KB_QUERY, AVIATION_SYSTEM_PROMPT


class AviationAgent(IndustryAgentBase):
    """
    Aviation operations advisory agent.

    Generates advisories grounded in ICAO NAT Doc 007 procedures:
    HF radio backup, polar route deviation, GPS degradation, crew briefing.
    """

    def __init__(self, stream_callback: Optional[Callable[[dict], None]] = None):
        super().__init__(
            name="aviation_agent",
            industry="aviation",
            system_prompt=AVIATION_SYSTEM_PROMPT,
            kb_query_template=AVIATION_KB_QUERY,
            stream_callback=stream_callback,
        )
