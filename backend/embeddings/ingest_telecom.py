"""
Ingest the telecom knowledge base.

telecom_kb was declared in COLLECTION_NAMES from the start but never had an
ingest script or any source documents, so it sat at 0 chunks. Telecom
advisories were grounded only by the generic impact_matrix chunks — which is
why they carried LOW_COVERAGE on every run.

Sources are ITU-R Recommendations, which are free to download and are the
governing references for exactly what a geomagnetic storm does to radio links:
HF propagation and MUF collapse, ionospheric scintillation on satellite paths,
and the radio-noise floor. See backend/data/telecom/SOURCES.md.
"""

from __future__ import annotations

import hashlib

from backend.embeddings.chunker import chunk_document
from backend.embeddings.store import embed_and_upsert
from backend.paths import DATA_DIR

# filename -> (category, subsystem the advisory should reason about)
_DOCS: dict[str, tuple[str, str]] = {
    "itu_r_p531_ionospheric_propagation.pdf": ("ionospheric_data", "gnss"),
    "itu_r_p533_hf_propagation_prediction.pdf": ("hf_propagation", "hf_link"),
    "itu_r_p372_radio_noise.pdf": ("radio_noise", "hf_link"),
    "itu_r_p618_earth_space_propagation.pdf": ("scintillation", "satellite_link"),
    # The one source here that is about consequences rather than physics: what a
    # primary reference time clock must do once GNSS traceability is lost, which
    # is the telecom impact operators actually plan around.
    "itu_t_g8272_primary_reference_time_clock.pdf": ("timing_holdover", "network_timing"),
}


def _stable_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:32]


def _impact_tag(text: str) -> str:
    """Coarse tag so retrieval can favour storm-relevant passages."""
    t = text.lower()
    if "holdover" in t or "prtc" in t:
        return "holdover"
    if "scintillation" in t:
        return "scintillation"
    if "muf" in t or "maximum usable frequency" in t:
        return "muf"
    if "absorption" in t or "auroral" in t or "polar cap" in t:
        return "absorption"
    if "total electron content" in t or "tec" in t:
        return "tec"
    if "noise" in t:
        return "noise_floor"
    return "general"


def run() -> list[dict]:
    all_chunks: list[dict] = []
    missing: list[str] = []

    for filename, (category, subsystem) in _DOCS.items():
        path = DATA_DIR / "telecom" / filename
        if not path.exists():
            missing.append(filename)
            continue
        chunks = chunk_document(str(path))
        for chunk in chunks:
            chunk["id"] = _stable_id(chunk["source"], chunk["text"])
            chunk["metadata"] = {
                "category": category,
                "subsystem": subsystem,
                "impact_tag": _impact_tag(chunk["text"]),
            }
        all_chunks.extend(chunks)

    if missing:
        print(
            "MISSING telecom sources (see backend/data/telecom/SOURCES.md):\n  "
            + "\n  ".join(missing)
        )

    if not all_chunks:
        print("No telecom sources present — telecom_kb left empty, nothing ingested.")
        return []

    embed_and_upsert("telecom_kb", all_chunks)
    print(f"Total chunks ingested: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    run()
