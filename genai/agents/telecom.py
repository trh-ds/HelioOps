"""Telecom / NOC industry advisory agent."""

from __future__ import annotations

from typing import Callable, Optional

from genai.agents.base import IndustryAgentBase
from genai.prompts.telecom import TELECOM_KB_QUERY, TELECOM_SYSTEM_PROMPT


class TelecomAgent(IndustryAgentBase):
    """
    Telecom NOC advisory agent.

    Generates advisories grounded in ITU-R / NESDIS:
    GPS L1 degradation, satellite uplink fade, GNSS integrity monitoring.
    """

    def __init__(self, stream_callback: Optional[Callable[[dict], None]] = None):
        super().__init__(
            name="telecom_agent",
            industry="telecom",
            system_prompt=TELECOM_SYSTEM_PROMPT,
            kb_query_template=TELECOM_KB_QUERY,
            stream_callback=stream_callback,
        )
