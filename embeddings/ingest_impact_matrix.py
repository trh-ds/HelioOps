from __future__ import annotations

import hashlib
import re

from embeddings.cache import CachedEmbedder, embed_and_upsert, get_redis_client
from embeddings.chunker import chunk_document

_HISTORICAL_YEARS = {"2003", "2017", "2024"}


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _category(text: str, default: str) -> str:
    if any(year in text for year in _HISTORICAL_YEARS):
        return "historical_case"
    return default


def run(embedder: CachedEmbedder | None = None) -> list[dict]:
    if embedder is None:
        embedder = CachedEmbedder(redis_client=get_redis_client())

    # noaa_tech_memo.pdf
    chunks_memo = chunk_document("data/impact_matrix/noaa_tech_memo.pdf")
    for chunk in chunks_memo:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = {"category": _category(chunk["text"], "technical_report")}

    # nesdis_impacts.pdf
    chunks_nesdis = chunk_document("data/impact_matrix/nesdis_impacts.pdf")
    for chunk in chunks_nesdis:
        chunk["id"] = _stable_id(chunk["source"], chunk["text"])
        chunk["metadata"] = {"category": _category(chunk["text"], "industry_briefing")}

    # noaa_space_weather_scales.txt — split on blank lines, skip tiktoken chunking
    with open("data/impact_matrix/noaa_space_weather_scales.txt", encoding="utf-8") as f:
        raw = f.read()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    chunks_scales = [
        {
            "id": _stable_id("noaa_space_weather_scales.txt", p),
            "text": p,
            "source": "noaa_space_weather_scales.txt",
            "token_count": len(p.split()),
            "metadata": {"category": "impact_matrix"},
        }
        for p in paragraphs
    ]

    all_chunks = chunks_memo + chunks_nesdis + chunks_scales
    embed_and_upsert("impact_matrix_kb", all_chunks, embedder=embedder)
    print(f"Total chunks ingested: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    run()
