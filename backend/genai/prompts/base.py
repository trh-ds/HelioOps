"""
Shared prompt components used across all industry advisory generators.

Includes:
  - JSON output schema (injected verbatim into every prompt)
  - format_advisory_prompt() — builds the full human-turn message
"""

from __future__ import annotations

import tiktoken

from backend.genai.config import MAX_CONTEXT_TOKENS
from backend.genai.models import RetrievedChunk, StormEvent

_enc: tiktoken.Encoding | None = None


def _encoder() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def _token_len(text: str) -> int:
    return len(_encoder().encode(text))

# ── JSON Output Schema ────────────────────────────────────────────────────────
# Injected into every prompt so the LLM always has the exact schema in scope.

OUTPUT_JSON_SCHEMA = """{
  "storm_event_id": "<string — copy the alert_id from the STORM EVENT section>",
  "industry": "<aviation | grid | maritime | telecom>",
  "severity": "<NONE | LOW | MEDIUM | HIGH | CRITICAL>",
  "summary": "<1 to 3 sentences. Must state the storm scale, affected operations, and urgency. No filler.>",
  "action_items": [
    {
      "step": <integer starting at 1, ordered by urgency — most time-critical first>,
      "action": "<imperative sentence. What to DO. No passive voice.>",
      "rationale": "<Why this action is needed. Must reference specific context.>",
      "source_ref": "<EXACT document filename (e.g. nat_doc_007_2025.pdf) OR regulation code (e.g. NERC TPL-007-4, ICAO NAT Doc 007). MANDATORY — no null.>",
      "time_window": "<When to execute. e.g. 'T+0 immediately', 'Within 30 min of storm arrival', 'T+2h to T+8h', 'Duration of peak impact window'.>"
    }
  ],
  "estimated_impact_window": "<ISO 8601 duration or time range string, e.g. 'PT6H' or '2024-05-10T18:00Z to 2024-05-11T06:00Z'. Null if unknown.>",
  "sources_cited": ["<list every source_ref value used above — no extras, no omissions>"]
}"""

# ── Advisory Prompt Formatter ─────────────────────────────────────────────────

