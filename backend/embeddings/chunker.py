from __future__ import annotations

from backend.paths import DATA_DIR

import re
from pathlib import Path
from uuid import uuid4

import tiktoken

from backend.embeddings.loaders import load_pdf

_enc: tiktoken.Encoding | None = None


def _encoder() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def _sentence_tokens(para: str) -> list[list[int]]:
    enc = _encoder()
    # pypdf often drops the space between a sentence-ending period and the next capital letter
    normalized = re.sub(r"([.!?])([A-Z])", r"\1 \2", para)
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [enc.encode(s) for s in sentences if s.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    source: str = "",
) -> list[dict]:
    enc = _encoder()

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return []

    # Expand oversized paragraphs into sentences; keep small ones as-is
    segments: list[list[int]] = []
    for para in paragraphs:
        tokens = enc.encode(para)
        if len(tokens) > chunk_size:
            segments.extend(_sentence_tokens(para))
        else:
            segments.append(tokens)

    # Greedily merge segments into chunks, hard-split anything still over limit
    raw_chunks: list[list[int]] = []
    current: list[int] = []

    for tokens in segments:
        if len(tokens) > chunk_size:
            if len(current) > overlap:
                raw_chunks.append(current)
            for i in range(0, len(tokens), chunk_size - overlap):
                raw_chunks.append(tokens[i : i + chunk_size])
            current = tokens[-overlap:]
        elif len(current) + len(tokens) > chunk_size:
            raw_chunks.append(current)
            actual_overlap = min(overlap, chunk_size - len(tokens))
            # Guard: current[-0:] == current[:] in Python, so handle zero overlap explicitly
            current = current[-actual_overlap:] + tokens if actual_overlap > 0 else list(tokens)
        else:
            current = current + tokens

    if len(current) > overlap:
        raw_chunks.append(current)

    return [
        {
            "id": str(uuid4()),
            "text": enc.decode(tokens),
            "source": source,
            "token_count": len(tokens),
        }
        for tokens in raw_chunks
        if tokens
    ]


def chunk_document(
    path: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[dict]:
    """
    Chunk a document PAGE BY PAGE so every chunk carries the page it came from.

    This used to be `"\\n\\n".join(pages)` before a single chunk_text() call,
    which destroyed the page number at ingest time - and no amount of frontend
    work recovers it, so a citation could only ever name a file, never a place
    inside it. Chunking per page is what makes `file.pdf p.42` possible.

    The cost is that chunks no longer span page boundaries, which is a fair
    trade: a citation that straddles two pages cannot point at one anyway.
    """
    source = Path(path).name
    chunks: list[dict] = []

    for page_no, page_text in enumerate(load_pdf(path), start=1):
        if not page_text or not page_text.strip():
            continue
        for chunk in chunk_text(page_text, chunk_size=chunk_size, overlap=overlap, source=source):
            # store._build_metadata() promotes chunk["metadata"] into the Chroma
            # record, so the page has to live there to survive the round trip.
            chunk.setdefault("metadata", {})["page"] = page_no
            chunks.append(chunk)

    avg_tokens = sum(c["token_count"] for c in chunks) / len(chunks) if chunks else 0
    print(f"{source}: {len(chunks)} chunks, avg {avg_tokens:.0f} tokens/chunk")
    return chunks


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else str(DATA_DIR / "aviation/nat_doc_007_2025.pdf")
    chunk_document(path)
