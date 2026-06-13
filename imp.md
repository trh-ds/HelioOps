# HelioOps — Complete Implementation Plan
**Team:** Tirth (Full-stack) · Neal (CV & ML) · Priyanshu (RAG & Agentic)  
**Repo:** `C:\Users\Admin\heliops\HelioOps\`  
**Status:** Active build — v2.0 four-layer architecture  
**Last updated:** June 2026

---

## Table of Contents
1. [What We're Building](#1-what-were-building)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Data Sources & Files on Disk](#4-data-sources--files-on-disk)
5. [Embeddings Pipeline — What's Already Done](#5-embeddings-pipeline--whats-already-done)
6. [Feature Specifications](#6-feature-specifications)
7. [Data Contracts](#7-data-contracts)
8. [Database Schema](#8-database-schema)
9. [API Surface](#9-api-surface)
10. [Layer-by-Layer Implementation](#10-layer-by-layer-implementation)
11. [25-Commit Build Roadmap](#11-25-commit-build-roadmap)
12. [Team Roles & RACI](#12-team-roles--raci)
13. [Demo Plan](#13-demo-plan)
14. [Risk Register](#14-risk-register)

---

## 1. What We're Building

HelioOps is a space weather operations platform. It watches the Sun 24/7, detects when a solar storm is forming, figures out exactly how that storm will damage specific infrastructure, writes verified operational instructions for airlines, power grids, and maritime operators, and delivers those instructions in under 3 minutes — before the storm arrives.

**The core gap we fill:**  
NOAA publishes alerts in physicist language: `G4 Watch, Kp 8, R3 in progress`. Operations teams speak regulation language: ICAO procedures, NERC GMD standards, GMDSS protocols. Today that translation is done manually by a handful of expensive specialists, in 2–4 hours, for a handful of large clients. Everyone else gets the generic NOAA text and does nothing with it.

**What we give them instead:**
> *"Reroute North Atlantic tracks below 70°N for the next 3 hours. Switch HF to 5 MHz on affected NAT tracks. Brief crews on a ~50-minute blackout window opening at 18:00 UTC."*

That is a work order. It comes out of our system 3 minutes after the storm is detected. Every number in it has been checked against the official ICAO rulebook before it leaves the system.

### The Four Layers

| Layer | What it does | Who builds |
|---|---|---|
| ① Heliospheric Detection | Spot the CME at the Sun using computer vision on CCOR-1 coronagraph imagery. Measure speed, width, direction. Fuse with NOAA alerts + DSCOVR L1 solar wind → `StormEvent` with days-of-warning. | Neal |
| ② Impact Intelligence | ML model converts storm physics → specific numbers: GPS off by 18–32 m above 60°N, 86% HF blackout probability on 8 MHz, GIC risk index 7.2/10 in southern Sweden. Calibrated 95% CIs. | Neal |
| ③ Verified Advisory | LangGraph agents draft per-industry instructions using RAG over ICAO/NERC/GMDSS procedure KBs. Deterministic verifier checks every number against rulebooks before anything dispatches. | Priyanshu |
| ④ Delivery + Flywheel | FastAPI backend + WebSocket streams every step live. CRM ticket creation, Slack/email delivery, append-only audit trail. Every operator edit becomes training data. | Tirth |

### Target Users

| User | Pain | What we give them |
|---|---|---|
| **Flight dispatcher** (polar/North Atlantic routes) | HF comms on Arctic routes black out with 30-min warning. Reactive re-routing burns fuel. | Specific reroute threshold (e.g. below 70°N), backup HF frequencies (8825/11384/17946 kHz), exact blackout window, hours ahead. |
| **Grid operator / TSO engineer** (Scandinavia, Canada, Scotland) | GIC currents can permanently damage £10M+ transformers. No automated action trigger. | Which transformer zones to protect (Zone A = >60° geomagnetic lat), NERC GMD activation step, risk index by area. |
| **Telecom / PNT lead** (precision agri, autonomous vehicles, financial timing) | GPS L1 accuracy degrades from 5m to 40m with no warning. | GPS error in metres by latitude band, which clients to alert, estimated duration. |
| **Maritime fleet ops** (Baltic/Arctic shippers) | GMDSS HF primary comms fail. No systematic advisory. | GMDSS backup channels, affected route list, degradation window. |

**Mid-market is the target.** Large airlines and national grid operators have in-house analysts. Regional airlines, smaller TSOs, mid-size shippers don't. They have the same exposure and zero guidance.

---

## 2. System Architecture

```
  PUBLIC DATA (all free)              H E L I O O P S                         OUTPUT
 ─────────────────────   ┌──────────────────────────────────────────┐   ─────────────────
  CCOR-1 coronagraph ───►│ ① HELIOSPHERIC DETECTION  (CV)            │
  SUVI EUV / GOES XRS───►│    CME detection (CNN on running-diff)    │   [ NEAL ]
  NOAA SWPC alerts   ───►│    Flare class + R-scale (XRS threshold)  │
  DSCOVR/ACE L1 wind ───►│    Fusion → StormEvent + confidence +     │
                         │    3-point timeline (days/hour/now)        │
                         │                    │ StormEvent            │
                         │                    ▼                       │
                         │ ② IMPACT INTELLIGENCE  (ML/DL)             │   [ NEAL ]
                         │    LightGBM quantile regression            │
                         │    GPS L1 error metres + 95% CI            │
                         │    HF blackout prob per band               │
                         │    GIC risk index per zone (rule-based P0) │
                         │    → ImpactAssessment                      │
                         │                    │                       │
                         │                    ▼                       │
                         │ ③ VERIFIED ADVISORY  (Agentic + symbolic)  │   [ PRIYANSHU ]
                         │    LangGraph fan-out → aviation + grid     │
                         │    RAG: ICAO Doc 007 / NERC GMD / GMDSS    │
                         │    Groq Llama 3.3 70B drafts advisory      │
                         │    Verifier: every number vs rulebook      │
                         │    21 MHz → BLOCKED (not in {3,5,8,11,17}) │
                         │    → VerifiedAdvisory + ProvenanceTrace    │
                         │                    │                       │
                         │                    ▼                       │
                         │ ④ DELIVERY + FLYWHEEL                      │   [ TIRTH ]
                         │    CRM ticket + Slack Block Kit + email    │
                         │    WebSocket live console stream           │
                         │    Append-only audit trail (PostgreSQL)    │
                         │    Operator feedback → flywheel JSONL      │◄─ approve/edit
                         └──────────────────────────────────────────┘
                                       ▲
                          Replay engine (Tirth) orchestrates all layers
                          from cached artifacts — zero live API in demo
