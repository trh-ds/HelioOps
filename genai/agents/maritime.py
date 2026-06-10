"""Maritime industry advisory agent."""

from __future__ import annotations

from typing import Callable, Optional

from genai.agents.base import IndustryAgentBase
from genai.prompts.maritime import MARITIME_KB_QUERY, MARITIME_SYSTEM_PROMPT


class MaritimeAgent(IndustryAgentBase):
    """
    Maritime operations advisory agent.

    Generates advisories grounded in IMO GMDSS 2019 / SOLAS Chapter IV:
    HF distress frequency continuity, AIS degradation, NAVTEX backup.
    """

    def __init__(self, stream_callback: Optional[Callable[[dict], None]] = None):
        super().__init__(
            name="maritime_agent",
            industry="maritime",
            system_prompt=MARITIME_SYSTEM_PROMPT,
            kb_query_template=MARITIME_KB_QUERY,
            stream_callback=stream_callback,
        )
