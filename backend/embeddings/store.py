"""
Embed chunks and upsert them into ChromaDB.

Ingest is an offline, one-shot operation over a handful of PDFs, so the old
Redis/fakeredis embedding cache bought nothing at runtime and cost two
dependencies plus a live-server probe on import.
"""

from __future__ import annotations

from backend.embeddings.collections import get_or_create_collection
from backend.embeddings.embedder import embed_texts


def _build_metadata(chunk: dict) -> dict:
    meta = {"source": chunk["source"], "token_count": chunk["token_count"]}
    meta.update(chunk.get("metadata") or {})
    return meta


def embed_and_upsert(collection_name: str, chunks: list[dict]) -> None:
    if not chunks:
        print(f"no chunks for '{collection_name}' — nothing to upsert")
        return

    texts = [c["text"] for c in chunks]
    print(f"embedding {len(texts)} chunks")
    embeddings = embed_texts(texts)

    get_or_create_collection(collection_name).upsert(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[_build_metadata(c) for c in chunks],
    )
    print(f"upserted {len(chunks)} chunks -> '{collection_name}'")