```

### Integration Seams (the contracts between three developers)

| Seam | Producer | Consumer | Object | Frozen at |
|---|---|---|---|---|
| Detection → Impact | Neal (Layer ①) | Neal (Layer ②) | `StormEvent` | P1 |
| Impact → Advisory | Neal (Layer ②) | Priyanshu (Layer ③) | `ImpactAssessment` | P1 |
| Advisory → Delivery | Priyanshu (Layer ③) | Tirth (Layer ④) | `VerifiedAdvisory` + `ProvenanceTrace` | P1 |
| Any layer → Console | All | Tirth WebSocket | `WsEvent` envelope | P1 |

---

## 3. Technology Stack

| Category | Choice | Version | Why, not alternatives |
|---|---|---|---|
| CV framework | PyTorch | 2.x | Custom CNN/ViT on solar imagery, Neal's primary framework. |
| Image processing | OpenCV | 4.x | Running-difference imaging, denoising, bounding boxes. Numpy-native. |
| FITS reader | astropy | 6.x | CCOR-1 images are FITS format. `astropy.io.fits` is the standard. `pip install astropy`. |
| Tabular ML | LightGBM | 4.x | Native quantile regression via `objective='quantile'`. Handles missing features. <1ms inference. XGBoost rejected — slower training. |
| Agent orchestration | LangGraph | 0.2 | Stateful typed graph, conditional edges, parallel fan-out, Redis checkpointing. `Annotated[dict, operator.or_]` merges parallel agent outputs. CrewAI rejected — too opaque. |
| LLM inference | Groq — Llama 3.3 70B | — | ~$0.001 per full 4-agent pipeline run. Sub-500ms drafting. `temperature=0.1` for deterministic advisory text. Swap to GPT-4o/Claude in prod. |
| Vector store | ChromaDB PersistentClient | 0.5.x | `./data/chroma_db`, 5 collections, HNSW index, cosine distance. Zero infra cost at hackathon scale. Migrates to Qdrant at prod. |
| Embedding model | BAAI/bge-small-en-v1.5 | — | 384-dim, free/local (no API cost, no egress), `normalize_embeddings=True` (cosine = dot product, matches ChromaDB default). 512-token context matches chunk size exactly. **CRITICAL: always `embed_query()` at retrieval — never `query_texts`** (MiniLM vs BGE = different spaces = meaningless distances). |
| Embedding cache | Redis | 7.x | Key: `emb:` + `sha256(text).hexdigest()`. TTL: 86400s. Cold: 5.73s, warm: 0.03s → **191× speedup**. `fakeredis.FakeRedis()` fallback for dev without Redis server. |
| Backend | FastAPI async | 0.110+ | Native WebSocket, OpenAPI docs auto-gen. Async by default. |
| Real-time push | WebSocket + Redis pub/sub | — | Streams LLM tokens + verifier events to dashboard. Multi-worker safe via pub/sub. |
| Database | PostgreSQL 15 | 15 | JSONB for advisory/provenance (flexible schema), standard SQL for audit + flywheel. |
| Frontend | Next.js 14 | 14 | Tailwind CSS, Recharts for Kp sparklines, React 18 streaming. |
| Scheduler | APScheduler | 3.x | 5-minute NOAA polling loop embedded in FastAPI. |
| Notifications | SendGrid + Slack Bolt SDK | — | HTML email + Slack Block Kit with approve/reject buttons. |
| Infra (hackathon) | Docker + Railway | — | $0 footprint. Cached data baked into image. Zero live-API dependency for demo. |
| Infra (prod path) | AWS ECS Fargate | — | ~$285/month at 5 clients (ECS + RDS + ElastiCache). |

---

## 4. Data Sources & Files on Disk

### Repo structure

```
C:\Users\Admin\heliops\HelioOps\
├── backend/
├── frontend/
├── data/
│   ├── raw/
│   │   ├── aviation/
│   │   │   └── nat_doc_007_2025.pdf          (160 pp, 2.6 MB — ICAO NAT v2025)
│   │   ├── grid/
│   │   │   ├── nerc_tpl007_4.pdf             (38 pp, 534 KB — NERC GMD standard)
│   │   │   ├── nerc_benchmark_gmd.pdf        (26 pp, 1.0 MB — benchmark GMD event)
│   │   │   └── nerc_transformer_thermal.pdf  (18 pp, 1.6 MB — transformer thermal WP)
│   │   ├── maritime/
│   │   │   └── imo_gmdss_2019.pdf            (2 pp usable — pypdf extracts poorly)
│   │   └── impact/
│   │       ├── noaa_tech_memo.pdf            (193 pp, 3.4 MB)
│   │       ├── nesdis_impacts.pdf            (4 pp, 1.8 MB)
│   │       └── noaa_space_weather_scales.txt (64 lines — manually generated, NOAA SWPC blocked 503)
│   ├── chroma_db/                            (ChromaDB persistence directory)
│   ├── cached/                               (TO CREATE: solar imagery cache)
│   │   ├── ccor1/2024-10/                    (FITS files from S3)
│   │   ├── lasco/2024-05/                    (SOHO LASCO for May 2024 G5)
│   │   ├── suvi/2024-10/
│   │   ├── xrs/2024-10/
│   │   ├── l1/2024-10/
│   │   └── alerts/2024-10/
│   ├── exports/                              (flywheel JSONL exports)
│   └── training/
│       └── noaa_archive/                     (NOAA 2000–2024 storm events)
├── genai/
├── ml/
│   ├── checkpoints/                          (frozen model checkpoints)
│   ├── stubs/                                (P1 contract stubs)
│   └── notebooks/
└── embeddings/                               (Priyanshu's RAG layer — Neal built foundation)
    ├── __init__.py
    ├── config.py
    ├── collections.py
    ├── loaders.py
    ├── chunker.py
    ├── embedder.py
    ├── cache.py
    ├── ingest_aviation.py
    ├── ingest_grid.py
    ├── ingest_maritime.py
    └── ingest_impact_matrix.py
```

### NOAA real-time APIs (confirmed working — no auth required)

```bash
# Kp index — 1-minute cadence
GET https://services.swpc.noaa.gov/json/planetary_k_index_1m.json

# Official Watch/Warning/Alert text — updates on new event
GET https://services.swpc.noaa.gov/products/alerts.txt

# GOES X-ray flux — 6-hour window
GET https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json

# DSCOVR L1 solar wind — 1-minute cadence
GET https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json
```

Storm trigger: fire pipeline when `kp_index >= 5.0` (G1 threshold) or a new WATCH/WARNING/ALERT appears in `alerts.txt`.

### CCOR-1 coronagraph imagery (for Neal — Oct 2024 storm)

```bash
# S3 public bucket — no AWS credentials needed
aws s3 sync s3://noaa-nesdis-swfo-ccor-1-pds/2024/10/ \
    data/cached/ccor1/2024-10/ --no-sign-request

# CCOR-1 available from September 2024 (GOES-U launched June 2024)
# 15-minute cadence, FITS format
# Oct 2024 G4 storm: ~Oct 10 2024
```

May 2024 G5 ("Gannon") uses SOHO/LASCO — CCOR-1 didn't exist yet:
```bash
# NASA SOHO archive
# https://soho.nascom.nasa.gov/data/
# LASCO C2 and C3 coronagraphs
```

### PDF download URLs (verified 200 OK)

```bash
# Aviation — ICAO NAT Doc 007 v2025 (160 pp)
curl -L -A "Mozilla/5.0" \
  "https://ops.group/dashboard/wp-content/uploads/2025/04/NAT-Doc-007-V.2025-1_Amd_0_eff_20MAR2025-compressed.pdf" \
  -o data/raw/aviation/nat_doc_007_2025.pdf

# Grid — NERC TPL-007-4 (38 pp)
curl -L "https://www.nerc.com/globalassets/standards/reliability-standards/tpl/tpl-007-4.pdf" \
  -o data/raw/grid/nerc_tpl007_4.pdf

# Grid — NERC Benchmark GMD Event (26 pp)
curl -L "https://www.nerc.com/globalassets/standards/projects/2013-03/benchmark_gmd_event_dec5_redline.pdf" \
  -o data/raw/grid/nerc_benchmark_gmd.pdf

# Grid — Transformer Thermal Impact (18 pp)
curl -L "https://www.nerc.com/globalassets/programs/compliance/compliance-guidance/implementation/tpl-007-1_transformer_thermal_impact_assessment_white_paper.pdf" \
  -o data/raw/grid/nerc_transformer_thermal.pdf

# Maritime — IMO GMDSS 2019 (2 pp usable, pypdf extracts poorly — use pdfplumber)
curl -L "https://wwwcdn.imo.org/localresources/en/OurWork/Safety/Documents/II970E.pdf" \
  -o data/raw/maritime/imo_gmdss_2019.pdf

# Impact — NOAA Tech Memo (193 pp)
curl -L "https://repository.library.noaa.gov/view/noaa/10024/noaa_10024_DS1.pdf" \
  -o data/raw/impact/noaa_tech_memo.pdf

# Impact — NESDIS Industry Briefing (4 pp)
curl -L "https://www.nesdis.noaa.gov/s3/2024-03/Impacts_Briefing_Space_Weather.pdf" \
  -o data/raw/impact/nesdis_impacts.pdf

# NOTE: NOAA SWPC CDN (swpc.noaa.gov/sites/default/files/*) returns 503 for external requests.
# noaa_space_weather_scales.txt was manually generated from public NOAA documentation.
```

---

## 5. Embeddings Pipeline — What's Already Done

**Status: Commits 01–06 complete. Commits 07–09 outstanding.**

### Current collection state

| Collection | Chunks | Source files | Avg tokens | Status |
|---|---|---|---|---|
| `aviation_kb` | 242 | `nat_doc_007_2025.pdf` | 463 | Done |
| `grid_kb` | 101 | `nerc_tpl007_4.pdf` (44) + `nerc_benchmark_gmd.pdf` (42) + `nerc_transformer_thermal.pdf` (15) | ~320 | Done |
| `maritime_kb` | 2 | `imo_gmdss_2019.pdf` | — | **Broken — pypdf extracts almost nothing. Needs pdfplumber reingestion.** |
| `impact_matrix_kb` | 166 | `noaa_tech_memo.pdf` (147) + `nesdis_impacts.pdf` (5) + `noaa_space_weather_scales.txt` (14) | — | Done |
| `telecom_kb` | 0 | No source data yet | — | Empty — P5 stretch |
| **Total** | **511** | | | |

All embedded with `BAAI/bge-small-en-v1.5` (384-dim, L2-normalized, cosine distance). Persisted at `./data/chroma_db`.

### embeddings/config.py

```python
CHROMA_PERSIST_PATH = "./data/chroma_db"
COLLECTION_NAMES = [
    "aviation_kb",
    "grid_kb",
    "maritime_kb",
    "impact_matrix_kb",
    "telecom_kb",
]
```

### embeddings/collections.py — critical bug fixed

```python
from __future__ import annotations  # REQUIRED: chromadb v1.x PersistentClient is a factory
                                     # function, not a class. `PersistentClient | None` raises
                                     # TypeError at runtime without this. Defers annotation
                                     # evaluation to strings.
import chromadb
from embeddings.config import CHROMA_PERSIST_PATH, COLLECTION_NAMES

_client: chromadb.PersistentClient | None = None  # module-level singleton

def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return _client

def get_or_create_collection(name: str):
    return _get_client().get_or_create_collection(name)

def init_all_collections():
    for name in COLLECTION_NAMES:
        c = get_or_create_collection(name)
        print(f"{name}: {c.count()} chunks")

if __name__ == "__main__":
    init_all_collections()
```

**Shadowing trap:** Never run scripts from inside `embeddings/`. Python adds `embeddings/` to `sys.path[0]`, so `import collections` finds `embeddings/collections.py` instead of the stdlib module. chromadb (which does `from collections import defaultdict`) crashes. Always run from project root as `python -m embeddings.collections`.

### embeddings/chunker.py — three bugs found and fixed

**Chunking strategy:** Recursive paragraph → sentence → token (not fixed-size, not header-based). Paragraph boundaries `\n{2,}` are natural units for NERC regulatory clauses like `"4.3. The benchmark GMD Vulnerability Assessment shall be provided: (i) to..."`. Sentence fallback handles dense single-`\n` pages. Token hard-split is last resort.

```python
import re, uuid
from typing import List, Dict
import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64,
               source: str = "") -> List[Dict]:
    # BUG 1 FIX: pypdf drops spaces between sentence-end and next capital.
    # "...NAT region.A large portion..." → regex (?<=[.!?])\s+ never splits.
    # Fix: inject space after sentence-ending punctuation before uppercase.
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)

    paragraphs = re.split(r"\n{2,}", text)
    raw_chunks, current, current_tokens = [], [], 0

    for para in paragraphs:
        tokens = ENCODING.encode(para)
        if len(tokens) > chunk_size:
            # Para too long — split into sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                s_tokens = ENCODING.encode(sent)
                if len(s_tokens) > chunk_size:
                    # Sentence too long — sliding window hard-split
                    step = chunk_size - overlap
                    for i in range(0, len(s_tokens), step):
                        raw_chunks.append(s_tokens[i:i + chunk_size])
                elif current_tokens + len(s_tokens) > chunk_size:
                    raw_chunks.append(current)
                    # BUG 2 FIX: current[-0:] is the ENTIRE list in Python, not empty slice.
                    # When actual_overlap == 0, current[-0:] + s_tokens = 512 + 512 = 1024 tokens.
                    # Fix: conditional on actual_overlap > 0.
                    # BUG 3 FIX: current[-overlap:] + tokens where len(tokens)=511 → 64+511=575.
                    # Fix: cap actual_overlap so combined never exceeds chunk_size.
                    actual_overlap = min(overlap, chunk_size - len(s_tokens))
                    current = (current[-actual_overlap:] + s_tokens
                               if actual_overlap > 0 else list(s_tokens))
                    current_tokens = len(current)
                else:
                    current.extend(s_tokens)
                    current_tokens += len(s_tokens)
        elif current_tokens + len(tokens) > chunk_size:
            raw_chunks.append(current)
            actual_overlap = min(overlap, chunk_size - len(tokens))
            current = (current[-actual_overlap:] + tokens
                       if actual_overlap > 0 else list(tokens))
            current_tokens = len(current)
        else:
            current.extend(tokens)
            current_tokens += len(tokens)

    if current:
        raw_chunks.append(current)

    return [
        {
            "id": str(uuid.uuid4()),
            "text": ENCODING.decode(c),
            "source": source,
            "token_count": len(c),
        }
        for c in raw_chunks
    ]