def format_advisory_prompt(
    storm: StormEvent,
    industry: str,
    severity: str,
    chunks: list[RetrievedChunk],
    previous_errors: list[str] | None = None,
) -> str:
    """
    Build the human-turn message for advisory generation.

    Structure:
      1. Retrieved context (numbered chunks with source labels)
      2. Storm event details
      3. Industry routing result
      4. Output schema
      5. Previous errors (if retrying)
      6. Final instruction
    """
    # --- Section 1: Retrieved Context (token-budgeted) ---
    # Chunks arrive sorted by similarity, so `continue` rather than `break`:
    # one oversized chunk should not discard the smaller, still-relevant ones
    # behind it. That mattered once the budget dropped from 4000 to ~1900 —
    # a single 500-token PDF chunk could otherwise drop the whole impact-matrix
    # tail, which is what carries the NOAA scale definitions.
    context_blocks: list[str] = []
    context_tokens = 0
    for chunk in chunks:
        block = (
            f"[CHUNK: {chunk.chunk_id} | "
            f"Source: {chunk.source} | "
            f"Similarity: {chunk.similarity:.2f}]\n"
            f"---\n"
            f"{chunk.text}\n"
            f"---"
        )
        block_tokens = _token_len(block)
        if context_tokens + block_tokens > MAX_CONTEXT_TOKENS:
            continue
        context_blocks.append(block)
        context_tokens += block_tokens

    context_section = (
        "\n\n".join(context_blocks)
        if context_blocks
        else "[NO CONTEXT RETRIEVED — use 'SOURCE UNAVAILABLE — consult space weather specialist' for all actions]"
    )

    # --- Section 2: Storm Event ---
    arrival = (
        storm.estimated_arrival_utc.isoformat() if storm.estimated_arrival_utc else "UNKNOWN"
    )
    peak_start = (
        storm.peak_impact_window_start.isoformat()
        if storm.peak_impact_window_start
        else "UNKNOWN"
    )
    peak_end = (
        storm.peak_impact_window_end.isoformat()
        if storm.peak_impact_window_end
        else "UNKNOWN"
    )

    storm_section = (
        f"Alert ID: {storm.alert_id}\n"
        f"G-Scale: {storm.g_scale.value}  (Kp={storm.kp_index})\n"
        f"S-Scale: {storm.s_scale or 'N/A'}\n"
        f"R-Scale: {storm.r_scale or 'N/A'}\n"
        f"Estimated Earth Arrival (UTC): {arrival}\n"
        f"Peak Impact Window: {peak_start}  →  {peak_end}\n"
        f"Authoritative Industry Severity: {severity}"
        + (f"\n\nRaw NOAA Alert Text:\n{storm.raw_alert_text}" if storm.raw_alert_text else "")
    )

    # --- Section 3: Errors from previous attempt ---
    error_section = ""
    if previous_errors:
        error_lines = "\n".join(f"  - {e}" for e in previous_errors)
        error_section = (
            f"\n\n=== PREVIOUS ATTEMPT ERRORS (FIX THESE) ===\n"
            f"{error_lines}\n"
            f"Do NOT repeat these mistakes."
        )

    # --- Numeric discipline ---
    #
    # The single largest source of genuine hallucinations. Each industry prompt
    # already forbids inventing values, but each does so by listing the
    # *categories* it cares about — GIC thresholds in A/phase, HF bands in MHz,
    # latitude boundaries — and models treat anything outside that list as fair
    # game. Measured on the G5 storm: grid invented "reduce loading by at least
    # 20%" and "increase VAR reserve by 15%", aviation invented "above 60,000
    # ft" and "north of 78°N". None of those figures are recommendations in the
    # retrieved text.
    #
    # Stating the rule once, generically, and giving an explicit escape hatch
    # (say it qualitatively) works better than extending each per-industry list
    # forever, because the failure is always the same shape: the model wants a
    # concrete-sounding number and will manufacture one unless told what to do
    # instead.
    numeric_rules = (
        "=== NUMERIC DISCIPLINE (applies to every action_item) ===\n"
        "Any quantity you state — percentage, frequency, altitude, latitude, "
        "current, voltage, temperature, distance, duration, count — must appear "
        "in the RETRIEVED REGULATORY CONTEXT above, and you must cite the source "
        "it came from.\n"
        "If the context does not give you a figure, do NOT invent one and do NOT "
        "estimate. Write the action qualitatively instead.\n"
        '  Wrong: "Reduce transformer loading by at least 20%."\n'
        '  Right: "Reduce transformer loading in line with the thermal limits '
        'given in the referenced standard."\n'
        '  Wrong: "Monitor crew dose above 60,000 ft."\n'
        '  Right: "Monitor crew radiation dose on affected high-latitude '
        'routes."\n'
        "A qualitative action that is fully grounded is worth more than a "
        "precise-sounding one that is invented. This is checked automatically "
        "after generation."
    )

    # --- Assemble ---
    prompt = (
        f"=== RETRIEVED REGULATORY CONTEXT ===\n"
        f"{context_section}\n\n"
        f"{numeric_rules}\n\n"
        f"=== STORM EVENT ===\n"
        f"{storm_section}\n\n"
        f"=== INDUSTRY ===\n"
        f"You are generating an advisory for: {industry.upper()}\n"
        f"Minimum required severity: {severity}\n\n"
        f"=== REQUIRED OUTPUT FORMAT ===\n"
        f"Output ONLY the following JSON — no text before or after:\n"
        f"{OUTPUT_JSON_SCHEMA}"
        f"{error_section}\n\n"
        f"Generate the {industry} advisory JSON now:"
    )

    return prompt
