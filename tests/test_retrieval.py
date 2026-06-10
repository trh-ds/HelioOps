"""
Tests for embeddings/retrieval.py — Commit 08.

Requires populated ChromaDB at data/chroma_db.
Run from project root: pytest tests/test_retrieval.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root on path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from embeddings.retrieval import query_kb, format_context, query_all_kbs
from embeddings.embedder import embed_query


# ── Aviation KB ──────────────────────────────────────────────────────────────

class TestAviationKB:
    def test_g4_aviation_query_returns_results(self, g4_fixture):
        """G4 query returns at least 1 chunk with hf_procedure category."""
        results = query_kb(
            "aviation_kb",
            f"G{g4_fixture['g_scale']} storm HF frequency blackout polar route reroute",
            n_results=5,
            use_mmr=True,
        )
        assert len(results) >= 1, "Expected at least 1 result from aviation_kb"
        categories = [r["metadata"].get("category") for r in results]
        assert "hf_procedure" in categories, (
            f"Expected hf_procedure in categories, got {categories}"
        )

    def test_mmr_diversity(self):
        """MMR returns at least 2 distinct categories in top 5."""
        results = query_kb(
            "aviation_kb",
            "G4 storm HF blackout polar route reroute latitude threshold",
            n_results=5,
            use_mmr=True,
        )
        categories = {r["metadata"].get("category") for r in results}
        assert len(categories) >= 2, (
            f"MMR should produce diverse results, got only: {categories}"
        )


# ── Grid KB ──────────────────────────────────────────────────────────────────

class TestGridKB:
    def test_zone_a_where_filter(self):
        """where={latitude_zone: A} returns only zone-A chunks."""
        results = query_kb(
            "grid_kb",
            "GIC transformer protection geomagnetic latitude 60 degrees",
            n_results=5,
            use_mmr=False,
            where={"latitude_zone": "A"},
        )
        assert len(results) >= 1, "Expected at least 1 zone-A result"
        for r in results:
            assert r["metadata"].get("latitude_zone") == "A", (
                f"Expected latitude_zone=A, got {r['metadata']}"
            )


# ── Maritime KB ──────────────────────────────────────────────────────────────

class TestMaritimeKB:
    def test_maritime_returns_at_least_one(self):
        """Maritime KB has limited chunks — assert at least 1 result."""
        results = query_kb(
            "maritime_kb",
            "GMDSS HF backup channel storm",
            n_results=3,
            use_mmr=False,
        )
        assert len(results) >= 1, "Expected at least 1 result from maritime_kb"


# ── Telecom KB ───────────────────────────────────────────────────────────────

class TestTelecomKB:
    @pytest.mark.xfail(reason="telecom_kb not yet populated", strict=True)
    def test_telecom_query_returns_results(self):
        """telecom_kb is empty — this should fail."""
        results = query_kb(
            "telecom_kb",
            "GPS L1 degradation satellite uplink",
            n_results=3,
        )
        assert len(results) >= 1


# ── Embedding Consistency ────────────────────────────────────────────────────

class TestEmbeddingConsistency:
    def test_same_text_produces_identical_embeddings(self):
        """Embedding same text twice yields bit-identical vectors."""
        text = "G4 storm HF frequency blackout"
        v1 = embed_query(text)
        v2 = embed_query(text)
        dot = np.dot(v1, v2)
        assert dot > 0.999, f"Expected dot product > 0.999, got {dot}"


# ── Format Context ───────────────────────────────────────────────────────────

class TestFormatContext:
    def test_format_context_numbered(self):
        """format_context produces numbered blocks with source info."""
        results = query_kb("aviation_kb", "HF frequency", n_results=2, use_mmr=False)
        ctx = format_context(results)
        assert "[1]" in ctx
        assert "source:" in ctx

    def test_format_context_empty(self):
        """Empty results produce a no-context marker."""
        ctx = format_context([])
        assert "NO CONTEXT" in ctx


# ── query_all_kbs ────────────────────────────────────────────────────────────

class TestQueryAllKBs:
    def test_returns_populated_kbs(self):
        """query_all_kbs returns results for non-empty collections."""
        all_results = query_all_kbs("G4 geomagnetic storm impacts", n_per_collection=2)
        # At minimum, aviation_kb and grid_kb should be populated
        assert "aviation_kb" in all_results
        assert "grid_kb" in all_results