```

All 511 chunks are strictly ≤ 512 tokens after these fixes.

### embeddings/embedder.py

```python
import os
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
# NOTE: TF 2.21.0 in this environment was compiled against protobuf 6.31.1
# but runtime was 5.29.6 → VersionError at import time.
# Fix: pip install "protobuf>=6.31.1" → resolved to 7.35.0
# The TRANSFORMERS_NO_TF flag alone does NOT guard the modeling_utils → image_transforms
# → tensorflow import path. The protobuf upgrade is the actual fix.

from sentence_transformers import SentenceTransformer

_model = None  # singleton — load once

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model

def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    model = _get_model()
    vecs = model.encode(texts, batch_size=32, normalize_embeddings=True)
    return vecs.tolist()

def embed_query(text: str) -> list[float]:
    """
    BGE asymmetric retrieval: apply query prefix at retrieval time only.
    Documents are indexed WITHOUT prefix. This is the correct BGE convention.
    ALWAYS use this function when querying — never pass text directly to
    collection.query(query_texts=...) because that uses ChromaDB's default
    MiniLM model, not BGE. Different embedding spaces → meaningless cosine
    distances.
    """
    prefixed = "Represent this sentence for searching relevant passages: " + text
    return embed_texts([prefixed], is_query=True)[0]
```

### embeddings/cache.py — Redis + fakeredis fallback

```python
import hashlib, json, redis as _redis
from embeddings.embedder import embed_texts

def get_redis_client():
    try:
        r = _redis.Redis(socket_connect_timeout=1)
        r.ping()
        return r
    except Exception:
        import fakeredis
        print("WARNING: Redis unavailable — using fakeredis (non-persistent)")
        return fakeredis.FakeRedis()

class CachedEmbedder:
    def __init__(self, redis_client=None, redis_url="redis://localhost:6379"):
        self.redis = redis_client or get_redis_client()
        self.TTL = 86400  # 24 hours

    def _key(self, text: str) -> str:
        return "emb:" + hashlib.sha256(text.encode()).hexdigest()  # 64-char hex

    def get(self, text: str) -> list[float]:
        key = self._key(text)
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
        vec = embed_texts([text])[0]
        self.redis.setex(key, self.TTL, json.dumps(vec))
        return vec

def embed_and_upsert(collection_name: str, chunks: list[dict], embedder=None):
    """
    Batch-optimised upsert:
    1. MGET all cache keys in one round-trip
    2. embed only cache misses in one batched model call
    3. write back via PIPELINE (atomic batch)
    4. collection.upsert() — idempotent by design

    Benchmark: 5 chunks cold = 5.73s, warm = 0.03s → 191× speedup
    """
    from embeddings.collections import get_or_create_collection
    emb = embedder or CachedEmbedder()
    collection = get_or_create_collection(collection_name)

    keys = [emb._key(c["text"]) for c in chunks]
    cached_values = emb.redis.mget(keys)

    misses = [(i, chunks[i]["text"]) for i, v in enumerate(cached_values) if v is None]
    if misses:
        miss_texts = [t for _, t in misses]
        new_vecs = embed_texts(miss_texts)
        pipe = emb.redis.pipeline()
        for (i, _), vec in zip(misses, new_vecs):
            pipe.setex(keys[i], emb.TTL, json.dumps(vec))
            cached_values[i] = json.dumps(vec)
        pipe.execute()

    embeddings = [json.loads(v) for v in cached_values]

    # Chunk ID: sha256(source + "::" + text)[:32] for idempotent re-upserts
    import hashlib as _h
    ids = [_h.sha256((c["source"] + "::" + c["text"]).encode()).hexdigest()[:32]
           for c in chunks]
    metadatas = [_build_metadata(c) for c in chunks]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=metadatas,
    )

def _build_metadata(chunk: dict) -> dict:
    meta = {"source": chunk.get("source", ""), "token_count": chunk.get("token_count", 0)}
    meta.update(chunk.get("metadata") or {})
    return meta
```

### Ingestion metadata tagging

**aviation_kb** — 242 chunks from `nat_doc_007_2025.pdf`:
```python
# First-match category assignment
if "hf" in text.lower() or "frequency" in text.lower():
    category = "hf_procedure"
elif "polar" in text.lower() or "latitude" in text.lower():
    category = "reroute_criteria"
elif "solar" in text.lower() or "geomagnetic" in text.lower():
    category = "space_weather"
else:
    category = "general"

storm_scale_relevance = "G3-G5" if any(w in text.lower() for w in ["severe", "extreme"]) else "G1-G5"
```

**grid_kb** — 101 chunks across 3 NERC PDFs:
- `category`: `"nerc_standard"` / `"gic_benchmark"` / `"transformer_thermal"` from filename
- `latitude_zone`: `"A"` if `"60"` AND (`"latitude"` or `"scandinavia"` or `"canada"`) in text; `"B"` if `"50"`; else `"all"`
- Distribution: **9 zone-A, 9 zone-B, 83 all**

⚠️ **Zone-A known issue:** The 9 zone-A chunks describe *"geomagnetic latitude of 60°"* — no chunk contains the phrase "Zone A". A query for *"Zone A Scandinavia"* returns zone-A chunks at **rank 11 of 15**. Fix: use `where={"latitude_zone": "A"}` metadata filter, or rephrase query to *"GIC transformer protection geomagnetic latitude 60 degrees"*.

**maritime_kb** — 2 chunks (BROKEN):  
`imo_gmdss_2019.pdf` extracts almost nothing with `pypdf`. Re-ingest with `pdfplumber`:
```python
import pdfplumber
with pdfplumber.open(path) as pdf:
    pages = [p.extract_text() or "" for p in pdf.pages]
```
Also delete old 2 chunks before re-ingesting:
```python
collection.delete(where={"source": "imo_gmdss_2019.pdf"})
```

**impact_matrix_kb** — 166 chunks:
- `noaa_tech_memo.pdf` → 147 chunks, `category="technical_report"`
- `nesdis_impacts.pdf` → 5 chunks, `category="industry_briefing"`
- `noaa_space_weather_scales.txt` → 14 chunks split on blank lines, `category="impact_matrix"`
- Any chunk containing `"2003"`, `"2017"`, or `"2024"` → override to `category="historical_case"`

### Verified query results

```
aviation_kb  query: "G4 storm HF blackout polar route reroute 78 degrees north"
→ VOLMET SIGMET broadcast, category=hf_procedure, storm_scale=G3-G5  ✓

grid_kb  query: "GIC risk transformer protection Zone A Scandinavia G3 storm"
→ Transformer Thermal Impact Assessment (zone-A at rank 11 — use where filter)  ✓

impact_matrix_kb  query: "G4 geomagnetic storm industry impacts aviation grid March 2024"
→ May 2024 G4-G5 storm entry from noaa_space_weather_scales.txt  ✓

maritime_kb  query: "GMDSS HF backup channel storm"
→ IMO GMDSS title/cover chunk (only 2 chunks — needs pdfplumber reingestion)  ⚠️
```

### Commits 07–09 still outstanding

**Commit 07** `fix(maritime) + feat(retrieval): pdfplumber reingestion + query_kb + MMR`

```python
# embeddings/retrieval.py

import numpy as np
from embeddings.collections import get_or_create_collection
from embeddings.embedder import embed_query
from embeddings.config import COLLECTION_NAMES

def query_kb(
    collection_name: str,
    query_text: str,
    n_results: int = 5,
    use_mmr: bool = True,
    where: dict = None,
) -> list[dict]:
    collection = get_or_create_collection(collection_name)
    n_total = collection.count()
    if n_total == 0:
        return []

    # ALWAYS use embed_query() — not query_texts (wrong model → wrong distances)
    query_vec = embed_query(query_text)
    n_fetch = min(20, n_total)  # guard against small collections (maritime = 2)

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_fetch,
        where=where,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    docs  = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    embs  = np.array(results["embeddings"][0])  # shape (n_fetch, 384)
    query_arr = np.array(query_vec)

    # Cosine distance ∈ [0,2] for L2-normalized vectors → sim = 1 - dist
    sims_to_query = 1 - np.array(dists)

    if not use_mmr or len(docs) <= n_results:
        return [{"text": d, "source": m.get("source",""), "metadata": m, "distance": dist}
                for d, m, dist in zip(docs, metas, dists)][:n_results]

    # MMR greedy selection — λ = 0.7 (70% relevance, 30% diversity)
    LAMBDA = 0.7
    selected, selected_embs = [], []

    for _ in range(min(n_results, len(docs))):
        if not selected:
            best = int(np.argmax(sims_to_query))
        else:
            sel_mat = np.array(selected_embs)  # (k, 384), L2-normalized
            # max cosine similarity to any already-selected chunk
            sim_to_selected = (embs @ sel_mat.T).max(axis=1)  # dot = cosine (normalized)
            scores = LAMBDA * sims_to_query - (1 - LAMBDA) * sim_to_selected
            scores[[s["_idx"] for s in selected]] = -np.inf  # exclude already picked
            best = int(np.argmax(scores))

        selected.append({"text": docs[best], "source": metas[best].get("source",""),
                         "metadata": metas[best], "distance": dists[best], "_idx": best})
        selected_embs.append(embs[best])

    return [{k: v for k, v in s.items() if k != "_idx"} for s in selected]


def format_context(results: list[dict]) -> str:
    """Numbered context block injected into LLM system prompt."""
    return "\n\n".join(
        f"[{i+1}] (source: {r['source']} | category: {r['metadata'].get('category','general')})\n{r['text']}"
        for i, r in enumerate(results)
    )


def query_all_kbs(query: str, n_per_collection: int = 3) -> dict:
    """Query all populated collections. Skip empty ones (telecom_kb = 0 chunks)."""
    out = {}
    for name in COLLECTION_NAMES:
        c = get_or_create_collection(name)
        if c.count() == 0:
            print(f"WARNING: {name} skipped — no data")
            continue
        out[name] = query_kb(name, query, n_results=n_per_collection)
    return out
