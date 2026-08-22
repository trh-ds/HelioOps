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
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.genai.config import (
    CITATION_BONUS,
    CITATION_PENALTY,
    COVERAGE_BONUS,
    GROQ_CHECKER_MAX_TOKENS,
    GROQ_CHECKER_MODEL,
    LOW_CONFIDENCE_THRESHOLD,
    MIN_ACTION_ITEMS,
    RAG_LOW_COVERAGE_THRESHOLD,
    MAX_CONTEXT_TOKENS,
    SELF_CHECK_MAX_CHUNKS,  # noqa: F401 — retained as a config knob
)
from backend.genai.llm import complete_json
from backend.genai.models import (
    ActionItem,
    AdvisoryOutput,
    Industry,
    LLMAdvisoryOutput,
    RetrievedChunk,
    SafetyFlag,
    SeverityTier,
)

log = logging.getLogger(__name__)


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
        detail = exc.errors() if hasattr(exc, "errors") else [{"msg": str(exc)}]
        for e in detail:
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

    # Step 3b: reject the no-context placeholder used as a real action.
    # The prompt tells the model to emit it when nothing was retrieved, but it
    # also reaches for it mid-advisory when a step is not covered by the
    # context — shipping "SOURCE UNAVAILABLE — consult a specialist" as an
    # operational instruction. Retrying produces a grounded step instead.
    placeholder_actions = [
        f"action_items[{i}].action"
        for i, item in enumerate(llm_out.action_items)
        if any(m in item.action.lower() for m in ("source unavailable", "no source"))
    ]
    if placeholder_actions:
        errors.append(
            f"Placeholder text used as an action on: {', '.join(placeholder_actions)}. "
            "Every action must be a concrete instruction grounded in the context."
        )
        return None, errors

    # Step 3c: an advisory needs enough steps to be operationally useful.
    if len(llm_out.action_items) < MIN_ACTION_ITEMS:
        errors.append(
            f"Only {len(llm_out.action_items)} action_items — at least "
            f"{MIN_ACTION_ITEMS} are required, ordered by urgency."
        )
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
            f"matrix requires minimum '{min_sev.value}' for this industry and storm scale."
        )
        return False, note

    return True, ""


# ── Citation matching ─────────────────────────────────────────────────────────
#
# Matching used to be `ref in src or src in ref` on lowercased strings, which
# only ever matched a citation that reproduced the filename verbatim. Models
# cite the way a human would — "ITU-R M.541", "NERC TPL-007-4", "ICAO NAT Doc
# 007" — and every one of those was scored as a CITATION_GAP against
# itu_r_m541_dsc_operational_procedures.pdf, nerc_tpl007_4.pdf and
# nat_doc_007_2025.pdf. It also docked confidence via CITATION_PENALTY, so
# correctly-cited advisories were penalised for citing correctly. That became
# much more visible once the maritime and telecom corpora turned into ITU-R
# documents whose names are all standard designators.
#
# The match is on the designator (a letter-run followed by a digit-run, so
# "M.541", "m541" and "M.541-11" all reduce to m541), falling back to shared
# words for sources with no designator at all, like
# noaa_space_weather_scales.txt.

_CITATION_STOPWORDS = {"pdf", "txt", "the", "and", "for", "doc", "itu", "rec"}


def _citation_tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _designators(text: str) -> set[str]:
    """Standard identifiers: m541, p618, tpl007, doc007 …"""
    tokens = _citation_tokens(text)
    found: set[str] = set()
    for token in tokens:
        # embedded runs, e.g. "m541" or "tpl0074"
        for m in re.finditer(r"([a-z]+)(\d+)", token):
            found.add(m.group(1) + m.group(2))
    for left, right in zip(tokens, tokens[1:]):
        # separated runs, e.g. "TPL" "007"
        if left.isalpha() and right.isdigit():
            found.add(left + right)
    return found


def _significant_words(text: str) -> set[str]:
    return {
        t for t in _citation_tokens(text)
        if len(t) >= 3 and not t.isdigit() and t not in _CITATION_STOPWORDS
    }


# The prompt tells the model to emit this when no context was retrieved, so it
# arrives as a source_ref like any other. It must never count as a citation —
# and it very nearly did: it shares "space" and "weather" with
# noaa_space_weather_scales.txt, which was enough for a word-overlap match.
_NON_CITATIONS = ("source unavailable", "not available", "no source", "n/a", "unknown")

# Word-overlap is the fallback for sources with no designator. Three shared
# words is the bar: two lets loosely-related prose match, as the placeholder
# above demonstrated.
_MIN_SHARED_WORDS = 3


def citation_matches(ref: str, source: str) -> bool:
    """True if `ref` plausibly names `source`."""
    if not ref or not source:
        return False
    if any(marker in ref.lower() for marker in _NON_CITATIONS):
        return False
    ref_ids, src_ids = _designators(ref), _designators(source)
    if ref_ids & src_ids:
        return True
    if ref_ids and src_ids:
        # Both name a standard, and they are different ones. "NERC TPL-999-9"
        # must not match nerc_tpl007_4.pdf just because both say NERC.
        return False
    return len(_significant_words(ref) & _significant_words(source)) >= _MIN_SHARED_WORDS


