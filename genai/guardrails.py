"""
Guardrails layer for the HelioOps GenAI advisories.

Anti-hallucination techniques implemented here:

  1.  JSON Schema Enforcement   — Pydantic strict validation of LLM output
  2.  JSON Extraction Fallback  — Handles markdown fences, trailing text
  3.  Severity Consistency      — LLM severity cannot be lower than deterministic matrix
  4.  Citation Coverage         — source_ref must match a retrieved chunk source
  5.  Source Existence Check    — Every cited source in sources_cited must appear in chunks
  6.  LLM Self-Check            — Separate LLM call judges if claims are grounded in context
  7.  Confidence Scoring        — Multi-factor score combining RAG quality + citation quality
  8.  Safety Flag Application   — Append SafetyFlag values without blocking delivery
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from genai.config import (
    CITATION_BONUS,
    CITATION_PENALTY,
    COVERAGE_BONUS,
    GROQ_API_KEY,
    GROQ_CHECKER_MODEL,
    GROQ_MAX_TOKENS,
    LOW_CONFIDENCE_THRESHOLD,
    RAG_LOW_COVERAGE_THRESHOLD,
    SELF_CHECK_MAX_CHUNKS,
)
from genai.models import (
    ActionItem,
    AdvisoryOutput,
    Industry,
    LLMAdvisoryOutput,
    RetrievedChunk,
    SafetyFlag,
    SeverityTier,
)


# ── JSON Extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """
    Extract the first JSON object from a string.
    Handles:
      - Bare JSON
      - Markdown fenced JSON (```json ... ```)
      - JSON preceded/followed by prose
    """
    # Strip markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1)

    # Find first { … } block
    start = raw.find("{")
    if start == -1:
        return raw  # let Pydantic produce the error

    # Find matching closing brace
    depth = 0
    for i, ch in enumerate(raw[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]

    return raw[start:]  # truncated JSON — will fail parsing, triggers retry


# ── Schema Validation ─────────────────────────────────────────────────────────

def validate_advisory_schema(
    raw_json: str,
    industry: str,
    storm_event_id: str,
    expected_severity: str,
) -> tuple[Optional[AdvisoryOutput], list[str]]:
    """
    Parse and validate LLM JSON output against the AdvisoryOutput schema.

    Returns:
        (AdvisoryOutput, [])              — on success
        (None, ["error1", "error2", ...]) — on failure
    """
    errors: list[str] = []

    # Step 1: Extract JSON
    try:
        json_str = _extract_json(raw_json)
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        errors.append(f"JSON parse error: {exc.msg} at position {exc.pos}")
        return None, errors

    # Step 2: Validate against LLMAdvisoryOutput (LLM-generated fields only)
    try:
        llm_out = LLMAdvisoryOutput(**data)
    except Exception as exc:
        # Pydantic v2 validation error → collect field-level messages
        for e in getattr(exc, "errors", lambda: [{"msg": str(exc)}])():
            errors.append(f"Schema: {'.'.join(str(x) for x in e.get('loc', []))} — {e['msg']}")
        return None, errors

    # Step 3: Check action_items have source_ref
    missing_refs = [
        f"action_items[{i}].source_ref"
        for i, item in enumerate(llm_out.action_items)
        if not item.source_ref or len(item.source_ref.strip()) < 3
    ]
    if missing_refs:
        errors.append(f"Missing source_ref on: {', '.join(missing_refs)}")
        return None, errors

    # Step 4: sources_cited must not be empty
    if not llm_out.sources_cited:
        errors.append("sources_cited list is empty — every advisory must cite at least one source")
        return None, errors

    # Step 5: Build AdvisoryOutput (system fields added here)
    try:
        advisory = AdvisoryOutput(
            advisory_id=str(uuid.uuid4()),
            storm_event_id=storm_event_id,
            industry=Industry(llm_out.industry),
            severity=SeverityTier(llm_out.severity),
            summary=llm_out.summary,
            action_items=[
                ActionItem(
                    step=a.step,
                    action=a.action,
                    rationale=a.rationale,
                    source_ref=a.source_ref,
                    time_window=a.time_window,
                )
                for a in llm_out.action_items
            ],
            estimated_impact_window=llm_out.estimated_impact_window,
            sources_cited=llm_out.sources_cited,
            validation_passed=True,
            generated_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        errors.append(f"AdvisoryOutput construction: {exc}")
        return None, errors

    return advisory, []


# ── Severity Consistency ──────────────────────────────────────────────────────

def check_severity_consistency(
    advisory: AdvisoryOutput,
    minimum_severity: str,
) -> tuple[bool, str]:
    """
    Verify the LLM-assigned severity is not below the deterministic matrix minimum.

    Returns:
        (True, "")      — consistent
        (False, note)   — LLM under-reported severity; note describes the issue
    """
    llm_sev  = advisory.severity
    min_sev  = SeverityTier(minimum_severity)

    if llm_sev < min_sev:
        note = (
            f"Severity mismatch: LLM output '{llm_sev.value}' but deterministic "
            f"matrix requires minimum '{min_sev.value}' for this industry and storm scale. "
            f"Advisory flagged; severity was NOT overridden (human review required)."
        )
        return False, note

    return True, ""


# ── Citation & Source Validation ──────────────────────────────────────────────

def validate_citations(
    advisory: AdvisoryOutput,
    retrieved_chunks: list[RetrievedChunk],
) -> list[SafetyFlag]:
    """
    Cross-check source_refs in action_items against the set of retrieved chunk sources.

    If an action item cites a source not present in any retrieved chunk, it is
    flagged as a potential hallucination. The advisory is not blocked, but
    CITATION_GAP is appended to safety_flags.
    """
    flags: list[SafetyFlag] = []
    known_sources = {c.source.lower() for c in retrieved_chunks}
    known_ids     = {c.chunk_id for c in retrieved_chunks}

    has_gap = False
    for item in advisory.action_items:
        ref = (item.source_ref or "").lower().strip()
        if not ref:
            has_gap = True
            continue
        # Accept if ref is a chunk_id OR if ref appears as a substring of any known source name
        ref_found = (
            ref in known_ids
            or any(ref in src or src in ref for src in known_sources)
        )
        if not ref_found:
            has_gap = True

    if has_gap:
        flags.append(SafetyFlag.CITATION_GAP)

    return flags


# ── LLM Self-Check ────────────────────────────────────────────────────────────

_SELF_CHECK_SYSTEM = """You are an impartial audit assistant checking an AI-generated operations advisory for hallucinations.