```

**Commit 08** `test(kb): G4 fixture + corrected grid query + zone-A filter + maritime edge case`

```python
# tests/fixtures/march_2024_g4.json
{
  "g_scale": 4, "kp_index": 8.3, "r_scale": 2,
  "eta_minutes": 45, "peak_window": "2024-05-11T06:00Z/18:00Z"
}
```

Key test changes vs original plan:
- **Grid query must use actual text language**: `"GIC transformer protection geomagnetic latitude 60 degrees"` not `"Zone A Scandinavia"` (no chunk contains "Zone A")
- **Separate zone-A filter test**: `query_kb("grid_kb", "GIC protection latitude", where={"latitude_zone": "A"}, n_results=5)` → assert all results have `metadata["latitude_zone"] == "A"`
- **Maritime assertion**: `len(results) >= 1` (not 3 — only 2 chunks even after pdfplumber)
- **Telecom xfail**: `@pytest.mark.xfail(reason="telecom_kb empty", strict=True)`
- **Embedding consistency**: embed same text twice, assert `np.dot(v1, v2) > 0.999`

---

## 6. Feature Specifications

### F1 — Heliospheric Detection [P0] — Neal

**What it does:** CV on solar imagery detects the storm at the Sun. Fuses CME kinematics + flare + L1 wind + NOAA alerts → `StormEvent` with days-of-warning.

**Sub-features:**

**F1.a — CME detection + kinematics on CCOR-1 [P0]**  
Input: cached CCOR-1 FITS sequence, Oct 2024 storm  
Process: running-difference imaging → CNN classifier → bounding region → frame-to-frame centroid tracking  
Output: `cme.speed_km_s`, `cme.angular_width_deg`, `cme.direction`, `cme.arrival_estimate`

**F1.b — Flare detection + R-scale on SUVI/XRS [P0]**  
Input: GOES XRS 1-8 Angstrom flux time series  
Process: peak flux threshold → M/X class → R-scale map  
Output: `flare.class`, `flare.r_scale`, `flare.onset`  
Note: R-scale fires immediately — radio effects travel at light speed, ~8 min to Earth

**F1.c — Fusion + confidence + timeline [P0]**  
Input: F1.a + F1.b + DSCOVR L1 (`speed_km_s`, `bz_nt`) + `alerts.txt`  
Output: `StormEvent` with:
- `confidence = 0.4×cme_conf + 0.2×flare_certainty + 0.2×bz_southward + 0.2×noaa_alert_present`
- `timeline[0]`: days-out (CCOR-1 CME arrival estimate)
- `timeline[1]`: ~1 hour (L1 ETA = 1,500,000 km / wind_speed_kmps / 60)
- `timeline[2]`: onset-now (Kp threshold crossing)

**F1.d — May 2024 anchor uses SOHO/LASCO [P0]**  
CCOR-1 launched June 2024. May 2024 G5 ("Gannon storm") uses SOHO/LASCO C2/C3. Same pipeline, different source. `cme.source = "SOHO/LASCO"`.

**Acceptance criteria:**
- Given Oct 2024 cached CCOR-1 sequence → CME detected with kinematics, **byte-identical on every run**
- Given SUVI/XRS with X-class flare → R-scale >= 3 emitted
- Given May 2024 → SOHO/LASCO used, valid `StormEvent` produced
- Given no CME in frame → `cme.detected=False`, do NOT block downstream
- Given corrupt frame → skip, interpolate timeline, never crash

---

### F2 — Impact Intelligence [P0] — Neal

**What it does:** Trained LightGBM model converts storm physics → specific numbers with 95% confidence intervals.

**P0 outputs:**

| Output | Example (G4 storm) | `ImpactAssessment` field |
|---|---|---|
| GPS L1 position error | 25 m (CI: 18–32 m, 95%), worsening above 60°N | `domain=gps_pnt, metric=l1_position_error_m` |
| HF blackout probability | 0.86 on 8 MHz, North Atlantic | `domain=hf_radio, metric=blackout_probability, band_mhz=8.0` |
| GIC risk index (rule-based at P0) | 7.2/10, southern Sweden zone | `domain=grid_gic, source=rule_based` |

**GPS error proxy formula** (for training label generation where ground truth is unavailable):
```
error_m ≈ 0.162 × (Kp - 3)^1.8   for Kp > 3
         = 0                        for Kp ≤ 3
```

**Conservative severity floor** (fallback when `low_confidence=True`):

| G-scale | GPS L1 error (m) | HF blackout prob (8 MHz, N.Atlantic) | GIC risk |
|---|---|---|---|
| G1 | 2–5 m | 0.10 | 1/10 |
| G2 | 5–10 m | 0.25 | 3/10 |
| G3 | 10–20 m | 0.55 | 6/10 |
| G4 | 15–35 m | 0.85 | 8/10 |
| G5 | 30–60 m | 0.97 | 10/10 |

**Training:**
```python
import lightgbm as lgb

params_low    = {"objective": "quantile", "alpha": 0.025, "metric": "quantile", "n_estimators": 300}
params_median = {"objective": "quantile", "alpha": 0.500, "metric": "quantile", "n_estimators": 300}
params_high   = {"objective": "quantile", "alpha": 0.975, "metric": "quantile", "n_estimators": 300}

model_low    = lgb.train(params_low,    train_data)
model_median = lgb.train(params_median, train_data)
model_high   = lgb.train(params_high,   train_data)

# Output: value=median, ci_low=q025, ci_high=q975
```

**Validation anchor — May 2024 G5 documented impacts:**
- GPS degradation: 15–40 m on L1 civilian receivers (widely reported)
- HF blackout: polar routes blacked out ~8 hours
- GIC warnings issued in Canada, UK, Scandinavia, auroras visible at 17°N (India)

Model output for May 2024 must be directionally consistent: GPS median > 15 m, HF blackout > 0.80.

**Acceptance criteria:**
- Given G4 `StormEvent` → GPS error CI range < 50 m wide (not the 0–100 m floor)
- Given OOD input (speed > 3000 km/s) → `low_confidence=True`, `source="severity_floor"`
- Given same input twice → byte-identical output (frozen checkpoint, `torch.manual_seed(42)`)

---

### F3 — Verified Advisory [P0] — Priyanshu

**What it does:** LangGraph agents draft per-industry advisories using RAG. Deterministic verifier checks every number before dispatch.

**The verifier — the hard gate:**

```python
ICAO_NAT_HF_BANDS_MHZ = {3, 5, 8, 11, 17}

def verify_hf_band(value_mhz: float) -> CheckResult:
    if value_mhz in ICAO_NAT_HF_BANDS_MHZ:
        return CheckResult(status="pass", value=value_mhz)
    nearest = min(ICAO_NAT_HF_BANDS_MHZ, key=lambda b: abs(b - value_mhz))
    return CheckResult(
        status="blocked",
        value=value_mhz,
        corrected_to=nearest,
        reason=f"{value_mhz} MHz not in ICAO NAT valid set {sorted(ICAO_NAT_HF_BANDS_MHZ)}",
    )

# verify_hf_band(21.0)
# → CheckResult(status="blocked", value=21.0, corrected_to=17,
#               reason="21.0 MHz not in ICAO NAT valid set [3, 5, 8, 11, 17]")
```

**WOW #2 — the 21 MHz block (scripted, fires every demo run):**  
LLM drafts `"switch HF to 21 MHz"` → verifier fires → blocked → corrected to 5 MHz → logged → console shows *"LLM proposal blocked by verifier — invalid HF band. No hallucinated frequency reached the dispatcher."*

**Verifier rulebook:**

| Value type | Authoritative source | Valid set / check |
|---|---|---|
| HF frequency | ICAO NAT Doc 007 | Must be in `{3, 5, 8, 11, 17}` MHz |
| Rerouting latitude | Published NAT rerouting criteria | G3+: below 78°N; G4+: below 70°N |
| GIC operating step | NERC GMD TPL-007-4 | Must be a defined step in Appendix B |
| GMDSS channel | ITU / GMDSS references | Must be a valid GMDSS distress/working channel |

**Verifier behavior:**
- `pass` → value in source → keep
- `corrected` → invalid but clear nearest valid substitute → correct + log
- `blocked` → invalid, no safe substitute, or un-checkable → flag for human, never auto-dispatch

**Acceptance criteria:**
- Given draft with `"21 MHz"` → status=`"blocked"`, corrected_to=`5`, logged, visible on console
- Given any dispatched advisory → every operational number in it exists in the rulebook
- Given no RAG procedure found → emit `"no authoritative procedure — escalate to human"`

---

### F4 — Delivery + Flywheel [P0/P1] — Tirth

- **CRM ticket [P0]**: on `VerifiedAdvisory` received, create ticket with work order + provenance link. Idempotency key = `advisory_id` (prevents double tickets on retry).
- **Slack Block Kit [P0]**: numbered actions + approve/reject interactive buttons. Webhook → `POST /advisory/{id}/action`.
- **Audit trail [P0]**: append-only log, never DELETE or UPDATE. Every event timestamped.
- **WebSocket live stream [P0]**: `agent_token` events stream LLM output token-by-token to console.
- **Flywheel capture [P1]**: `operator_action + edited_fields` → `feedback_log` → JSONL export for LoRA fine-tuning.

---

### F5 — Mission Control Console [P0] — Tirth

| Surface | Content | Priority |
|---|---|---|
| Storm banner | G/S/R scales, confidence, severity colour (gray/amber/orange/red), `aria-live="assertive"` for CRITICAL | P0 |
| Multi-horizon timeline | days-out node → 1-hour node → onset-now node, fills as detection runs | P0 |
| Detection panel | Solar image + CME bounding box overlay + `speed_km_s`, `angular_width_deg`, arrival estimate | P0 — WOW #1 |
| Impact panel | GPS error metres + CI bars, HF blackout %, `low_confidence` badge in amber | P0 — WOW #2 partial |
| Verifier panel | Streamed `VerifierCheck` rows; blocked row has red glow + shake animation | P0 — WOW #2 |
| Advisory cards | Per-industry: severity, numbered actions, timing window, cited procedure | P0 |
| CRM ticket view | Dispatched work order with provenance link | P0 |
| Provenance trace | One-click 6-step stepper: raw data → detection → impact → retrieval → verifier → output | P0 |
| Replay controls | Choose storm (May 2024 G5 / Oct 2024 G4), play/pause/scrub, deterministic | P0 |
| Operator action UI | Approve/edit/reject → flywheel | P1 |

---

## 7. Data Contracts

### 7.1 StormEvent — Neal produces

```jsonc
{
  "storm_id": "2024-10-G4",
  "detected_at": "2024-10-10T12:34:00Z",
  "confidence": 0.91,
  "scales": { "G": 4, "S": 2, "R": 3 },
  "cme": {
    "detected": true,
    "source": "CCOR-1",           // "SOHO/LASCO" for May 2024
    "speed_km_s": 1480,
    "angular_width_deg": 110,
    "direction": "earth_directed",
    "arrival_estimate": "2024-10-11T18:00:00Z",
    "confidence": 0.88
  },
  "flare": {
    "detected": true,
    "class": "X1.2",
    "r_scale": 3,
    "source": "GOES-XRS+SUVI",
    "onset": "2024-10-10T12:30:00Z"
  },
  "l1_solar_wind": {
    "speed_km_s": 720,
    "bz_nt": -28,                 // negative = southward = more geomagnetic activity
    "measured_at": "2024-10-11T17:10:00Z",
    "eta_minutes": 35             // 1_500_000 km / 720 km/s / 60 = 34.7 min
  },
  "timeline": [
    { "horizon": "days_out", "source": "CCOR-1 CME",   "t": "2024-10-10T12:34:00Z" },
    { "horizon": "one_hour", "source": "L1 wind",       "t": "2024-10-11T17:10:00Z" },
    { "horizon": "onset",    "source": "geomagnetic",   "t": "2024-10-11T18:00:00Z" }
  ],
  "noaa_alert_raw": "G4 Watch, Kp 8, R3 in progress"
}
```

### 7.2 ImpactAssessment — Neal produces

```jsonc
{
  "storm_id": "2024-10-G4",
  "model_version": "impact-v0.3-frozen",
  "low_confidence": false,
  "source": "model",              // "severity_floor" when low_confidence=true
  "impacts": [
    {
      "domain": "gps_pnt",
      "metric": "l1_position_error_m",
      "value": 25, "ci_low": 18, "ci_high": 32, "ci_level": 0.95,
      "qualifier": "worsening above 60N"
    },
    {
      "domain": "hf_radio",
      "metric": "blackout_probability",
      "band_mhz": 8.0,
      "route": "north_atlantic",
      "value": 0.86, "ci_low": 0.79, "ci_high": 0.92, "ci_level": 0.95
    },
    {
      "domain": "grid_gic",
      "metric": "gic_risk_index",
      "zone": "southern_sweden",
      "value": 7.2, "scale_max": 10,
      "source": "rule_based"      // model head not trained yet — rule-based fallback at P0
    }
  ]
}
```

### 7.3 VerifiedAdvisory — Priyanshu produces

```jsonc
{
  "advisory_id": "adv_2024-10-G4_aviation_001",
  "storm_id": "2024-10-G4",
  "industry": "aviation",
  "severity": "high",
  "numbered_actions": [
    "Reroute all North Atlantic tracks below 70N for the next 3 hours.",
    "Switch HF comms to 5 MHz on all affected NAT tracks.",
    "Brief crews on a 50-minute blackout window opening at 18:00 UTC."
  ],
  "timing_window": { "opens": "2024-10-11T18:00:00Z", "duration_min": 50 },
  "technical_details": "R3 radio blackout. HF degraded on 8 MHz NAT band (p=0.86, 95% CI 0.79–0.92).",
  "cited_procedure": { "source": "ICAO NAT Doc 007", "ref": "HF backup band table" },
  "verifier": {
    "status": "passed_with_corrections",
    "checks": [
      {
        "field": "hf_band",
        "proposed": 21,           // LLM wrote 21 MHz
        "status": "blocked",
        "corrected_to": 5,        // nearest valid in {3,5,8,11,17}
        "reason": "21 MHz not in ICAO NAT valid set [3, 5, 8, 11, 17]"
      },
      { "field": "reroute_latitude", "proposed": 70, "status": "pass" }
    ]
  },
  "provenance_ref": "trace_adv_2024-10-G4_aviation_001",
  "requires_human": false
}
```

### 7.4 ProvenanceTrace — Priyanshu produces

```jsonc
{
  "trace_id": "trace_adv_2024-10-G4_aviation_001",
  "advisory_id": "adv_2024-10-G4_aviation_001",
  "chain": [
    { "step": "raw_data",   "ref": "data/cached/ccor1/2024-10/seq_001.fits" },
    { "step": "detection",  "ref": "StormEvent:2024-10-G4", "confidence": 0.91 },
    { "step": "impact",     "ref": "ImpactAssessment:2024-10-G4", "ci_level": 0.95 },
    { "step": "retrieval",  "ref": "ICAO NAT Doc 007 :: HF backup band table" },
    { "step": "verifier",   "ref": "blocked 21 MHz → corrected to 5 MHz" },
    { "step": "output",     "ref": "VerifiedAdvisory:adv_2024-10-G4_aviation_001" }
  ]
}
```

### 7.5 WsEvent — Tirth transports

```jsonc
{
  "type": "detection | impact | agent_token | verifier_check | dispatch | audit",
  "storm_id": "2024-10-G4",
  "ts": "2024-10-11T17:10:01Z",
  "payload": { }  // shape depends on type
}
```

---

## 8. Database Schema

```sql
-- storm_events
CREATE TABLE storm_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id         VARCHAR(64) UNIQUE,        -- sha256(noaa_alert_raw) for deduplication
    raw_payload      TEXT,
    g_scale          SMALLINT,
    s_scale          SMALLINT,
    r_scale          SMALLINT,
    kp_index         DECIMAL(4,1),
    storm_event_json JSONB,                     -- full StormEvent object from Neal
    status           VARCHAR(20) DEFAULT 'raw', -- raw|detecting|assessing|advising|delivered|resolved
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_storm_alert_id ON storm_events(alert_id);

