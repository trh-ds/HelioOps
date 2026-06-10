"""
Data contracts for Layer ③ → Layer ④ integration.

These Pydantic models match the frozen contracts in imp.md §7.2–7.4.
Tirth's delivery layer consumes VerifiedAdvisory + ProvenanceTrace.
"""

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── §7.2 ImpactAssessment (Neal produces, Priyanshu consumes) ────────────────

class ImpactMetric(BaseModel):
    """Single impact metric from Neal's model."""
    domain: str                        # gps_pnt, hf_radio, grid_gic
    metric: str                        # l1_position_error_m, blackout_probability, gic_risk_index
    value: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    ci_level: Optional[float] = None   # e.g. 0.95
    qualifier: Optional[str] = None    # e.g. "worsening above 60N"
    # Optional domain-specific fields
    band_mhz: Optional[float] = None
    route: Optional[str] = None
    zone: Optional[str] = None
    scale_max: Optional[float] = None
    source: Optional[str] = None       # "model" or "rule_based"


class ImpactAssessment(BaseModel):
    """Stub matching imp.md §7.2. Neal produces this; Priyanshu consumes it."""
    storm_id: str
    model_version: str = "impact-v0.3-frozen"
    low_confidence: bool = False
    source: str = "model"              # "model" or "severity_floor"
    impacts: list[ImpactMetric] = Field(default_factory=list)


# ── §7.3 VerifiedAdvisory (Priyanshu produces, Tirth consumes) ──────────────

class VerifierCheck(BaseModel):
    """Single rule check performed by the deterministic verifier."""
    field: str                         # hf_band, reroute_latitude, gic_step, gmdss_channel
    proposed: Any                      # what the LLM wrote
    status: Literal["pass", "blocked"]
    corrected_to: Optional[Any] = None # filled only when status="blocked"
    reason: Optional[str] = None


class VerifierResult(BaseModel):
    """Aggregate verifier outcome for one advisory."""
    status: Literal["passed", "passed_with_corrections", "blocked"]
    checks: list[VerifierCheck] = Field(default_factory=list)


class VerifiedAdvisory(BaseModel):
    """
    Post-verification advisory matching imp.md §7.3.
    This is what Tirth's Layer ④ stores and dispatches.
    """
    advisory_id: str
    storm_id: str
    industry: str                      # aviation, grid, maritime, telecom
    severity: str                      # critical, high, medium, low
    numbered_actions: list[str]        # plain-text action strings
    timing_window: dict                # {"opens": ISO8601, "duration_min": int}
    technical_details: str
    cited_procedure: dict              # {"source": str, "ref": str}
    verifier: VerifierResult
    provenance_ref: str                # trace_id linking to ProvenanceTrace
    requires_human: bool = False


# ── §7.4 ProvenanceTrace (Priyanshu produces, Tirth renders) ────────────────

class ProvenanceStep(BaseModel):
    """Single step in the 6-step provenance chain."""
    step: str                          # raw_data, detection, impact, retrieval, verifier, output
    ref: str                           # human-readable reference
    confidence: Optional[float] = None
    ci_level: Optional[float] = None


class ProvenanceTrace(BaseModel):
    """
    Full provenance chain matching imp.md §7.4.
    Links raw data → detection → impact → retrieval → verifier → output.
    """
    trace_id: str
    advisory_id: str
    chain: list[ProvenanceStep] = Field(default_factory=list)
