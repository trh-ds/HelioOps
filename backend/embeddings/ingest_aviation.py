from __future__ import annotations

from backend.paths import DATA_DIR

import hashlib

from backend.embeddings.store import embed_and_upsert
from backend.embeddings.chunker import chunk_document


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _classify(text: str) -> dict:
    t = text.lower()
    if "hf" in t or "frequency" in t:
        category = "hf_procedure"
    elif "polar" in t or "latitude" in t:
        category = "reroute_criteria"
    elif "solar" in t or "geomagnetic" in t:
        category = "space_weather"
    else:
        category = "general"
    storm_scale = "G3-G5" if ("severe" in t or "extreme" in t) else "G1-G5"
    return {"category": category, "storm_scale_relevance": storm_scale}


def run() -> list[dict]:
    chunks = chunk_document(str(DATA_DIR / "aviation/nat_doc_007_2025.pdf"))
    for chunk in chunks:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = _classify(chunk["text"])

    embed_and_upsert("aviation_kb", chunks)
    print(f"Total chunks ingested: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    run()