-- advisories
CREATE TABLE advisories (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storm_event_id   UUID REFERENCES storm_events(id),
    industry         VARCHAR(20),               -- aviation|grid|telecom|maritime
    severity         VARCHAR(10),               -- critical|high|medium|low
    advisory_json    JSONB,                     -- full VerifiedAdvisory — flexible schema
    verifier_status  VARCHAR(30),               -- passed|passed_with_corrections|blocked
    status           VARCHAR(20) DEFAULT 'pending',
    confidence       DECIMAL(3,2),
    approved_by      VARCHAR(100),              -- NULL = auto-approved after timeout
    approved_at      TIMESTAMPTZ,
    generation_ms    INTEGER
);
CREATE INDEX idx_advisories_storm_id ON advisories(storm_event_id);

-- provenance_traces
CREATE TABLE provenance_traces (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advisory_id  UUID REFERENCES advisories(id),
    trace_json   JSONB,                         -- full ProvenanceTrace — 6-step chain
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- feedback_log (data flywheel)
CREATE TABLE feedback_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advisory_id      UUID REFERENCES advisories(id),
    operator_action  VARCHAR(30) CHECK (operator_action IN ('approved','edited','rejected','escalated')),
    edited_fields    JSONB,                     -- {field: {before, after}} — correction delta
    outcome          VARCHAR(30),               -- actions_taken|false_positive|storm_subsided
    operator_notes   TEXT,
    logged_at        TIMESTAMPTZ DEFAULT NOW(),
    -- DB-level integrity: if edited, must have the diff
    CONSTRAINT edited_requires_fields CHECK (
        operator_action != 'edited' OR edited_fields IS NOT NULL
    )
);
CREATE INDEX idx_feedback_advisory ON feedback_log(advisory_id);
CREATE INDEX idx_feedback_logged_at ON feedback_log(logged_at);

-- audit_log (NEVER DELETE FROM THIS TABLE)
CREATE TABLE audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storm_id     VARCHAR,
    event_type   VARCHAR(30),                   -- detection|impact|draft|verifier|dispatch|operator_action
    payload      JSONB,
    actor        VARCHAR(50),                   -- 'system' or operator id
    ts           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_storm ON audit_log(storm_id);
CREATE INDEX idx_audit_ts ON audit_log(ts);
```

---

## 9. API Surface

### REST

| Method | Route | Purpose | Auth |
|---|---|---|---|
| `GET` | `/storms` | List available replay storms (`2024-05-G5`, `2024-10-G4`) | API key |
| `POST` | `/replay/{storm_id}/start` | Start deterministic replay | API key |
| `POST` | `/replay/{storm_id}/control` | `{action: play|pause|scrub|reset}` | API key |
| `GET` | `/advisory/{advisory_id}` | Fetch full `VerifiedAdvisory` | API key |
| `GET` | `/provenance/{trace_id}` | Fetch `ProvenanceTrace` | API key |
| `GET` | `/audit?storm_id=...` | Fetch append-only audit log | API key |
| `POST` | `/advisory/{id}/action` | `{operator_action, edited_fields, outcome}` | API key + role |
| `WS` | `/ws/stream?storm_id=...` | Live `WsEvent` stream | API key |

### WebSocket event payloads

```jsonc
// type: "detection"
{ "storm_event": { /* full StormEvent */ } }

// type: "impact"
{ "impact_assessment": { /* full ImpactAssessment */ } }

// type: "agent_token"
{ "industry": "aviation", "token": "Switch", "cumulative_text": "Switch HF to" }

// type: "verifier_check"
{ "field": "hf_band", "proposed": 21, "status": "blocked", "corrected_to": 5,
  "reason": "21 MHz not in ICAO NAT valid set [3, 5, 8, 11, 17]" }

// type: "dispatch"
{ "advisory_id": "adv_...", "channels": ["slack", "email"], "ticket_id": "CRM-001" }
```

---

## 10. Layer-by-Layer Implementation

### Layer ① — Heliospheric Detection (Neal)

**Dependencies:** `astropy`, `opencv-python`, `torch`, `torchvision`, `numpy`

**Step 1 — Load and pre-process CCOR-1 FITS**
```python
from astropy.io import fits
import numpy as np, cv2

def load_ccor1_frame(path: str) -> np.ndarray:
    with fits.open(path) as hdul:
        data = hdul[0].data.astype(np.float32)
    # normalize to [0,1]
    data = (data - data.min()) / (data.max() - data.min() + 1e-8)
    return data

def running_difference(frames: list[np.ndarray]) -> list[np.ndarray]:
    """Subtract previous frame — CME appears as moving bright arc."""
    return [frames[i] - frames[i-1] for i in range(1, len(frames))]

def preprocess(frame: np.ndarray) -> np.ndarray:
    """Denoise and normalize difference frame."""
    frame = np.clip(frame, 0, None)                       # keep positive (CME) signal
    frame = cv2.GaussianBlur(frame, (3, 3), 0)           # reduce sensor noise
    return (frame / (frame.max() + 1e-8) * 255).astype(np.uint8)
```

**Step 2 — CME detection (CNN)**
```python
import torch, torch.nn as nn

class CMEDetector(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((8, 8)),
        )
        self.classifier = nn.Linear(64*8*8, 2)   # CME / no-CME

    def forward(self, x): return self.classifier(self.features(x).flatten(1))

# Inference — deterministic (frozen checkpoint, no dropout, eval mode)
torch.manual_seed(42)
model = CMEDetector()
model.load_state_dict(torch.load("ml/checkpoints/cme-v0.1-frozen.pt"))
model.eval()
```

**Step 3 — Kinematics**
```python
def estimate_kinematics(
    centroids: list[tuple],   # (x, y) pixel positions of CME front per frame
    plate_scale_deg_px: float = 0.0225,  # CCOR-1 approximate
    solar_radius_km: float = 695_700,
    cadence_sec: float = 900,            # 15-minute cadence
) -> dict:
    # plane-of-sky speed from frame-to-frame centroid displacement
    displacements = [
        np.linalg.norm(np.array(centroids[i]) - np.array(centroids[i-1]))
        for i in range(1, len(centroids))
    ]
    avg_disp_px = np.mean(displacements)
    speed_km_s = avg_disp_px * plate_scale_deg_px * (np.pi/180) * solar_radius_km / cadence_sec

    # arrival time: 1 AU = 1.496e8 km
    eta_seconds = 1.496e8 / speed_km_s
    from datetime import datetime, timedelta, timezone
    arrival = datetime.now(timezone.utc) + timedelta(seconds=eta_seconds)

    return {
        "speed_km_s": round(speed_km_s, 1),
        "arrival_estimate": arrival.isoformat(),
        "angular_width_deg": 110.0,   # from bounding region extent (placeholder)
    }
