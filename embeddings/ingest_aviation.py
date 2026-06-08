from __future__ import annotations

import hashlib

from embeddings.cache import CachedEmbedder, embed_and_upsert, get_redis_client
from embeddings.chunker import chunk_document


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _classify(text: str) -> dict:
    t = text.lower()
    if "hf" in t or "frequency" in t:
        category = "hf_procedure"
    elif "polar" in t or "latitude" in t:
        category = "reroute_criteria"
    elif "solar" in t or "geomagnetic" in t:
        category = "space_weather"
    else:
        category = "general"
    storm_scale = "G3-G5" if ("severe" in t or "extreme" in t) else "G1-G5"
    return {"category": category, "storm_scale_relevance": storm_scale}


def run(embedder: CachedEmbedder | None = None) -> list[dict]:
    if embedder is None:
        embedder = CachedEmbedder(redis_client=get_redis_client())

    chunks = chunk_document("data/aviation/nat_doc_007_2025.pdf")
    for chunk in chunks:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = _classify(chunk["text"])

    embed_and_upsert("aviation_kb", chunks, embedder=embedder)
    print(f"Total chunks ingested: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    run()
