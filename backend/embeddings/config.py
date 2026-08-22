import os

from backend.paths import CHROMA_DIR

# Single source of truth — genai/config.py re-exports this value, and
# embeddings/collections.py is the only thing that opens the DB.
#
# HELIOOPS_CHROMA_PERSIST_PATH was documented in .env, .env.example and
# backend/config.py Settings, but nothing on the retrieval path ever read it:
# this module hardcoded backend.paths.CHROMA_DIR, so pointing the variable
# somewhere else silently had no effect at all. It is honoured here now, which
# is also what makes it possible to move the DB off a synced or slow volume
# without moving the repo.
#
# Relative values resolve against the REPO ROOT, not the current working
# directory, so `backend/data/chroma_db` behaves the same however you launch.
#
# It used to resolve against the backend package (CHROMA_DIR.parent.parent),
# which turned the `backend/data/chroma_db` shipped in .env and .env.example
# into `backend/backend/data/chroma_db`. Chroma happily *creates* that path, so
# every KB came back empty, retrieve_chunks() swallowed it, and every advisory
# was ungrounded with no error anywhere. Pinned by TestChromaPathResolution.
_override = os.getenv("HELIOOPS_CHROMA_PERSIST_PATH", "").strip()
if _override:
    _path = os.path.expanduser(_override)
    if not os.path.isabs(_path):
        _path = str((CHROMA_DIR.parent.parent.parent / _path).resolve())
    CHROMA_PERSIST_PATH = _path
else:
    CHROMA_PERSIST_PATH = str(CHROMA_DIR)

COLLECTION_NAMES = [
    "aviation_kb",
    "grid_kb",
    "maritime_kb",
    "impact_matrix_kb",
    "telecom_kb",
]