Your task: determine if any action items make specific factual claims that CANNOT be verified from the provided context.

WHAT TO FLAG (potential hallucinations):
- Specific numbers (frequencies in kHz/MHz, distance thresholds in km/nm, voltage limits, flux thresholds) that do NOT appear in the context
- Regulation codes or standard names (e.g. NERC TPL-007-4, ICAO Annex 2) that are NOT mentioned in the context
- Named procedures or protocols that are NOT described in the context

WHAT NOT TO FLAG:
- General operational reasoning that logically follows from the context
- Severity levels consistent with the stated storm scale
- Time window estimates based on the provided storm arrival time
- Standard industry terminology without specific numeric claims

Respond with ONLY valid JSON matching this exact schema:
{
  "hallucinations_found": false,
  "issues": [],
  "verdict_confidence": 0.9
}
Where "issues" is a list of strings describing specific problems found.
"""


async def self_check_hallucination(
    advisory: AdvisoryOutput,
    context_chunks: list[RetrievedChunk],
    llm: ChatGroq,
) -> tuple[bool, str]:
    """
    Run a lightweight LLM self-check to detect potential hallucinations.

    Uses a separate LLM call with a curated subset of context (SELF_CHECK_MAX_CHUNKS)
    to keep latency low.

    Returns:
        (True, "")          — no hallucinations detected
        (False, "reason")   — potential hallucination found
    """
    # Use only the top-N most similar chunks to keep the check fast
    top_chunks = sorted(context_chunks, key=lambda c: c.similarity, reverse=True)[
        :SELF_CHECK_MAX_CHUNKS
    ]
    context_text = "\n\n".join(
        f"[{c.source}]\n{c.text}" for c in top_chunks
    )

    action_summary = "\n".join(
        f"Step {a.step}: {a.action} (source_ref: {a.source_ref or 'NONE'})"
        for a in advisory.action_items
    )

    human_msg = f"""=== ADVISORY TO AUDIT ===
Industry: {advisory.industry.value}
Severity: {advisory.severity.value}
Summary: {advisory.summary}

Action Items:
{action_summary}

=== CONTEXT PROVIDED TO THE ADVISORY GENERATOR ===
{context_text}

Audit the advisory against the context and return JSON."""

    try:
        checker_llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_CHECKER_MODEL,
            temperature=0.0,
            max_tokens=512,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = await checker_llm.ainvoke([
            SystemMessage(content=_SELF_CHECK_SYSTEM),
            HumanMessage(content=human_msg),
        ])
        result = json.loads(_extract_json(response.content))
        if result.get("hallucinations_found", False):
            issues = result.get("issues", ["unspecified issues"])
            return False, "; ".join(issues[:3])
        return True, ""
    except Exception as exc:
        # Self-check failure must not block advisory delivery
        return True, f"self-check skipped: {exc}"


# ── Confidence Scoring ────────────────────────────────────────────────────────

def compute_confidence_score(
    advisory: AdvisoryOutput,
    chunks: list[RetrievedChunk],
    context_quality: float,
) -> float:
    """
    Multi-factor confidence score [0.0, 1.0].

    Factors:
      - Base score:       average cosine similarity of all retrieved chunks
      - Citation bonus:   +CITATION_BONUS per action item with a valid source_ref
      - Citation penalty: -CITATION_PENALTY per action item missing source_ref
      - Coverage bonus:   +COVERAGE_BONUS if context_quality > 0.6
    """
    score = context_quality  # base: retrieval quality

    known_sources = {c.source.lower() for c in chunks}
    known_ids     = {c.chunk_id for c in chunks}

    for item in advisory.action_items:
        ref = (item.source_ref or "").lower().strip()
        if ref and (
            ref in known_ids
            or any(ref in src or src in ref for src in known_sources)
        ):
            score += CITATION_BONUS
        else:
            score -= CITATION_PENALTY

    if context_quality > 0.6:
        score += COVERAGE_BONUS

    return round(max(0.0, min(1.0, score)), 4)


# ── Safety Flag Application ───────────────────────────────────────────────────

def apply_safety_flags(
    advisory: AdvisoryOutput,
    chunks: list[RetrievedChunk],
    context_quality: float,
) -> AdvisoryOutput:
    """
    Append appropriate SafetyFlag values to the advisory based on quality checks.
    Does NOT block the advisory — flags are informational for human reviewers.
    """
    flags = list(advisory.safety_flags)

    # LOW_COVERAGE: too few chunks above similarity threshold
    if len(chunks) < RAG_LOW_COVERAGE_THRESHOLD:
        flags.append(SafetyFlag.LOW_COVERAGE)

    # LOW_CONFIDENCE: final confidence score is low
    if advisory.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        flags.append(SafetyFlag.LOW_CONFIDENCE)

    # CITATION_GAP: action items cite unknown sources
    citation_flags = validate_citations(advisory, chunks)
    flags.extend(citation_flags)

    # Deduplicate
    advisory.safety_flags = list(dict.fromkeys(flags))
    return advisory
