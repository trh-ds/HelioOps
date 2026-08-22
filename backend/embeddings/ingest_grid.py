from __future__ import annotations

from backend.paths import DATA_DIR

import hashlib

from backend.embeddings.store import embed_and_upsert
from backend.embeddings.chunker import chunk_document

_DOCS = {
    str(DATA_DIR / "grid/nerc_tpl007_4.pdf"): "nerc_standard",
    str(DATA_DIR / "grid/nerc_benchmark_gmd.pdf"): "gic_benchmark",
    str(DATA_DIR / "grid/nerc_transformer_thermal.pdf"): "transformer_thermal",
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


def run() -> list[dict]:
    all_chunks: list[dict] = []
    for path, category in _DOCS.items():
        chunks = chunk_document(path)
        for chunk in chunks:
            chunk["id"] = _stable_id(chunk["source"], chunk["text"])
            chunk.setdefault("metadata", {}).update({
                "category": category,
                "latitude_zone": _latitude_zone(chunk["text"]),
            })
        all_chunks.extend(chunks)

    embed_and_upsert("grid_kb", all_chunks)
    print(f"Total chunks ingested: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    run()