def citation_is_grounded(ref: Optional[str], chunks: list[RetrievedChunk]) -> bool:
    """True if the citation resolves to a chunk that was actually retrieved."""
    ref = (ref or "").strip()
    if not ref:
        return False
    if any(ref == c.chunk_id for c in chunks):
        return True
    return any(citation_matches(ref, c.source) for c in chunks)


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

    has_gap = any(
        not citation_is_grounded(item.source_ref, retrieved_chunks)
        for item in advisory.action_items
    )

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


def build_self_check_context(
    context_chunks: list[RetrievedChunk],
) -> tuple[str, int]:
    """
    Render the evidence the auditor judges against, plus how many chunks fit.

    The auditor must see everything the generator saw. This previously took the
    top SELF_CHECK_MAX_CHUNKS and truncated to MAX_CONTEXT_TOKENS * 2 chars,
    then `break` on the first chunk that did not fit — which, measured on the
    G5 aviation advisory, meant auditing against 1 of 5 chunks, 35% of the
    generator's context.

    An auditor shown a third of the evidence flags grounded claims as
    unsupported, and it did: HALLUCINATION_DETECTED fired on nearly every
    advisory in every run, which makes the flag worthless — a signal that is
    always on carries no information. It was also costing a full regeneration
    per advisory back when the self-check still blocked.

    Budget is 4 chars/token against the *same* context budget the generator
    had. The checker runs on its own model and therefore its own TPM bucket, so
    this costs nothing the advisory needed.
    """
    ordered = sorted(context_chunks, key=lambda c: c.similarity, reverse=True)
    max_chars = MAX_CONTEXT_TOKENS * 4
    parts: list[str] = []
    total = 0
    for chunk in ordered:
        part = f"[{chunk.source}]\n{chunk.text}"
        if total + len(part) > max_chars:
            continue  # skip one oversized chunk, keep the rest
        parts.append(part)
        total += len(part)
    return "\n\n".join(parts), len(parts)


async def self_check_hallucination(
    advisory: AdvisoryOutput,
    context_chunks: list[RetrievedChunk],
) -> tuple[bool, str]:
    """
    Run a lightweight LLM self-check to detect potential hallucinations.

    Uses a separate LLM call, on a different model, over the same context the
    generator saw.

    Returns:
        (True, "")          — no hallucinations detected
        (False, "reason")   — potential hallucination found
    """
    # The auditor must see everything the generator saw. This previously took
    # the top SELF_CHECK_MAX_CHUNKS and truncated to MAX_CONTEXT_TOKENS * 2
    # chars, then `break` on the first chunk that did not fit — which, measured
    # on the G5 aviation advisory, meant auditing against 1 of 5 chunks, 35% of
    # the generator's context.
    #
    # An auditor shown a third of the evidence flags grounded claims as
    # unsupported, and it did: HALLUCINATION_DETECTED fired on nearly every
    # advisory across every run, which makes the flag worthless — a signal that
    # is always on carries no information, and it was also costing a full
    # regeneration per advisory back when the self-check was blocking.
    #
    # Budget is 4 chars/token against the *same* context budget the generator
    # had, so the checker sees the whole thing. It runs on its own model and
    # therefore its own TPM bucket, so this costs nothing the advisory needed.
    context_text, included = build_self_check_context(context_chunks)

    if included < len(context_chunks):
        # Auditing on partial evidence produces false positives, so say so
        # rather than reporting a confident verdict from a partial view.
        log.warning(
            "Self-check sees %d/%d chunks for %s — verdict may over-flag",
            included, len(context_chunks), advisory.industry.value,
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
        raw = await complete_json(
            _SELF_CHECK_SYSTEM,
            human_msg,
            model=GROQ_CHECKER_MODEL,
            temperature=0.0,
            max_tokens=GROQ_CHECKER_MAX_TOKENS,
        )
        result = json.loads(_extract_json(raw))
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

    for item in advisory.action_items:
        if citation_is_grounded(item.source_ref, chunks):
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
    industry_chunk_count: int | None = None,
) -> AdvisoryOutput:
    """
    Append appropriate SafetyFlag values to the advisory based on quality checks.
    Does NOT block the advisory — flags are informational for human reviewers.

    `industry_chunk_count` is the number of chunks from the *industry* KB, as
    distinct from `chunks`, which also carries impact_matrix results.
    """
    flags = list(advisory.safety_flags)

    # LOW_COVERAGE: too few chunks above the similarity threshold.
    #
    # This used to measure len(chunks) — the combined industry + impact_matrix
    # set. Every industry is always handed 2 impact_matrix chunks (generic NOAA
    # scale definitions, not industry grounding), so the effective floor was 2
    # and the flag could only fire when an industry KB was completely empty.
    #
    # maritime_kb returns exactly 2 chunks, and they come from a 2-page
    # publisher catalogue page rather than the GMDSS manual itself. Combined
    # with the 2 generic chunks that reached 4, cleared the threshold of 3, and
    # maritime shipped as the highest-confidence, zero-flag industry in every
    # run while being the least grounded. Counting industry chunks only is what
    # makes that visible.
    coverage = industry_chunk_count if industry_chunk_count is not None else len(chunks)
    if coverage < RAG_LOW_COVERAGE_THRESHOLD:
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
