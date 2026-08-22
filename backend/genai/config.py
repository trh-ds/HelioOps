"""
Configuration for the HelioOps GenAI layer.
All tuneable knobs in one place.
"""

from __future__ import annotations

import os

# ── Paths ─────────────────────────────────────────────────────────────────────

from backend.embeddings.config import CHROMA_PERSIST_PATH  # noqa: F401 — re-export

# ── LLM ───────────────────────────────────────────────────────────────────────
#
# Model choice, 2026-08-21. The previous defaults — llama-3.3-70b-versatile and
# llama-3.1-8b-instant — were decommissioned by Groq and now return 404
# model_not_found, which made every advisory fall through to the
# ESCALATE_TO_SPECIALIST fallback. Verify the live list with:
#     python -c "from groq import Groq; print([m.id for m in Groq().models.list().data])"
#
# gpt-oss are reasoning models: their chain-of-thought is returned in a separate
# `reasoning` field but is billed against max_tokens. At the default reasoning
# effort a full advisory prompt burns the entire completion budget on CoT and
# returns finish_reason="length" — truncated JSON. GROQ_REASONING_EFFORT="low"
# is what keeps the JSON intact.

GROQ_API_KEY:    str   = os.getenv("GROQ_API_KEY", "")

# Groq meters TPM per (key, model). A second key is therefore a second full
# budget for the same model — the cheapest way to buy throughput without
# touching prompt size or quality.
#
# GROQ_API_KEYS takes a comma-separated list and supersedes GROQ_API_KEY when
# set. Keys are pooled: any key can serve any model, and llm.py routes each
# call to whichever (key, model) bucket has the most headroom.
#
# This buys latency, not accuracy. Context window is 131k and the largest
# prompt we send is ~3.9k — 3% utilisation — so no amount of extra budget
# unlocks "more context". See MAX_PROMPT_TOKENS below.
def _parse_keys() -> list[str]:
    raw = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys or [""]


GROQ_API_KEYS: list[str] = _parse_keys()

GROQ_MODEL:      str   = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_TEMPERATURE: float = 0.1   # near-deterministic — advisories must be reproducible
GROQ_MAX_TOKENS: int   = int(os.getenv("GROQ_MAX_TOKENS", "1200"))
GROQ_REASONING_EFFORT: str = os.getenv("GROQ_REASONING_EFFORT", "low")

# The self-check runs on a *different* model on purpose: Groq meters TPM per
# model, so the checker draws from its own bucket instead of competing with the
# advisory calls. Verified empirically — burning 1.5k tokens on gpt-oss-120b
# left gpt-oss-20b's remaining-token counter untouched.
GROQ_CHECKER_MODEL: str = os.getenv("GROQ_CHECKER_MODEL", "openai/gpt-oss-20b")
GROQ_CHECKER_MAX_TOKENS: int = int(os.getenv("GROQ_CHECKER_MAX_TOKENS", "512"))

# ── Rate limiting ────────────────────────────────────────────────────────────
#
# Free-tier Groq keys meter 8000 tokens/minute per model. The old design fired
# four agents at once with a 4000-token context budget and a 2048-token
# completion cap — ~26k tokens in a single burst, 3.3x over the ceiling, and
# ~79k across the retry loop. There was no 429 handling anywhere, so a rate
# limit raised straight into the agent's `except`, burned a retry attempt
# instantly, and the run degraded to fallback advisories.
#
# GROQ_TPM_LIMIT drives a client-side sliding-window bucket in genai/llm.py.
# Set it to your account's real limit; raise it on a paid key to remove pacing.

GROQ_TPM_LIMIT: int = int(os.getenv("GROQ_TPM_LIMIT", "8000"))
GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "4"))

# Wall-clock ceiling for a single completion. Without one, a stalled connection
# holds an agent (and its semaphore slot) forever, and the pipeline never
# returns — there is no other timeout anywhere on this path. Generous enough
# that normal calls (1-6s observed) never trip it.
GROQ_REQUEST_TIMEOUT_S: float = float(os.getenv("GROQ_REQUEST_TIMEOUT_S", "90"))

# Cap on simultaneous in-flight advisory agents. Bounded fan-out keeps each
# burst inside the bucket instead of spiking 4x and then stalling.
GENAI_MAX_CONCURRENCY: int = int(os.getenv("GENAI_MAX_CONCURRENCY", "2"))

# ── Token Budget ─────────────────────────────────────────────────────────────
#
# MAX_CONTEXT_TOKENS budgets the retrieved chunks *only* — it is not a whole-
# prompt ceiling. The fixed overhead around them (system prompt, JSON schema
# block, storm section, instructions) is ~1100 tokens, accounted for by
# PROMPT_FIXED_OVERHEAD_TOKENS so callers can reason about the real total.
#
# MAX_PROMPT_TOKENS is kept as the whole-prompt ceiling and as the name the
# .env has always used.

