"""
Knowledge-base retrieval with Maximal Marginal Relevance (MMR) reranking.

Usage:
    from embeddings.retrieval import query_kb, format_context, query_all_kbs

    results = query_kb("aviation_kb", "G4 storm HF blackout polar route", n_results=5)
    context = format_context(results)

CRITICAL: Always uses embed_query() from embeddings.embedder — never ChromaDB's
built-in query_texts (that uses MiniLM, a different embedding space).
"""

from __future__ import annotations

import numpy as np

from embeddings.collections import get_or_create_collection
from embeddings.config import COLLECTION_NAMES
from embeddings.embedder import embed_query


def query_kb(
    collection_name: str,
    query_text: str,
    n_results: int = 5,
    use_mmr: bool = True,
    where: dict | None = None,
) -> list[dict]:
    """
    Query a ChromaDB collection and return filtered, ranked chunks.

    Args:
        collection_name: Name of the ChromaDB collection.
        query_text:      Natural-language query string.
        n_results:       Number of results to return.
        use_mmr:         Apply MMR reranking (lambda=0.7) for diversity.
        where:           Optional ChromaDB metadata filter dict.

    Returns:
        List of dicts with keys: text, source, metadata, distance.
    """
    collection = get_or_create_collection(collection_name)
    n_total = collection.count()
    if n_total == 0:
        return []

    query_vec = embed_query(query_text)
    # Only fetch extra candidates + embeddings when MMR reranking is needed
    n_fetch = min(20, n_total) if use_mmr else min(n_results, n_total)
    include = ["documents", "metadatas", "distances"] + (["embeddings"] if use_mmr else [])

    query_kwargs: dict = {
        "query_embeddings": [query_vec],
        "n_results": n_fetch,
        "include": include,
    }
    if where is not None:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    # Cosine distance ∈ [0, 2] for L2-normalized vectors → sim = 1 - dist/2
    sims_to_query = 1.0 - np.array(dists) / 2.0

    if not use_mmr or len(docs) <= n_results:
        return [
            {"text": d, "source": m.get("source", ""), "metadata": m, "distance": dist}
            for d, m, dist in zip(docs, metas, dists)
        ][:n_results]

    embs = np.array(results["embeddings"][0])  # shape (n_fetch, 384)

    # MMR greedy selection — λ = 0.7 (70% relevance, 30% diversity)
    LAMBDA = 0.7
    selected: list[dict] = []
    selected_embs: list[np.ndarray] = []

    for _ in range(min(n_results, len(docs))):
        if not selected:
            best = int(np.argmax(sims_to_query))
        else:
            sel_mat = np.array(selected_embs)  # (k, 384), L2-normalized
            # Max cosine similarity to any already-selected chunk
            sim_to_selected = (embs @ sel_mat.T).max(axis=1)  # dot = cosine (normalized)
            scores = LAMBDA * sims_to_query - (1 - LAMBDA) * sim_to_selected
            # Exclude already-picked indices
            for s in selected:
                scores[s["_idx"]] = -np.inf
            best = int(np.argmax(scores))

        selected.append({
            "text": docs[best],
            "source": metas[best].get("source", ""),
            "metadata": metas[best],
            "distance": dists[best],
            "_idx": best,
        })
        selected_embs.append(embs[best])

    # Strip internal _idx before returning
    return [{k: v for k, v in s.items() if k != "_idx"} for s in selected]


def format_context(results: list[dict]) -> str:
    """Numbered context block injected into LLM system prompt."""
    if not results:
        return "[NO CONTEXT RETRIEVED]"
    return "\n\n".join(
        f"[{i + 1}] (source: {r['source']} | category: {r['metadata'].get('category', 'general')})\n{r['text']}"
        for i, r in enumerate(results)
    )


def query_all_kbs(query: str, n_per_collection: int = 3) -> dict[str, list[dict]]:
    """Query all populated collections. Skip empty ones (e.g. telecom_kb = 0 chunks)."""
    out: dict[str, list[dict]] = {}
    for name in COLLECTION_NAMES:
        c = get_or_create_collection(name)
        if c.count() == 0:
            print(f"WARNING: {name} skipped -- no data")
            continue
        out[name] = query_kb(name, query, n_results=n_per_collection)
    return out


if __name__ == "__main__":
    # Quick smoke test
    results = query_kb(
        "aviation_kb",
        "G4 storm HF blackout polar route reroute latitude threshold",
        n_results=5,
        use_mmr=True,
    )
    print(f"\n--- aviation_kb: {len(results)} results ---")
    for i, r in enumerate(results):
        cat = r["metadata"].get("category", "general")
        print(f"  [{i + 1}] category={cat} source={r['source'][:40]} dist={r['distance']:.4f}")
    print("\n--- format_context preview ---")
    print(format_context(results)[:500])