```

**Step 4 — Flare + R-scale from GOES XRS**
```python
import json, requests

R_SCALE_MAP = {
    "M1": 1, "M2": 1, "M3": 1, "M4": 1,
    "M5": 2, "M6": 2, "M7": 2, "M8": 2, "M9": 2,
    "X1": 3, "X2": 3, "X3": 3, "X4": 3, "X5": 3,
    "X6": 3, "X7": 3, "X8": 3, "X9": 3,
    "X10": 4,
    "X20": 5,
}

def classify_flare(peak_flux_wm2: float) -> tuple[str, int]:
    """Returns (class_string, r_scale)."""
    if peak_flux_wm2 >= 1e-3:
        r = 5 if peak_flux_wm2 >= 2e-3 else 4
        n = peak_flux_wm2 / 1e-4
        return f"X{n:.1f}", r
    elif peak_flux_wm2 >= 1e-4:
        n = peak_flux_wm2 / 1e-5
        key = f"X{int(n)}" if n >= 1 else "M9"
        return f"X{n:.1f}", R_SCALE_MAP.get(key, 3)
    elif peak_flux_wm2 >= 1e-5:
        n = peak_flux_wm2 / 1e-6
        key = f"M{int(n)}"
        return f"M{n:.1f}", R_SCALE_MAP.get(key, 1)
    return "C", 0
```

**Step 5 — Fusion → StormEvent**
```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

class StormEvent(BaseModel):
    storm_id: str
    detected_at: str
    confidence: float
    scales: dict
    cme: dict
    flare: dict
    l1_solar_wind: dict
    timeline: list
    noaa_alert_raw: str

def fuse(cme_result: dict, flare_result: dict,
         l1: dict, noaa_alert: str, storm_id: str) -> StormEvent:
    # Calibrated confidence
    bz_southward = 1.0 if l1["bz_nt"] < 0 else 0.0
    confidence = (
        0.4 * cme_result.get("confidence", 0.0) +
        0.2 * (1.0 if flare_result["detected"] else 0.0) +
        0.2 * bz_southward +
        0.2 * (1.0 if noaa_alert.strip() else 0.0)
    )
    eta = int(1_500_000 / l1["speed_km_s"] / 60)  # minutes from L1
    now = datetime.now(timezone.utc).isoformat()

    return StormEvent(
        storm_id=storm_id,
        detected_at=now,
        confidence=round(confidence, 3),
        scales={"G": l1.get("g_scale", 0), "S": 0, "R": flare_result["r_scale"]},
        cme=cme_result,
        flare=flare_result,
        l1_solar_wind={**l1, "eta_minutes": eta},
        timeline=[
            {"horizon": "days_out", "source": cme_result.get("source","CCOR-1"),
             "t": cme_result.get("arrival_estimate", now)},
            {"horizon": "one_hour", "source": "L1 wind", "t": now},
            {"horizon": "onset",    "source": "geomagnetic", "t": now},
        ],
        noaa_alert_raw=noaa_alert,
    )

def detect(storm_id: str) -> StormEvent:
    """Entry point called by Tirth's replay engine."""
    # P1: load from stub
    # P2+: run real CV pipeline
    import json
    stub = json.load(open(f"ml/stubs/storm_event_{storm_id}.json"))
    return StormEvent(**stub)
```

---

### Layer ② — Impact Intelligence (Neal)

**Dependencies:** `lightgbm`, `scikit-learn`, `pandas`, `numpy`

**Feature vector for model input:**
```python
import pandas as pd, numpy as np

FEATURE_COLS = [
    "g_scale",          # 0–5
    "kp_index",         # 0.0–9.0
    "bz_nt",            # negative = more activity
    "wind_speed_km_s",  # solar wind speed
    "cme_speed_km_s",   # 0 if no CME
    "cme_width_deg",    # 0 if no CME
    "r_scale",          # 0–5
    "geomag_lat_bin",   # 0=equatorial, 1=mid-lat, 2=high-lat (>60°)
    "local_time_bin",   # 0=night, 1=day (ionosphere differs)
]

def storm_event_to_features(storm: dict, geomag_lat: float = 55.0,
                             local_time_h: float = 12.0) -> pd.DataFrame:
    return pd.DataFrame([{
        "g_scale":          storm["scales"]["G"],
        "kp_index":         storm["scales"]["G"] * 1.5 + 2,  # approx if Kp not in event
        "bz_nt":            storm["l1_solar_wind"]["bz_nt"],
        "wind_speed_km_s":  storm["l1_solar_wind"]["speed_km_s"],
        "cme_speed_km_s":   storm["cme"].get("speed_km_s", 0) if storm["cme"]["detected"] else 0,
        "cme_width_deg":    storm["cme"].get("angular_width_deg", 0) if storm["cme"]["detected"] else 0,
        "r_scale":          storm["scales"]["R"],
        "geomag_lat_bin":   2 if geomag_lat > 60 else (1 if geomag_lat > 45 else 0),
        "local_time_bin":   1 if 6 <= local_time_h <= 18 else 0,
    }])
```

**assess() entry point:**
```python
import joblib, json
from pydantic import BaseModel

SEVERITY_FLOOR = {
    1: {"gps_error": (2,  5),  "hf_blackout": 0.10, "gic": 1.0},
    2: {"gps_error": (5,  10), "hf_blackout": 0.25, "gic": 3.0},
    3: {"gps_error": (10, 20), "hf_blackout": 0.55, "gic": 6.0},
    4: {"gps_error": (15, 35), "hf_blackout": 0.85, "gic": 8.0},
    5: {"gps_error": (30, 60), "hf_blackout": 0.97, "gic": 10.0},
}

def assess(storm: dict, geomag_lat: float = 55.0,
           local_time_h: float = 12.0) -> dict:
    """
    Entry point called by Tirth's replay engine.
    Returns ImpactAssessment dict.
    """
    g = storm["scales"]["G"]
    X = storm_event_to_features(storm, geomag_lat, local_time_h)

    # OOD detection: Z-score on wind speed and CME speed
    wind = storm["l1_solar_wind"]["speed_km_s"]
    low_confidence = (wind > 2500 or wind < 200 or g == 0)

    if low_confidence:
        floor = SEVERITY_FLOOR.get(g, SEVERITY_FLOOR[1])
        return {
            "storm_id": storm["storm_id"],
            "model_version": "severity_floor",
            "low_confidence": True,
            "source": "severity_floor",
            "impacts": [
                {"domain": "gps_pnt", "metric": "l1_position_error_m",
                 "value": sum(floor["gps_error"])/2,
                 "ci_low": floor["gps_error"][0], "ci_high": floor["gps_error"][1],
                 "ci_level": 0.95, "qualifier": "worsening above 60N"},
                {"domain": "hf_radio", "metric": "blackout_probability",
                 "band_mhz": 8.0, "route": "north_atlantic",
                 "value": floor["hf_blackout"],
                 "ci_low": floor["hf_blackout"]-0.1,
                 "ci_high": min(floor["hf_blackout"]+0.1, 1.0), "ci_level": 0.95},
            ]
        }

    # Load frozen quantile models
    gps_low    = joblib.load("ml/checkpoints/impact-v0.3-frozen/gps_q025.pkl")
    gps_med    = joblib.load("ml/checkpoints/impact-v0.3-frozen/gps_q500.pkl")
    gps_high   = joblib.load("ml/checkpoints/impact-v0.3-frozen/gps_q975.pkl")
    hf_low     = joblib.load("ml/checkpoints/impact-v0.3-frozen/hf_q025.pkl")
    hf_med     = joblib.load("ml/checkpoints/impact-v0.3-frozen/hf_q500.pkl")
    hf_high    = joblib.load("ml/checkpoints/impact-v0.3-frozen/hf_q975.pkl")

    return {
        "storm_id": storm["storm_id"],
        "model_version": "impact-v0.3-frozen",
        "low_confidence": False,
        "source": "model",
        "impacts": [
            {"domain": "gps_pnt", "metric": "l1_position_error_m",
             "value": round(gps_med.predict(X)[0], 1),
             "ci_low": round(gps_low.predict(X)[0], 1),
             "ci_high": round(gps_high.predict(X)[0], 1), "ci_level": 0.95,
             "qualifier": "worsening above 60N"},
            {"domain": "hf_radio", "metric": "blackout_probability",
             "band_mhz": 8.0, "route": "north_atlantic",
             "value": round(float(hf_med.predict(X)[0]), 3),
             "ci_low": round(float(hf_low.predict(X)[0]), 3),
             "ci_high": round(min(float(hf_high.predict(X)[0]), 1.0), 3),
             "ci_level": 0.95},
            {"domain": "grid_gic", "metric": "gic_risk_index",
             "zone": "southern_sweden" if geomag_lat > 55 else "central_europe",
             "value": SEVERITY_FLOOR[g]["gic"],
             "scale_max": 10, "source": "rule_based"},   # model head not trained yet
        ]
    }
```

---

### Layer ③ — Verified Advisory (Priyanshu)

**LangGraph state:**
```python
from typing import TypedDict, Annotated
import operator

class HelioOpsState(TypedDict):
    storm_event:       dict
    impact_assessment: dict
    affected_industries: list[str]
    advisories:        Annotated[dict, operator.or_]   # merged from parallel agents
    formatted_packet:  dict | None
    provenance_trace:  dict | None

def build_graph():
    from langgraph.graph import StateGraph, END
    g = StateGraph(HelioOpsState)
    g.add_node("impact_router",      impact_router)
    g.add_node("aviation_agent",     aviation_agent)
    g.add_node("grid_agent",         grid_agent)
    g.add_node("advisory_formatter", advisory_formatter)
    g.add_node("verifier",           verifier_gate)
    g.set_entry_point("impact_router")
    # Parallel fan-out
    g.add_edge("impact_router", "aviation_agent")
    g.add_edge("impact_router", "grid_agent")
    # Merge
    g.add_edge("aviation_agent", "advisory_formatter")
    g.add_edge("grid_agent",     "advisory_formatter")
    g.add_edge("advisory_formatter", "verifier")
    g.add_edge("verifier", END)
    return g.compile(checkpointer=RedisCheckpointer())
```

**Aviation agent query + prompt:**
```python
from embeddings.retrieval import query_kb, format_context
from embeddings.embedder import embed_query  # always use this, never query_texts

