from __future__ import annotations

import hashlib
import re
from pathlib import Path

from embeddings.cache import CachedEmbedder, embed_and_upsert, get_redis_client
from embeddings.chunker import chunk_text
from embeddings.collections import get_or_create_collection
from embeddings.loaders import load_pdf_pdfplumber


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _frequency_type(text: str) -> str:
    lower = text.lower()
    if "hf" in lower or "high frequency" in lower:
        return "hf"
    if "mf" in lower or "medium frequency" in lower:
        return "mf"
    return "satcom"


def run(embedder: CachedEmbedder | None = None) -> list[dict]:
    if embedder is None:
        embedder = CachedEmbedder(redis_client=get_redis_client())

    pdf_path = "data/maritime/imo_gmdss_2019.pdf"
    source = Path(pdf_path).name

    # Delete old chunks before re-ingestion (pypdf extracted almost nothing)
    collection = get_or_create_collection("maritime_kb")
    try:
        existing = collection.get(where={"source": source})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"Deleted {len(existing['ids'])} old chunks from maritime_kb")
    except Exception:
        pass  # collection may be empty or filter unsupported

    # Use pdfplumber for better extraction from IMO GMDSS PDF
    pages = load_pdf_pdfplumber(pdf_path)
    full_text = "\n\n".join(pages)

    # pypdf normalization: inject space after sentence-ending punctuation before uppercase
    full_text = re.sub(r"([.!?])([A-Z])", r"\1 \2", full_text)

    chunks = chunk_text(full_text, chunk_size=512, overlap=64, source=source)
    print(f"{source}: {len(chunks)} chunks extracted with pdfplumber")

    for chunk in chunks:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = {
            "category": "gmdss_procedure",
            "region": "global",
            "frequency_type": _frequency_type(chunk["text"]),
        }

    embed_and_upsert("maritime_kb", chunks, embedder=embedder)
    print(f"Total chunks ingested: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    run()
