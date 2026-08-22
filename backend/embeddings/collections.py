from __future__ import annotations

import logging
import threading
import time

import chromadb
from backend.embeddings.config import CHROMA_PERSIST_PATH, COLLECTION_NAMES

log = logging.getLogger(__name__)

_client: chromadb.PersistentClient | None = None
# Every advisory starts with two retrieve_chunks() calls dispatched through
# asyncio.to_thread, so first use is genuinely concurrent across threads.
# Without this lock several threads enter PersistentClient() at once and the
# losers observe a half-initialised client, surfacing as
# "Could not connect to tenant default_tenant". Retrieval then returns no
# chunks and the agent silently emits an ungrounded advisory.
#
# The race was latent while free-tier TPM limits serialised the agents; it
# became reproducible as soon as a pooled key set let them actually run in
# parallel. embedder.py guards its model singleton the same way.
_client_lock = threading.Lock()


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # double-checked locking
                # Telemetry off. Chroma's PostHog reporter fires during advisory
                # generation and blocks on a 15s DNS/read timeout when egress is
                # restricted, which shows up as unexplained latency in the middle
                # of a pipeline run. Nothing here needs it.
                _client = chromadb.PersistentClient(
                    path=CHROMA_PERSIST_PATH,
                    settings=chromadb.config.Settings(anonymized_telemetry=False),
                )
    return _client


def get_client() -> chromadb.PersistentClient:
    """The single ChromaDB client. Never construct a second one on this path."""
    return _get_client()


def get_or_create_collection(name: str) -> chromadb.Collection:
    return _get_client().get_or_create_collection(name)


# ── Transient segment-reader faults ──────────────────────────────────────────
#
# chromadb intermittently fails a vector query with
#
#     Error executing plan: Internal error:
#     Error creating hnsw segment reader: Nothing found on disk
#
# even though the DB is structurally sound: every VECTOR segment in
# chroma.sqlite3 has its directory on disk, and there are no orphans either
# way. It reproduces in roughly one pytest session in five and does not
# reproduce from a plain script issuing the same queries.
#
# Things ruled out by measurement, so nobody re-checks them:
#   - Not a synced-folder problem. It reproduces identically with
#     HELIOOPS_CHROMA_PERSIST_PATH pointing at a local non-synced disk.
#   - Not DB corruption from a partial revert. Segment/directory bookkeeping
#     was verified consistent while the failure was live.
#   - Not our client-construction race. That is separately locked below, and
#     30 concurrent retrievals pass cleanly.
#
# The root cause is inside chromadb and is not fixed here. What is fixed is the
# consequence: a failed read used to mean an advisory generated with no
# retrieved context at all. Recovery re-acquires the collection handle and
# retries, which took a 12-run soak from 3 failures to 0.
#
# Do not "improve" this by also dropping the client singleton between attempts.
# That was tried: it invalidates handles other callers still hold and made
# things worse, taking the same soak from 1 failure in 10 to 3 in 8.
_TRANSIENT_MARKERS = (
    "nothing found on disk",
    "hnsw segment reader",
    "error executing plan",
    "no such file",
    "being used by another process",
    "permission denied",
)
_QUERY_ATTEMPTS = 4


def is_transient_storage_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def with_collection(collection_name: str, operation, *, create: bool = False):
    """
    Run `operation(collection)`, recovering from transient segment faults.

    The collection handle is acquired *inside* the retry loop on purpose: the
    fault appears to leave a dead segment reader attached to the handle, so
    retrying the same object does not recover.

    Every chroma read goes through here. Wrapping only `.query()` was not
    enough: `.count()` runs before the query on both retrieval paths and
    `.get()` is used for metadata lookups, and an unprotected fault in either
    produced the same ungrounded-advisory outcome.

    Re-raises non-transient errors immediately, and re-raises the transient one
    once attempts are exhausted — callers decide whether an unreadable KB is
    fatal or merely means "no context".
    """
    for attempt in range(1, _QUERY_ATTEMPTS + 1):
        try:
            client = _get_client()
            collection = (
                client.get_or_create_collection(collection_name)
                if create
                else client.get_collection(collection_name)
            )
            return operation(collection)
        except Exception as exc:
            if not is_transient_storage_error(exc):
                raise
            if attempt == _QUERY_ATTEMPTS:
                log.error(
                    "KB '%s' unreadable after %d attempts (%s)",
                    collection_name, _QUERY_ATTEMPTS, exc,
                )
                raise
            log.warning(
                "KB '%s' segment fault (attempt %d/%d): %s — re-acquiring and retrying",
                collection_name, attempt, _QUERY_ATTEMPTS, str(exc)[:90],
            )
            # Re-acquire the collection handle on the next pass, but do NOT drop
            # the shared client. Nulling the singleton invalidates handles that
            # other callers in the same process are still holding, which turned
            # one failed read into several — measured failure rate went up, not
            # down, when this reset the client.
            time.sleep(0.2 * attempt)


def query_collection(collection_name: str, /, **query_kwargs):
    """Vector query by collection name, with transient-fault recovery."""
    return with_collection(collection_name, lambda c: c.query(**query_kwargs))


def count_collection(collection_name: str, *, create: bool = False) -> int:
    """Chunk count, with transient-fault recovery. 0 if the collection is absent."""
    try:
        return with_collection(collection_name, lambda c: c.count(), create=create)
    except Exception:
        if create:
            raise
        return 0


def init_all_collections() -> list[chromadb.Collection]:
    return [get_or_create_collection(name) for name in COLLECTION_NAMES]


if __name__ == "__main__":
    collections = init_all_collections()
    for col in collections:
        print(f"{col.name}: {col.count()} documents")