def aviation_agent(state: HelioOpsState) -> HelioOpsState:
    storm = state["storm_event"]
    impact = state["impact_assessment"]
    g = storm["scales"]["G"]

    # Pull relevant procedure chunks
    # NOTE: query phrasing must match actual text in aviation_kb
    # "HF frequency polar route" → category=hf_procedure, storm_scale=G3-G5
    results = query_kb(
        "aviation_kb",
        f"G{g} storm HF frequency blackout polar route reroute latitude threshold",
        n_results=5, use_mmr=True
    )
    context = format_context(results)

    # Get impact numbers from Neal's model
    gps_impact = next((i for i in impact["impacts"] if i["domain"]=="gps_pnt"), None)
    hf_impact  = next((i for i in impact["impacts"] if i["domain"]=="hf_radio"), None)

    prompt = f"""You are an aviation operations advisor. A G{g} geomagnetic storm is in progress.

IMPACT INTELLIGENCE:
- GPS L1 error: {gps_impact['value']} m (95% CI: {gps_impact['ci_low']}–{gps_impact['ci_high']} m), {gps_impact['qualifier']}
- HF {hf_impact['band_mhz']} MHz blackout probability: {hf_impact['value']:.0%} (95% CI: {hf_impact['ci_low']:.0%}–{hf_impact['ci_high']:.0%})
- Timing: storm onset {storm['timeline'][-1]['t']}

OFFICIAL PROCEDURES (retrieved from ICAO NAT Doc 007):
{context}

Write a structured advisory with:
1. severity (critical/high/medium/low)
2. numbered_actions (list of specific operational instructions, each with a verifiable number)
3. timing_window (opens, duration_min)
4. technical_details (one technical sentence)
5. cited_procedure (source and ref from the context above)

Use only frequencies and thresholds from the retrieved procedures."""

    # Call Groq Llama 3.3 70B
    from groq import Groq
    client = Groq()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1000,
    )
    # Parse structured output + run verifier
    draft = parse_advisory_json(response.choices[0].message.content)
    return {**state, "advisories": {"aviation": draft}}
```

**Verifier:**
```python
ICAO_NAT_HF_BANDS_MHZ = {3, 5, 8, 11, 17}
# G3+: reroute below 78°N. G4+: reroute below 70°N.
REROUTE_LAT_THRESHOLDS = {3: 78, 4: 70, 5: 60}

def verifier_gate(state: HelioOpsState) -> HelioOpsState:
    g = state["storm_event"]["scales"]["G"]
    checks = []

    for industry, draft in state["advisories"].items():
        for action in draft.get("numbered_actions", []):
            # Check HF frequencies
            import re
            freq_matches = re.findall(r"(\d+)\s*MHz", action)
            for freq_str in freq_matches:
                freq = int(freq_str)
                if freq in ICAO_NAT_HF_BANDS_MHZ:
                    checks.append({"field": "hf_band", "proposed": freq,
                                   "status": "pass"})
                else:
                    nearest = min(ICAO_NAT_HF_BANDS_MHZ, key=lambda b: abs(b-freq))
                    checks.append({
                        "field": "hf_band", "proposed": freq, "status": "blocked",
                        "corrected_to": nearest,
                        "reason": f"{freq} MHz not in ICAO NAT valid set {sorted(ICAO_NAT_HF_BANDS_MHZ)}"
                    })
                    # Correct in the action text
                    action = action.replace(f"{freq} MHz", f"{nearest} MHz")

    # Assemble VerifiedAdvisory
    # ... (attach checks, provenance, etc.)
    return state
```

---

### Layer ④ — Delivery + Console (Tirth)

**FastAPI + WebSocket:**
```python
from fastapi import FastAPI, WebSocket
import redis.asyncio as aioredis

app = FastAPI()
redis_client = aioredis.from_url("redis://localhost:6379")

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket, storm_id: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"storm:{storm_id}")
    async for message in pubsub.listen():
        if message["type"] == "message":
            await websocket.send_text(message["data"].decode())

@app.post("/replay/{storm_id}/start")
async def start_replay(storm_id: str):
    # Orchestrate: detect() → assess() → advise() → dispatch()
    # Each step publishes WsEvents to storm:{storm_id}
    import asyncio
    asyncio.create_task(run_replay(storm_id))
    return {"status": "started"}
```

**Flywheel export (JSONL for LoRA fine-tuning):**
```python
import json
from datetime import date

def export_flywheel(output_path: str = None):
    """
    Export feedback_log rows as Llama 3 instruction-tuning pairs.
    Only approved + edited records with confidence >= 0.7.
    Tag embedding_model for reproducibility in Phase 3 fine-tuning.
    """
    if output_path is None:
        output_path = f"data/exports/heliops_finetune_{date.today()}.jsonl"

    # Query: feedback_log JOIN advisories JOIN storm_events
    # WHERE operator_action IN ('approved', 'edited') AND confidence >= 0.7
    rows = db_query("""
        SELECT f.*, a.advisory_json, a.confidence, s.storm_event_json
        FROM feedback_log f
        JOIN advisories a ON f.advisory_id = a.id
        JOIN storm_events s ON a.storm_event_id = s.id
        WHERE f.operator_action IN ('approved', 'edited')
          AND a.confidence >= 0.7
        ORDER BY f.logged_at
    """)

    with open(output_path, "w") as out:
        for row in rows:
            advisory = row["advisory_json"]
            # For edited records, the operator's correction is ground truth
            if row["operator_action"] == "edited":
                edited = row["edited_fields"] or {}
                for field, delta in edited.items():
                    advisory[field] = delta["after"]

            record = {
                "instruction": (
                    f"Storm: G{row['storm_event_json']['scales']['G']}, "
                    f"Kp={row['storm_event_json']['l1_solar_wind'].get('kp', 'N/A')}, "
                    f"industry: {advisory['industry']}. "
                    f"Generate a verified operational advisory."
                ),
                "input": "",
                "output": json.dumps({
                    "severity": advisory["severity"],
                    "numbered_actions": advisory["numbered_actions"],
                    "timing_window": advisory["timing_window"],
                }),
                "metadata": {
                    "advisory_id": str(row["advisory_id"]),
                    "industry": advisory["industry"],
                    "operator_action": row["operator_action"],
                    "confidence": float(row["confidence"]),
                    "embedding_model": "BAAI/bge-small-en-v1.5",   # tag for reproducibility
                    "logged_at": str(row["logged_at"]),
                }
            }
            out.write(json.dumps(record) + "\n")

    print(f"Exported to {output_path}")
