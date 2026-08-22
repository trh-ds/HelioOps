"""
ChromaDB retrieval wrapper for the HelioOps GenAI layer.

Uses the same BGE-small embedder that was used at ingest time, ensuring
query and document vectors are in the same embedding space.

Similarity is computed from ChromaDB's L2 distance:
  cosine_similarity = 1 - (l2_distance² / 2)     [valid for unit-norm vectors]
"""

from __future__ import annotations

import logging

from backend.embeddings.collections import count_collection as _count_collection
from backend.embeddings.collections import query_collection as _query_collection
from backend.embeddings.embedder import embed_query as _embed_query
from backend.genai.config import RAG_MIN_SIMILARITY
from backend.genai.models import RetrievedChunk

log = logging.getLogger(__name__)

# ── Core retrieval ────────────────────────────────────────────────────────────

def retrieve_chunks(
    collection_name: str,
    query: str,
    top_k: int = 8,
    min_similarity: float = RAG_MIN_SIMILARITY,
) -> list[RetrievedChunk]:
    """
    Query a ChromaDB collection and return filtered, ranked chunks.

    Args:
        collection_name:  Name of the ChromaDB collection.
        query:            Natural-language query string.
        top_k:            Maximum number of results to retrieve from Chroma.
        min_similarity:   Drop chunks with cosine similarity below this threshold.

    Returns:
        List of RetrievedChunk objects sorted by similarity (descending).
        Empty list if collection doesn't exist or no chunks pass the threshold.
    """
    # A silent `except Exception: return []` used to wrap this whole function.
    # When retrieval broke, the agent got zero chunks, the prompt fell back to
    # "[NO CONTEXT RETRIEVED]", and the LLM produced an ungrounded advisory
    # whose only citation was that placeholder string — flagged LOW_COVERAGE
    # but otherwise indistinguishable from a real one. In an anti-hallucination
    # pipeline a retrieval failure has to be loud, so only the genuinely
    # expected case (collection absent) is swallowed.
    try:
        count = _count_collection(collection_name)
        if count == 0:
            log.warning(
                "KB collection '%s' is empty — advisory will be ungrounded",
                collection_name,
            )
            return []

        query_embedding = _embed_query(query)
        results = _query_collection(
            collection_name,
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        log.exception(
            "RAG retrieval failed for collection '%s' — advisory will be ungrounded",
            collection_name,
        )
        return []

    chunks: list[RetrievedChunk] = []
    for i, (doc, meta, dist) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ):
        # ChromaDB L2 distance → cosine similarity (unit-norm vectors)
        # dist = ||a - b||² = 2 - 2·cos(θ)  →  cos(θ) = 1 - dist/2
        cosine_sim = max(0.0, 1.0 - dist / 2.0)
        if cosine_sim < min_similarity:
            continue
        chunks.append(
            RetrievedChunk(
                chunk_id=results["ids"][0][i],
                text=doc,
                source=meta.get("source", "unknown"),
                similarity=round(cosine_sim, 4),
                metadata=dict(meta),
            )
        )

    # Sort by similarity descending (already sorted by Chroma, but enforce)
    chunks.sort(key=lambda c: c.similarity, reverse=True)
    return chunks


# ── Context formatting ────────────────────────────────────────────────────────

def format_context(chunks: list[RetrievedChunk], max_chars: int = 12_000) -> str:
    """
    Render retrieved chunks as a labelled context block for the LLM prompt.

    Each chunk is labelled with its chunk_id and source filename so the LLM
    can produce accurate source_ref citations.
    """
    if not chunks:
        return "[NO CONTEXT RETRIEVED — insufficient knowledge base coverage]"

    lines: list[str] = []
    total_chars = 0

    for chunk in chunks:
        # The page is what lets the console deep-link the citation into the PDF
        # (#page=N). Advertising it here is what makes the model cite it, so the
        # locator survives all the way from ingest to the operator's click.
        page = chunk.metadata.get("page")
        source = f"{chunk.source} p.{page}" if page else chunk.source
        header = (
            f"[CHUNK: {chunk.chunk_id} | "
            f"Source: {source} | "
            f"Similarity: {chunk.similarity:.2f}]"
        )
        block = f"{header}\n---\n{chunk.text}\n---\n"
        if total_chars + len(block) > max_chars:
            break
        lines.append(block)
        total_chars += len(block)

    return "\n".join(lines)


def compute_context_quality(chunks: list[RetrievedChunk]) -> float:
    """
    Average cosine similarity of the provided chunks.
    Returns 0.0 for empty input.
    """
    if not chunks:
        return 0.0
    return round(sum(c.similarity for c in chunks) / len(chunks), 4)
