from __future__ import annotations

import hashlib
import json
from typing import Any

import redis as redis_lib

from embeddings.embedder import embed_texts

_TTL = 86400
_PREFIX = "emb:"


class CachedEmbedder:
    def __init__(
        self,
        redis_client: Any = None,
        redis_url: str = "redis://localhost:6379",
    ) -> None:
        self._redis = redis_client if redis_client is not None else redis_lib.from_url(redis_url)

    def _key(self, text: str) -> str:
        return _PREFIX + hashlib.sha256(text.encode()).hexdigest()

    def get(self, text: str) -> list[float]:
        key = self._key(text)
        cached = self._redis.get(key)
        if cached:
            return json.loads(cached)
        embedding = embed_texts([text])[0]
        self._redis.setex(key, _TTL, json.dumps(embedding))
        return embedding


def embed_and_upsert(
    collection_name: str,
    chunks: list[dict],
    embedder: CachedEmbedder | None = None,
) -> None:
    from embeddings.collections import get_or_create_collection

    if embedder is None:
        embedder = CachedEmbedder()

    texts = [c["text"] for c in chunks]
    keys = [embedder._key(t) for t in texts]

    # Single round-trip to check all keys at once
    cached_values = list(embedder._redis.mget(keys))
    miss_indices = [i for i, v in enumerate(cached_values) if v is None]

    if miss_indices:
        print(f"embedding {len(miss_indices)} chunks")
        miss_texts = [texts[i] for i in miss_indices]
        new_embeddings = embed_texts(miss_texts)
        pipe = embedder._redis.pipeline()
        for idx, vec in zip(miss_indices, new_embeddings):
            pipe.setex(keys[idx], _TTL, json.dumps(vec))
        pipe.execute()
        for idx, vec in zip(miss_indices, new_embeddings):
            cached_values[idx] = json.dumps(vec).encode()
    else:
        print(f"all {len(chunks)} chunks cached — 0 embedding calls")

    embeddings = [json.loads(v) for v in cached_values]

    collection = get_or_create_collection(collection_name)
    collection.upsert(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"], "token_count": c["token_count"]} for c in chunks],
    )
    print(f"upserted {len(chunks)} chunks -> '{collection_name}'")