```

---

## 11. 25-Commit Build Roadmap

### Phase P1 — Spine (get a storm on screen)
**Goal:** Hardcoded StormEvent renders storm banner + timeline on console. Contracts frozen. Everyone can build against stubs.

| # | Commit | Owner | DoD |
|---|---|---|---|
| 01 | `chore: scaffold repo + Docker Compose (FastAPI Postgres Redis Chroma Next.js)` | Tirth | `docker-compose up` brings everything up |
| 02 | `feat(ws): WebSocket + Redis pub/sub + replay engine with hardcoded StormEvent` | Tirth | Console receives WsEvents from hardcoded Oct 2024 G4 storm |
| 03 | `feat(ui): storm banner + multi-horizon timeline rendering off WsEvent stream` | Tirth | Banner shows G4, timeline shows 3 markers |
| 04 | `feat(chroma): init persistent chromadb + 5 collection scaffold` | Priyanshu | `python -m embeddings.collections` prints 5 collections |
| 05 | `feat(ingest): pdf loader + 512/64 chunker + BAAI/bge-small embedder + redis cache` | Priyanshu | All 3 chunker bugs fixed, 511 total chunks, 191× cache speedup |
| 06 | `feat(kb): ingest aviation(242) + grid(101) + maritime(pdfplumber) + impact_matrix(166)` | Priyanshu | All 4 KBs populated and queryable with embed_query() |
| 07 | `feat(retrieval): query_kb + MMR(λ=0.7) + format_context + query_all_kbs` | Priyanshu | MMR returns ≥2 distinct categories on aviation G4 query |
| 08 | `test(kb): G4 fixture + zone-A where filter + maritime edge case + embedding consistency` | Priyanshu | All tests green (telecom xfail expected) |
| 09 | `feat(data): cache CCOR-1 oct2024 + LASCO may2024 + SUVI/XRS + L1 + NOAA archive` | Neal | ≥50 CCOR-1 frames in data/cached/ccor1/2024-10/ |
| 10 | `feat(contracts): stub StormEvent + ImpactAssessment + VerifiedAdvisory (all match §7)` | Neal + Priyanshu | `detect("2024-10-G4")` and `assess(stub)` return valid contract objects |
| 11 | `feat(db): alembic init + all 5 table migrations with indexes + CHECK constraint` | Tirth | `alembic upgrade head`, CHECK blocks edited+null fields |

### Phase P2 — Signals (real detection + real numbers)
**Goal:** Neal's CV detects CME on real imagery. Impact model produces quantified CIs. Both panels render.

| # | Commit | Owner | DoD |
|---|---|---|---|
| 12 | `feat(cv): CCOR-1 pre-processing — FITS load + denoise + running-difference` | Neal | Difference images show CME arc for Oct 2024 sequence |
| 13 | `feat(cv): CME detection CNN + bounding region + kinematics (speed, width, ETA)` | Neal | `speed_km_s` in 500–3000 range for Oct 2024 storm |
| 14 | `feat(cv): flare detection + R-scale on SUVI/XRS` | Neal | R-scale matches NOAA event report for Oct 2024 |
| 15 | `feat(cv): fusion → real StormEvent with calibrated confidence + 3-point timeline` | Neal | `detect("2024-10-G4")` byte-identical across 3 runs |
| 16 | `feat(ui): detection panel — imagery + CME bounding box overlay + kinematics readout` | Tirth | 
 #1 visible on console with real CV output |
| 17 | `feat(ml): LightGBM quantile regression — GPS error + HF blackout (q025/q500/q975)` | Neal | May 2024 GPS median > 15 m (documented 15–40 m) |
| 18 | `feat(ml): severity floor + OOD detection + low_confidence flag → ImpactAssessment` | Neal | OOD input (wind > 2500 km/s) → `low_confidence=True` |
| 19 | `feat(ui): impact panel — metric rows + CI bars + low-confidence badge` | Tirth | GPS error metres + HF % with CI bars visible |
| 20 | `feat(agents): LangGraph aviation + grid agents with real StormEvent + ImpactAssessment` | Priyanshu | Structured (unverified) advisory produced for Oct 2024 |

### Phase P3 — Verified Brain (trust made structural)
**Goal:** Verifier gate fires, 21 MHz blocked, provenance works.

| # | Commit | Owner | DoD |
|---|---|---|---|
| 21 | `feat(verifier): deterministic gate + 21MHz block + VerifiedAdvisory + ProvenanceTrace` | Priyanshu | 21 MHz → blocked → corrected to 5 MHz → logged → visible on console |
| 22 | `feat(ui): verifier panel (blocked row red glow + shake) + advisory cards + provenance drawer` | Tirth | WOW #2 fires visibly. Provenance opens 6-step chain. |
| 23 | `feat(demo): freeze checkpoint + byte-deterministic inference + May2024 anchor validation` | Neal | 3 consecutive runs: identical StormEvent + ImpactAssessment. May 2024 validated. |

### Phase P4 — Theater (unbreakable + unforgettable)
**Goal:** Full demo locked. Both WOWs on cue. Backup video exists.

| # | Commit | Owner | DoD |
|---|---|---|---|
| 24 | `feat(delivery): CRM ticket + Slack Block Kit + email + audit trail + Railway deploy` | Tirth | End-to-end replay in < 4 min, CRM ticket created, zero failures |
| 25 | `chore(demo): lock two-storm replay + rehearse pitch + record backup video` | All | Backup video recorded. Pitch rehearsed cold twice. |

### Phase P5 — Stretch (only if P4 DoD is fully green)

- Priyanshu: Telecom + Maritime agents
- Neal: Live CCOR-1 ingestion with auto-fallback to cache; GIC + GMDSS model heads
- Tirth: Real CRM integration; operator approve/edit/reject UI

**All P5 items are flag-off by default. None of them destabilize the P4 demo.**

---

## 12. Team Roles & RACI

### Developer slices

**Tirth — Full-stack + DevOps ("the spine")**  
Owns everything the user sees and everything that runs. Critical-path root — his P1 spine unblocks Neal and Priyanshu.
- Backend: FastAPI async + WebSocket + Redis pub/sub
- Replay/orchestration engine (calls Neal's detect() and assess(), Priyanshu's advise())
- Database: PostgreSQL 15 JSONB advisories + append-only audit + provenance
- Console: Next.js 14 + Tailwind + Recharts — all surfaces in F5
- Delivery: CRM ticket, Slack Block Kit, email, audit trail
- Infra: Docker, Railway, env/secrets, backup video

**Neal — Computer Vision + ML ("the signals")**  
Owns the intelligence stack no one else can build.
- Layer ①: CME detection on CCOR-1/LASCO, kinematics, flare/R-scale, fusion → `StormEvent`
- Layer ②: LightGBM quantile regression impact model → `ImpactAssessment`
- Data caching: CCOR-1 S3, SOHO/LASCO, SUVI/XRS, L1, NOAA archive
- Embeddings infrastructure (built — Priyanshu operates going forward)

**Priyanshu — RAG + Agentic ("the brain")**  
Owns the advisory layer.
- ChromaDB KBs (5 collections, BAAI/bge-small-en-v1.5): aviation, grid, maritime, impact_matrix, telecom
- LangGraph agents: Aviation + Grid at MVP
- Deterministic verifier: ICAO HF bands, rerouting thresholds, NERC GIC steps, GMDSS channels
- Provenance trace assembly
- Groq integration (Llama 3.3 70B, temp=0.1)

### RACI

| Workstream | Tirth | Neal | Priyanshu |
|---|---|---|---|
| Backend + WebSocket + replay engine | **R/A** | C | C |
| Console UI (all surfaces) | **R/A** | I | I |
| DB schema + audit trail | **R/A** | C | C |
| Layer ① CV → `StormEvent` | C | **R/A** | I |
| Layer ② ML → `ImpactAssessment` | C | **R/A** | C |
| ChromaDB KBs (5 collections) | I | R (built) | **A** (ongoing) |
| LangGraph agents + verifier | I | C | **R/A** |
| Provenance trace | C (stores/renders) | I | **R/A** |
| Delivery (CRM/Slack/email) | **R/A** | I | C |
| §7 data contracts | **A** | R (Storm/Impact) | R (Advisory/Provenance) |
| WOW #1 (CME at the Sun) | R (renders) | **R (builds)** | I |
| WOW #2 (21 MHz blocked) | R (renders) | I | **R (builds)** |
| Demo script + backup video | **R/A** | C | C |

### Critical path

```
P1 Tirth spine ──┬──► P2 Neal detect() + assess() ──────────────────────────┐
(critical root)  │                                                           ├──► P3 Priyanshu advise+verify ──► P4 lock
                 ├──► P1 Neal data cache (parallel, start day 1)            │
                 └──► P1 Priyanshu KB ingestion + stubs (parallel)  ────────┘
```

Neal and Priyanshu build against P1 stubs — they never wait for each other's real implementation. Integration is continuous from day 1.

---

## 13. Demo Plan

### Two anchor storms

| Storm | Date | Peak | Why |
|---|---|---|---|
| May 2024 G5 — "Gannon storm" | 10–11 May 2024 | Kp=9, G5 | Strongest since 2003. Documented: 500+ polar diversions, GPS 15–40 m error on L1, HF blackout 8 hrs (N.Atlantic), GIC warnings in Canada/UK/Scandinavia, auroras to 17°N India. Judges verify on Wikipedia. |
| October 2024 G4 | ~10 Oct 2024 | Kp=8.3, G4 | First major storm with CCOR-1 coronagraph available. WOW #1: CME visible at the Sun on CCOR-1 FITS sequence before it left. |

### WOW #1 — "Detected at the Sun" (Neal + Tirth)

1. Replay Oct 2024 storm. CCOR-1 imagery streams into Detection panel.
2. CV model draws bounding box around CME. Kinematics populate: `1480 km/s`, `110°`, arrival `+21 hours`.
3. Timeline: days-out marker fills. Flare flagged on SUVI/XRS (R3).
4. L1 reading arrives → 1-hour marker fills → confidence finalizes to 0.91.
5. **The quote**: *"That storm left the Sun 21 hours ago. NOAA wouldn't confirm it for another 6. We saw it at the source."*

### WOW #2 — "No hallucinated frequency ships" (Priyanshu + Tirth)

1. Impact panel shows: GPS error 25 m (CI: 18–32 m), HF blackout 86% on 8 MHz.
2. Aviation agent starts drafting — reasoning streams token by token.
3. Agent writes `"switch HF to 21 MHz"`.
4. Verifier fires. Console shows red row: *"hf_band: proposed=21 MHz, status=BLOCKED, corrected_to=5 MHz — not in ICAO NAT valid set {3, 5, 8, 11, 17}"*.
5. Corrected advisory dispatched. CRM ticket created.
6. **The quote**: *"LLM proposal blocked by verifier. No hallucinated frequency reached the dispatcher. Every number that ships exists in the official rulebook."*

### 90-second pitch script

> *(console open, calm state, no storm)*  
> "This is HelioOps. Solar storms damage GPS, black out radio communications, and risk $100 billion in grid infrastructure. Every operator gets the same generic NOAA alert. Nobody gets specific instructions."

> *(select Oct 2024, press play — WOW #1 fires)*  
> "This storm happened last October. Our coronagraph AI spotted the CME leaving the Sun — 21 hours before NOAA issued a bulletin. Speed: 1480 km/s. Arrival: +21 hours. Days of warning, not minutes."

> *(impact panel fills)*  
> "The impact model outputs real numbers. GPS off by 25 metres above 60 North. 86% chance of HF blackout on the 8 MHz North Atlantic frequency. Confidence intervals. Not a severity tier."

> *(agent reasoning streams — WOW #2 fires)*  
> "Our advisory agent drafts the work order from official ICAO and NERC procedures. Watch: it writes '21 MHz' — the verifier fires — blocked. 21 MHz is not in the ICAO valid set. Corrected to 5 MHz. Nothing fake ships."

> *(CRM ticket appears)*  
> "Three minutes after detection: a verified, rulebook-checked work order in the dispatcher's system. Manual analysts take 2–4 hours — when they exist at all."

> "Detected at the Sun. Quantified. Verified. This is SWxOps."

### Demo rules

1. **Everything runs on cached data.** Zero live API calls during judging. Live is a bonus toggle with auto-fallback to cache.
2. **Both WOWs fire on cue every run.** Rehearse cold twice before the event.
3. **Backup video of the full run exists** and can launch in 30 seconds if anything fails on stage.
4. **Byte-deterministic.** Same storm ID → identical outputs across 100 runs. No random seeds in inference.
5. **Zero network dependency.** Disconnect WiFi before rehearsal. If it fails: fix it before the demo.

---

## 14. Risk Register

| Risk | Prob | Impact | Owner | Mitigation |
|---|---|---|---|---|
| CV doesn't detect reliably on real CCOR-1 imagery | Medium | High | Neal | Cached-only for two storms. Hand-curate frames that clearly show the CME. Confidence can be low (0.5) without blocking downstream. |
| Verifier rulebook incomplete at P3 | Medium | High | Priyanshu | Draft all tables (ICAO HF bands, rerouting thresholds, NERC steps) in P1. Un-checkable values fail-safe to `requires_human=True` — never auto-dispatch. |
| Integration big-bang at the end | Medium | High | All | Frozen contracts + stubs from P1. Tirth renders stubs by P1 end. Daily 10-min sync on contract status. |
| CCOR-1 imagery takes too long to download | Medium | High | Neal | Start `aws s3 sync` on day 1 — this is Commit 09. FITS files are ~50 MB each. Pre-convert to PNG for CV speed. |
| Zone-A retrieval mismatch | Low | Medium | Priyanshu | Already identified: NERC text says "geomagnetic latitude of 60°" not "Zone A". Use `where={"latitude_zone": "A"}` filter. Test confirmed via `collection.get(where={"latitude_zone": "A"})` returns all 9 chunks. |
| maritme_kb only 2 chunks | Low | Medium | Priyanshu | Commit 07 includes pdfplumber reingestion + `collection.delete(where={"source": "imo_gmdss_2019.pdf"})` before upsert. Target: >10 meaningful chunks. |
| Impact model overconfident / OOD storm | Medium | Medium | Neal | Calibrated quantile CIs + conservative severity floor + `low_confidence` flag. Z-score OOD detection on wind speed. May 2024 anchor validates directional accuracy. |
| Demo depends on live API on stage | Low | Critical | Tirth | Cached-only demo path. `DEMO_MODE=true` env var disables all live API calls. Backup video as ultimate fallback. |
| WebSocket drops mid-demo | Low | High | Tirth | Auto-reconnect on client. Replay state is server-authoritative — client re-syncs on reconnect. |
| Scope creep (P5 leaking into P4) | Medium | Medium | All | P5 is gated on a fully-green P4 DoD. All P5 items are `--flag-off` by default. No P5 commit merged if any P4 DoD item is red. |

---

*End of document. The only thing left to do is build it.*