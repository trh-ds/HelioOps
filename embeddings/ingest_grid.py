from __future__ import annotations

import hashlib

from embeddings.cache import CachedEmbedder, embed_and_upsert, get_redis_client
from embeddings.chunker import chunk_document

_DOCS = {
    "data/grid/nerc_tpl007_4.pdf": "nerc_standard",
    "data/grid/nerc_benchmark_gmd.pdf": "gic_benchmark",
    "data/grid/nerc_transformer_thermal.pdf": "transformer_thermal",
}


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _latitude_zone(text: str) -> str:
    t = text.lower()
    if "60" in text and ("latitude" in t or "scandinavia" in t or "canada" in t):
        return "A"
    if "50" in text:
        return "B"
    return "all"


def run(embedder: CachedEmbedder | None = None) -> list[dict]:
    if embedder is None:
        embedder = CachedEmbedder(redis_client=get_redis_client())

    all_chunks: list[dict] = []
    for path, category in _DOCS.items():
        chunks = chunk_document(path)
        for chunk in chunks:
            chunk["id"] = _stable_id(chunk["source"], chunk["text"])
            chunk["metadata"] = {
                "category": category,
                "latitude_zone": _latitude_zone(chunk["text"]),
            }
        all_chunks.extend(chunks)

    embed_and_upsert("grid_kb", all_chunks, embedder=embedder)
    print(f"Total chunks ingested: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    run()
