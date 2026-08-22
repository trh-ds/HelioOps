"""
Ingest the maritime knowledge base.

Source history: this used to ingest `imo_gmdss_2019.pdf`, which is not the IMO
GMDSS Manual — it is the 2-page publisher catalogue page advertising it (411KB,
3,804 characters of extractable text, against 160 pages / 417k characters for
the aviation source). It yielded 2 chunks, so maritime advisories were grounded
on a book listing while scoring the highest confidence of any industry.

The IMO GMDSS Manual is a paid IMO publication with no legitimate free
download. The ITU-R M-series Recommendations used here are free, are the
international standards the GMDSS is actually built on, and cover the
storm-relevant part directly: DSC distress procedures, and NAVTEX/MSI coverage
prediction including skywave propagation.

See backend/data/maritime/SOURCES.md.
"""

from __future__ import annotations

import hashlib
import re

from backend.embeddings.chunker import chunk_text
from backend.embeddings.collections import get_or_create_collection
from backend.embeddings.loaders import load_pdf_pdfplumber
from backend.embeddings.store import embed_and_upsert
from backend.paths import DATA_DIR

# filename -> (category, region, page_range)
#
# page_range is None for whole documents. NGA Pub 117 needs one: it is 710
# pages of which only ~118 are prose, and the bulk is a country-by-country
# directory of radio station call signs, frequencies and watch schedules.
# Ingesting all of it would add ~1800 chunks of tabular station listings and
# bury the 174 procedure chunks the ITU-R documents provide — retrieval would
# get worse, not better. Pages 542-581 are the GMDSS / distress / emergency
# procedure block, which is the part that answers an operational question.
_DOCS: dict[str, tuple[str, str, tuple[int, int] | None]] = {
    "itu_r_m541_dsc_operational_procedures.pdf": ("dsc_procedure", "global", None),
    "itu_r_m1467_navtex_coverage_propagation.pdf": ("msi_coverage", "global", None),
    "itu_r_m493_dsc_system.pdf": ("dsc_system", "global", None),
    "itu_r_m1173_hf_radiotelephony.pdf": ("hf_radiotelephony", "global", None),
    "nga_pub117_radio_navigational_aids_2014.pdf": ("gmdss_emergency", "global", (542, 581)),
}

# Superseded source, deliberately not ingested. Listed so a stale copy left in
# the data directory is purged from the collection rather than silently kept.
_RETIRED = ("imo_gmdss_2019.pdf",)


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _frequency_type(text: str) -> str:
    lower = text.lower()
    if "hf" in lower or "high frequency" in lower:
        return "hf"
    if "mf" in lower or "medium frequency" in lower:
        return "mf"
    return "satcom"


def _purge(collection, source: str) -> None:
    try:
        existing = collection.get(where={"source": source})
    except Exception:
        return  # empty collection, or filter unsupported
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])
        print(f"Purged {len(existing['ids'])} chunks from previous '{source}' ingest")


def run() -> list[dict]:
    collection = get_or_create_collection("maritime_kb")
    for stale in _RETIRED:
        _purge(collection, stale)

    all_chunks: list[dict] = []
    missing: list[str] = []

    for filename, (category, region, page_range) in _DOCS.items():
        path = DATA_DIR / "maritime" / filename
        if not path.exists():
            missing.append(filename)
            continue

        # pdfplumber, not pypdf: pypdf extracted almost nothing from these.
        pages = load_pdf_pdfplumber(str(path))
        if page_range:
            first, last = page_range
            pages = pages[first - 1 : last]  # 1-indexed, inclusive
            print(f"{filename}: using pages {first}-{last} of the document")
        _purge(collection, filename)

        # Page by page, so every chunk keeps the page it came from - the same
        # reason chunk_document() stopped joining. This path has its own loader
        # (pdfplumber, because pypdf extracted almost nothing from these), so
        # it needs the same treatment rather than inheriting it.
        page_offset = page_range[0] - 1 if page_range else 0
        chunks = []
        for idx, page_text in enumerate(pages):
            if not page_text or not page_text.strip():
                continue
            # Re-insert the space PDF extraction drops between a sentence-ending
            # punctuation mark and the next capitalised word.
            page_text = re.sub(r"([.!?])([A-Z])", r"\1 \2", page_text)
            for chunk in chunk_text(page_text, chunk_size=512, overlap=64, source=filename):
                # Number against the real document, not the slice, so the link
                # opens the page the operator is actually being cited to.
                chunk.setdefault("metadata", {})["page"] = page_offset + idx + 1
                chunks.append(chunk)
        print(f"{filename}: {len(chunks)} chunks")

        for chunk in chunks:
            chunk["id"] = _stable_id(chunk["source"], chunk["text"])
            chunk.setdefault("metadata", {}).update({
                "category": category,
                "region": region,
                "frequency_type": _frequency_type(chunk["text"]),
            })
        all_chunks.extend(chunks)

    if missing:
        print(
            "MISSING maritime sources (see backend/data/maritime/SOURCES.md):\n  "
            + "\n  ".join(missing)
        )

    if not all_chunks:
        print("No maritime sources present — nothing ingested.")
        return []

    embed_and_upsert("maritime_kb", all_chunks)
    print(f"Total chunks ingested: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    run()
