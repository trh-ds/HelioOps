"""
Configuration for the HelioOps GenAI layer.
All tuneable knobs in one place.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

# Project root = two levels up from this file (genai/config.py → genai/ → project root)
_PROJECT_ROOT = Path(__file__).parent.parent

# Must match embeddings/config.py CHROMA_PERSIST_PATH
CHROMA_PERSIST_PATH = str(_PROJECT_ROOT / "data" / "chroma_db")

# ── LLM ───────────────────────────────────────────────────────────────────────

GROQ_API_KEY:    str   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL:      str   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE: float = 0.1   # near-deterministic — advisories must be reproducible
GROQ_MAX_TOKENS: int   = 2048

# Self-check uses a lighter model to save tokens; fall back to main model if not set
GROQ_CHECKER_MODEL: str = os.getenv("GROQ_CHECKER_MODEL", "llama-3.1-8b-instant")

# ── Token Budget ─────────────────────────────────────────────────────────────

MAX_PROMPT_TOKENS:  int = int(os.getenv("MAX_PROMPT_TOKENS", "4000"))  # max context tokens in advisory prompt

# ── RAG ───────────────────────────────────────────────────────────────────────

RAG_TOP_K:                int   = 5     # chunks per industry KB query
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

MAX_RETRY_ATTEMPTS:       int   = 3
SELF_CHECK_ENABLED:       bool  = True     # run LLM hallucination self-check
SELF_CHECK_MAX_CHUNKS:    int   = 5        # pass only top-N chunks to self-check LLM
LOW_CONFIDENCE_THRESHOLD: float = 0.50     # confidence below this → LOW_CONFIDENCE flag
CITATION_PENALTY:         float = 0.08     # per action_item missing source_ref
CITATION_BONUS:           float = 0.02     # per action_item with valid source_ref
COVERAGE_BONUS:           float = 0.10     # applied when context_quality > 0.6
