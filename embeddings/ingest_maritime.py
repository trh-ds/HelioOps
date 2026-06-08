from __future__ import annotations

import hashlib

from embeddings.cache import CachedEmbedder, embed_and_upsert, get_redis_client
from embeddings.chunker import chunk_document


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _frequency_type(text: str) -> str:
    if "HF" in text:
        return "hf"
    if "MF" in text:
        return "mf"
    return "satcom"


def run(embedder: CachedEmbedder | None = None) -> list[dict]:
    if embedder is None:
        embedder = CachedEmbedder(redis_client=get_redis_client())

    chunks = chunk_document("data/maritime/imo_gmdss_2019.pdf")
    for chunk in chunks:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = {
            "category": "gmdss_procedure",
            "region": "global",
            "frequency_type": _frequency_type(chunk["text"]),
        }

    embed_and_upsert("maritime_kb", chunks, embedder=embedder)
    print(f"Total chunks ingested: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    run()
