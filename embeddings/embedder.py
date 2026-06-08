from __future__ import annotations

import os

# Prevent transformers from importing TensorFlow, which has a conflicting protobuf version
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
# Applied at query time only — documents are indexed without a prefix (BGE convention)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_BATCH_SIZE = 32
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    if is_query:
        texts = [QUERY_PREFIX + t for t in texts]
    embeddings = model.encode(
        texts,
        batch_size=_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text], is_query=True)[0]
