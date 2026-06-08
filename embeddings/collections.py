from __future__ import annotations

import chromadb
from embeddings.config import CHROMA_PERSIST_PATH, COLLECTION_NAMES

_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return _client


def get_or_create_collection(name: str) -> chromadb.Collection:
    return _get_client().get_or_create_collection(name)


def init_all_collections() -> list[chromadb.Collection]:
    return [get_or_create_collection(name) for name in COLLECTION_NAMES]


if __name__ == "__main__":
    collections = init_all_collections()
    for col in collections:
        print(f"{col.name}: {col.count()} documents")
