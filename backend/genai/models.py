"""
Pydantic models for the HelioOps GenAI layer.

StormEvent   — input from NOAA detection pipeline
AdvisoryOutput — validated advisory returned to backend
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class GScale(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"


class SeverityTier(str, Enum):
    NONE     = "NONE"
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[self.value]

    def __gt__(self, other: "SeverityTier") -> bool:
        return self.rank > other.rank

    def __lt__(self, other: "SeverityTier") -> bool:
        return self.rank < other.rank

    def __ge__(self, other: "SeverityTier") -> bool:
        return self.rank >= other.rank


class Industry(str, Enum):
    AVIATION = "aviation"
    GRID     = "grid"
    MARITIME = "maritime"
    TELECOM  = "telecom"


class SafetyFlag(str, Enum):
    """Flags appended by the guardrails layer — never by the LLM."""
    SEVERITY_MISMATCH     = "SEVERITY_MISMATCH"      # LLM severity < deterministic matrix
    HALLUCINATION_DETECTED = "HALLUCINATION_DETECTED" # Self-check failed
    LOW_COVERAGE          = "LOW_COVERAGE"            # < 3 chunks above similarity threshold
    LOW_CONFIDENCE        = "LOW_CONFIDENCE"          # confidence_score < 0.5
    CITATION_GAP          = "CITATION_GAP"            # action_item missing source_ref
    GENERATION_FAILED     = "GENERATION_FAILED"       # all retries exhausted → safe fallback


# ── Input Models ──────────────────────────────────────────────────────────────

class StormEvent(BaseModel):
    """Structured storm event parsed from NOAA SWPC alerts."""
    alert_id:                str
    g_scale:                 GScale
    s_scale:                 Optional[str]     = None   # "S1"–"S5" or None
    r_scale:                 Optional[str]     = None   # "R1"–"R5" or None
    kp_index:                float             = Field(..., ge=0.0, le=9.0)
    estimated_arrival_utc:   Optional[datetime] = None
    peak_impact_window_start: Optional[datetime] = None
    peak_impact_window_end:  Optional[datetime] = None
    raw_alert_text:          str
    source_url:              Optional[str]     = None

    @field_validator("kp_index")
    @classmethod
    def round_kp(cls, v: float) -> float:
        return round(v, 1)


# ── RAG Models ────────────────────────────────────────────────────────────────

class RetrievedChunk(BaseModel):
    """Single chunk returned from ChromaDB retrieval."""
    chunk_id:   str
    text:       str
    source:     str              # original PDF/TXT filename
    similarity: float            # cosine similarity 0–1 (computed from L2 distance)
    metadata:   Dict[str, Any] = Field(default_factory=dict)


# ── Advisory Models ───────────────────────────────────────────────────────────

class ActionItem(BaseModel):
    """A single numbered action in an advisory."""
    step:                 int    = Field(..., ge=1)
    action:               str    = Field(..., min_length=10)
    rationale:            str    = Field(..., min_length=10)
    source_ref:           Optional[str] = None  # document name or regulation code
    time_window:          Optional[str] = None  # e.g. "T+0 to T+2h", "Within 30 min"


class AdvisoryOutput(BaseModel):
    """
    Final validated advisory output, suitable for storage in the backend DB
    (advisory_json column) and dispatch via WebSocket + notifications.
    """
    advisory_id:           str             = Field(default_factory=lambda: str(uuid.uuid4()))
    storm_event_id:        str
    industry:              Industry
    severity:              SeverityTier
    confidence_score:      float           = Field(default=0.0, ge=0.0, le=1.0)
    summary:               str
    action_items:          List[ActionItem]
    estimated_impact_window: Optional[str] = None
    sources_cited:         List[str]       = Field(default_factory=list)
    validation_passed:     bool            = False
    generated_at:          datetime        = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_used:            str             = ""
    # Guardrail metadata — set by system, never by LLM
    safety_flags:          List[SafetyFlag] = Field(default_factory=list)
    generation_errors:     List[str]        = Field(default_factory=list)


# ── Routing Models ────────────────────────────────────────────────────────────

class IndustryImpact(BaseModel):
    """Result of deterministic routing for one industry."""
    industry: Industry
    severity: SeverityTier
    triggered: bool          # False means no advisory needed (NONE severity)


# ── Stream Events ─────────────────────────────────────────────────────────────

class StreamEvent(BaseModel):
    """Event emitted during pipeline execution for WebSocket streaming."""
    event:     str            # e.g. "agent.thinking", "advisory.ready", "pipeline.complete"
    industry:  Optional[str]  = None
    step:      Optional[str]  = None
    message:   Optional[str]  = None
    data:      Optional[dict] = None
    timestamp: str            = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── LLM Raw Output Schema (what the LLM generates, pre-validation) ────────────

class LLMActionItem(BaseModel):
    """Raw action item from LLM before validation."""
    step:        int
    action:      str
    rationale:   str
    source_ref:  Optional[str] = None
    time_window: Optional[str] = None


class LLMAdvisoryOutput(BaseModel):
    """
    Strict schema the LLM must output in JSON mode.
    Fields like confidence_score are NOT here — they're computed by the system.
    """
    storm_event_id:          str
    industry:                str
    severity:                str
    summary:                 str
    action_items:            List[LLMActionItem]
    estimated_impact_window: Optional[str] = None
    sources_cited:           List[str]     = Field(default_factory=list)
