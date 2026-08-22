from __future__ import annotations

import logging
import os
import threading

# Prevent transformers from importing TensorFlow, which has a conflicting protobuf version
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
# Applied at query time only — documents are indexed without a prefix (BGE convention)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_BATCH_SIZE = 32
_model: SentenceTransformer | None = None
_model_lock = threading.Lock()  # prevents race on first load across asyncio.to_thread calls


def _get_model() -> SentenceTransformer:
    """
    Load the BGE embedder, preferring GPU but never depending on it.

    sentence-transformers auto-selects CUDA when a device is visible. If that
    device is out of memory — another process holding it, a shared dev box —
    the constructor raises and takes the whole GenAI layer down with it, since
    every advisory starts with a RAG query. The model is 130MB and runs fine on
    CPU, so a GPU problem should cost latency, not availability.

    HELIOOPS_EMBED_DEVICE forces a device explicitly ("cpu", "cuda").
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # double-checked locking
                forced = os.getenv("HELIOOPS_EMBED_DEVICE")
                if forced:
                    _model = SentenceTransformer(MODEL_NAME, device=forced)
                    return _model
                try:
                    _model = SentenceTransformer(MODEL_NAME)
                except Exception as exc:
                    log.warning(
                        "Embedder failed to load on the default device (%s) — "
                        "falling back to CPU",
                        exc,
                    )
                    _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def _demote_to_cpu() -> SentenceTransformer:
    """Reload the model on CPU and make it the process-wide instance."""
    global _model
    with _model_lock:
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    if is_query:
        texts = [QUERY_PREFIX + t for t in texts]

    def _encode(m: SentenceTransformer):
        return m.encode(
            texts,
            batch_size=_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    try:
        return _encode(model).tolist()
    except Exception as exc:
        # The model can load onto a GPU successfully and still fail here when
        # the device runs out of memory mid-run — which is what happened under
        # uvicorn, where every advisory embeds a query from a worker thread.
        # Retrieval callers treat an exception as "no context", so a transient
        # GPU fault silently produced ungrounded advisories. Demote once and
        # stay on CPU for the rest of the process.
        if os.getenv("HELIOOPS_EMBED_DEVICE"):
            raise
        log.warning("Embedding failed on the active device (%s) — retrying on CPU", exc)
        return _encode(_demote_to_cpu()).tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text], is_query=True)[0]
