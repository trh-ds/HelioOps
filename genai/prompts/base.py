"""
Shared prompt components used across all industry advisory generators.

Includes:
  - JSON output schema (injected verbatim into every prompt)
  - format_advisory_prompt() — builds the full human-turn message
"""

from __future__ import annotations

from genai.models import RetrievedChunk, StormEvent

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
    # --- Section 1: Retrieved Context ---
    context_blocks: list[str] = []
    for chunk in chunks:
        block = (
            f"[CHUNK: {chunk.chunk_id} | "
            f"Source: {chunk.source} | "
            f"Similarity: {chunk.similarity:.2f}]\n"
            f"---\n"
            f"{chunk.text}\n"
            f"---"
        )
        context_blocks.append(block)

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

    # --- Assemble ---
    prompt = (
        f"=== RETRIEVED REGULATORY CONTEXT ===\n"
        f"{context_section}\n\n"
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
