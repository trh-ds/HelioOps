"""
Rebuild every knowledge-base collection from the committed source documents.

    python -m backend.embeddings.rebuild_kb            # ingest all four KBs
    python -m backend.embeddings.rebuild_kb --verify   # report counts only

Why this exists
---------------
`backend/data/chroma_db/` is committed so a fresh clone and the Docker image
have working RAG with no setup step. That makes it derived data living in git:
ChromaDB rewrites the segment files whenever the DB is opened, so `git status`
shows the binaries as modified after any test run even though the contents are
unchanged. This script makes the DB reproducible, so that churn is discardable
(`git checkout -- backend/data/chroma_db`) rather than something to preserve.

The source PDFs and text are all committed under `backend/data/`, so this is
deterministic apart from chunk ordering.
"""

from __future__ import annotations

import argparse

from backend.embeddings.collections import get_client
from backend.embeddings.config import COLLECTION_NAMES

_INGESTS = ("aviation", "grid", "maritime", "impact_matrix", "telecom")


# Below this, an industry KB cannot ground an advisory on its own and the
# agent's output leans on the generic impact_matrix chunks instead. Kept in
# step with RAG_LOW_COVERAGE_THRESHOLD, which raises SafetyFlag.LOW_COVERAGE
# for the same condition at runtime.
_THIN_KB_CHUNKS = 10


def verify() -> int:
    """Print per-collection counts. Returns the number of unusable collections."""
    client = get_client()
    bad = 0
    for name in COLLECTION_NAMES:
        try:
            count = client.get_collection(name).count()
        except Exception:
            count = 0

        if not count:
            note = "   <-- EMPTY: advisories will be ungrounded"
            bad += 1
        elif count < _THIN_KB_CHUNKS:
            note = "   <-- THIN: check the source document is the real thing"
            bad += 1
        else:
            note = ""
        print(f"  {name:<20} {count:>5} chunks{note}")
    return bad


def rebuild() -> None:
    from importlib import import_module

    total = 0
    for name in _INGESTS:
        module = import_module(f"backend.embeddings.ingest_{name}")
        print(f"\n=== {name} ===")
        chunks = module.run()
        total += len(chunks or [])
    print(f"\nTotal chunks ingested: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="print per-collection chunk counts without re-ingesting",
    )
    args = parser.parse_args()

    if args.verify:
        print("Knowledge base contents:")
        empty = verify()
        raise SystemExit(1 if empty else 0)

    rebuild()
    print("\nKnowledge base contents:")
    verify()


if __name__ == "__main__":
    main()