# Sizing note. The context window is 131,072 and the largest prompt we build
# is ~3.9k tokens — 3% utilisation. The window has never been the constraint
# and no amount of extra rate-limit budget changes that; raising this trades
# latency for grounding, nothing more.
#
# Measured on the G5 anchor storm, citation validity (fraction of action items
# whose source_ref resolves to a chunk that was actually retrieved):
#     K=3 / 1900-token context ->  95% mean, 2288 mean input tokens, ~86s/storm
#     K=5 / 3200-token context -> 100% mean, 2829 mean input tokens, ~129s/storm
#     K=8 / 6000-token context -> 100% mean, 3624 mean input tokens
#
# Treat that 95->100 as noise, not a result: it is one sample per cell, and a
# later K=5 run produced a CITATION_GAP that the K=5 sample above did not.
# Two of the four industries cannot respond to K at all — maritime_kb returns
# only 2 chunks over the similarity floor and telecom_kb is empty — so K moves
# at most half the output, and not reliably.
#
# Default is therefore the cheap setting. K=5 costs +50% wall time for an
# unproven gain on one free-tier key; with GROQ_API_KEYS pooled that latency
# largely disappears and K=5 becomes the better default. Raise both together.
MAX_PROMPT_TOKENS:  int = int(os.getenv("MAX_PROMPT_TOKENS", "3000"))
PROMPT_FIXED_OVERHEAD_TOKENS: int = 1100
MAX_CONTEXT_TOKENS: int = max(400, MAX_PROMPT_TOKENS - PROMPT_FIXED_OVERHEAD_TOKENS)

# ── RAG ───────────────────────────────────────────────────────────────────────
#
# Pairs with MAX_PROMPT_TOKENS above — see the measurement note there before
# changing it. Raise to 5 together with MAX_PROMPT_TOKENS=4300 when running a
# pooled key set, where the extra latency is absorbed.

RAG_TOP_K:                int   = int(os.getenv("RAG_TOP_K", "3"))   # chunks per industry KB query
RAG_IMPACT_MATRIX_TOP_K:  int   = 2     # chunks from impact_matrix_kb per query
RAG_MIN_SIMILARITY:        float = 0.35  # drop chunks below this cosine similarity
RAG_LOW_COVERAGE_THRESHOLD: int  = 3     # fewer valid chunks → LOW_COVERAGE flag

# ── Knowledge Base Names (must match embeddings/config.py COLLECTION_NAMES) ──

INDUSTRY_KB_MAP: dict[str, str] = {
    "aviation": "aviation_kb",
    "grid":     "grid_kb",
    "maritime": "maritime_kb",
    "telecom":  "telecom_kb",
}
IMPACT_MATRIX_KB: str = "impact_matrix_kb"

# ── Retry & Guardrail Thresholds ─────────────────────────────────────────────

# An operations advisory with one step is not an advisory. The schema had no
# floor, so a single-action response validated cleanly and shipped — observed
# on maritime (1 item) and telecom (2) while both KBs held 160+ chunks.
# Falling short routes into the normal retry loop.
MIN_ACTION_ITEMS:         int   = int(os.getenv("MIN_ACTION_ITEMS", "3"))

MAX_RETRY_ATTEMPTS:       int   = 3
SELF_CHECK_ENABLED:       bool  = True     # run LLM hallucination self-check
SELF_CHECK_MAX_CHUNKS:    int   = 5        # pass only top-N chunks to self-check LLM

# When the self-check fires, does the agent regenerate from scratch?
#
# It used to, unconditionally, and that was the single most expensive thing in
# the layer. A flagged advisory cost a second full prompt+completion, and on
# the G5 anchor storm three of four industries flagged — tripling token spend
# and pushing a run from ~90s to 344s against the free-tier TPM budget.
#
# It also rarely helped. The checker flags specific numerics ("225 A/phase",
# "2.8-18 MHz") that the model re-derives from the same context on the retry,
# so the second attempt flags too, and the code keeps the flagged advisory
# anyway once attempts run out. Same output, 3x the tokens.
#
# Default: flag it, score it down, ship it for human review — which is what
# SafetyFlag.HALLUCINATION_DETECTED is for. Set true to restore regeneration.
SELF_CHECK_BLOCKING:      bool  = os.getenv("SELF_CHECK_BLOCKING", "false").lower() == "true"

# Confidence penalty applied when the self-check flags an advisory but
# SELF_CHECK_BLOCKING is off. Keeps the flag economically meaningful.
SELF_CHECK_CONFIDENCE_PENALTY: float = 0.25
LOW_CONFIDENCE_THRESHOLD: float = 0.50     # confidence below this → LOW_CONFIDENCE flag
CITATION_PENALTY:         float = 0.08     # per action_item missing source_ref
CITATION_BONUS:           float = 0.02     # per action_item with valid source_ref
COVERAGE_BONUS:           float = 0.10     # applied when context_quality > 0.6
