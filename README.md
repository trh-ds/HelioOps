# HelioOps

Real-time space weather operations platform that detects solar storms and generates regulatory-compliant advisories for aviation, power grids, maritime, and telecom industries.

## How It Works

```
Solar Imagery (FITS)
    │
    ▼
┌──────────────────────┐
│  Layer 1: CV Detection│  Threshold CME detector + NASA DONKI physics
│  cv/detect.py         │  → StormEvent (confidence, G/S/R scales, CME kinematics)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Layer 2: ML Impact   │  LightGBM quantile regression (6 models)
│  ML_after_CV/         │  → GPS error ± 95% CI, HF blackout probability ± 95% CI
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Layer 3: GenAI       │  4 parallel agents (Groq Llama 3.3 70B + ChromaDB RAG)
│  genai/               │  → Industry-specific advisories with 10 anti-hallucination layers
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Deterministic        │  Zero-LLM rule engine checks HF frequencies, reroute
│  Verifier             │  latitudes, GIC procedures, GMDSS channels
│  genai/verifier.py    │  → VerifiedAdvisory + ProvenanceTrace (6-step audit)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Layer 4: Delivery    │  FastAPI REST + WebSocket, Next.js dashboard
│  backend/ + frontend/ │  → Real-time streaming to operators
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Supabase PostgreSQL  │  Persistent storage for storms, advisories,
│  supabase/            │  provenance traces, pipeline runs
└──────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements-backend.txt
pip install -r requirements-genai.txt
pip install -r requirements-data.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set GROQ_API_KEY (get free key at https://console.groq.com/keys)

# 3. Start backend
python -m backend.run

# 4. Open Swagger docs
# http://localhost:8000/docs

# 5. Run pipeline for a demo storm
curl -X POST http://localhost:8000/api/detect/2024-10-G4
```

### Docker (recommended)

```bash
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Project Structure

```
HelioOps/
├── cv/                         # Layer 1: Heliospheric Detection
│   ├── detect.py               # Main entry — deterministic replay + live mode
│   ├── preprocessing.py        # FITS → running-difference images
│   ├── threshold_detector.py   # 9-step deterministic CME detector
│   ├── cache_fits.py           # CCOR-1 S3 + SOHO LASCO cache
│   ├── fusion.py               # StormEvent contract + fuse()
│   ├── donki_client.py         # NASA DONKI CME physics API
│   ├── flare_classifier.py     # GOES XRS → R-scale classification
│   ├── l1_client.py            # DSCOVR L1 solar wind + ETA
│   └── README.md
│
├── ML_after_CV/                # Layer 2: Impact Intelligence
│   ├── inference.py            # Production — LightGBM inference with 95% CIs
│   ├── 01_data_generation_eda.py
│   ├── 02_train_and_tune.py    # Quantile regression training
│   ├── 03_anchor_test.py       # G5 black-swan validation
│   ├── checkpoints/            # 6 trained models (gps + hf × 3 quantiles)
│   └── README.md
│
├── genai/                      # Layer 3: Verified Advisory
│   ├── orchestrator.py         # AgentScope parallel fan-out
│   ├── impact_router.py        # Deterministic G-scale → severity matrix
│   ├── retriever.py            # ChromaDB RAG (BGE-small, cosine similarity)
│   ├── verifier.py             # Zero-LLM rule engine (ICAO, NERC, GMDSS)
│   ├── guardrails.py           # Schema validation + hallucination detection
│   ├── contracts.py            # VerifiedAdvisory + ProvenanceTrace
│   ├── models.py               # Pydantic schemas + enums
│   ├── config.py               # All config knobs
│   ├── agents/                 # Per-industry agents (aviation, grid, maritime, telecom)
│   ├── prompts/                # Industry-specific system prompts
│   └── README.md
│
├── embeddings/                 # RAG Infrastructure
│   ├── embedder.py             # BGE-small-en-v1.5 embeddings
│   ├── retrieval.py            # Query + cosine similarity filtering
│   ├── chunker.py              # Token-aware document chunking (512 tok, 64 overlap)
│   ├── ingest_aviation.py      # NAT Doc 007 → ChromaDB
│   ├── ingest_grid.py          # NERC TPL-007-4 → ChromaDB
│   ├── ingest_maritime.py      # IMO GMDSS 2019 → ChromaDB
│   ├── ingest_impact_matrix.py # NOAA/NESDIS → ChromaDB
│   └── README.md
│
├── backend/                    # Layer 4: FastAPI Server
│   ├── app.py                  # REST + WebSocket + health + metrics
│   ├── pipeline.py             # run_full_pipeline() — chains all layers
│   ├── adapter.py              # cv.StormEvent → genai.StormEvent bridge
│   ├── config.py               # Pydantic Settings (env vars + .env)
│   ├── logging.py              # Structured JSON logging (structlog)
│   ├── health.py               # /health, /health/ready, /health/live, /metrics
│   ├── ports/                  # Hexagonal architecture — abstract interfaces
│   │   ├── detection.py        # DetectionPort
│   │   ├── prediction.py       # PredictionPort
│   │   ├── advisory.py         # AdvisoryPort, VerificationPort
│   │   └── repository.py       # ResultRepository
│   ├── adapters/               # Concrete implementations of ports
│   │   ├── detection_adapter.py
│   │   ├── prediction_adapter.py
│   │   ├── advisory_adapter.py
│   │   ├── repository_adapter.py  # In-memory store (default)
│   │   └── schema_adapter.py      # Anti-corruption layer
│   ├── run.py                  # uvicorn entry point
│   └── README.md
│
├── frontend/                   # Next.js 14 Dashboard
│   └── src/                    # React components + Tailwind + Three.js
│
├── supabase/                   # Database Schema (Supabase PostgreSQL)
│   ├── 001_schema.sql          # 4 enums + 8 tables + indexes + triggers
│   ├── 002_rls.sql             # Row Level Security policies
│   └── 003_seed.sql            # Demo storm data (G4 + G5)
│
├── data/
│   ├── chroma_db/              # ChromaDB persistence (5 collections)
│   ├── cached/                 # FITS cache + annotated PNGs
│   ├── aviation/               # NAT Doc 007 PDF
│   ├── grid/                   # NERC TPL-007-4 PDFs
│   ├── maritime/               # IMO GMDSS 2019 PDF
│   └── impact_matrix/          # NOAA space weather scales
│
├── ml/stubs/                   # Pre-computed storm events (G4 + G5)
├── tests/                      # 64 tests (pytest)
│   ├── test_option_c.py        # CV + fusion + detection tests (51)
│   ├── test_pipeline.py        # Backend pipeline tests (13)
│   └── README.md
│
├── docs/
│   ├── archived/               # Legacy design docs
│   └── ml_research/            # EDA plots from ML training
│
├── .github/workflows/ci.yml    # CI: lint + test + build + Docker
├── k8s/                        # Kubernetes manifests (base, staging, production)
├── infra/                      # Terraform IaC (VPC + EKS modules)
├── argocd/                     # ArgoCD GitOps application manifests
├── chaos/                      # Chaos Mesh experiments (staging only)
├── runbooks/                   # Operational playbooks (4 scenarios)
│
├── Dockerfile.backend          # Multi-stage Python 3.12 image
├── Dockerfile.frontend         # Multi-stage Node 20 image
├── docker-compose.yml          # Local dev: backend + frontend
├── .env.example                # Environment variable template
├── requirements-backend.txt    # fastapi, uvicorn, structlog, pydantic-settings
├── requirements-genai.txt      # agentscope, langchain-groq, chromadb
├── requirements-data.txt       # sentence-transformers, tiktoken
└── ARCHITECTURE_CHANGES.md     # DevOps architecture decisions
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/detect/{storm_id}` | Run full 5-step pipeline |
| GET | `/api/storms` | List available + completed storms |
| GET | `/api/advisory/{advisory_id}` | Verified advisory + provenance trace |
| GET | `/api/result/{storm_id}` | Full pipeline result |
| WS | `/ws/stream` | Real-time pipeline event streaming |
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness (checks ML, CV, GenAI layers) |
| GET | `/health/live` | Liveness (process check) |
| GET | `/metrics` | Prometheus-compatible metrics |

## Database (Supabase)

8 PostgreSQL tables with Row Level Security:

| Table | Description |
|-------|-------------|
| `storm_events` | CV detection output (JSONB for CME, flare, L1 wind) |
| `impact_predictions` | ML quantile regression results (GPS + HF with 95% CIs) |
| `advisories` | GenAI advisory output per industry |
| `action_items` | Numbered actions within each advisory |
| `verified_advisories` | Post-verification advisory with rule check results |
| `verifier_checks` | Individual rule check results (pass/blocked) |
| `provenance_traces` | 6-step audit chain per advisory |
| `pipeline_runs` | Denormalized pipeline execution summary |

Setup:
```bash
# Run in Supabase SQL Editor (in order):
supabase/001_schema.sql    # Tables + indexes + triggers
supabase/002_rls.sql       # RLS policies
supabase/003_seed.sql      # Demo data (2 storms)
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Groq API key for LLM generation |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model ID |
| `GROQ_MAX_TOKENS` | No | `2048` | Max generation tokens |
| `GROQ_CHECKER_MODEL` | No | `llama-3.1-8b-instant` | Self-check LLM (lighter = fewer tokens) |
| `MAX_PROMPT_TOKENS` | No | `4000` | Token budget cap for RAG context |
| `HELIOOPS_HOST` | No | `0.0.0.0` | Server bind address |
| `HELIOOPS_PORT` | No | `8000` | Server port |
| `HELIOOPS_LOG_LEVEL` | No | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `HELIOOPS_LOG_FORMAT` | No | `json` | Log format (json/console) |
| `HELIOOPS_WORKERS` | No | `1` | Uvicorn worker count |
| `HELIOOPS_RELOAD` | No | `true` | Hot reload (dev only) |
| `HELIOOPS_CHROMA_PERSIST_PATH` | No | `data/chroma_db` | ChromaDB persistence path |
| `HELIOOPS_ML_CHECKPOINT_DIR` | No | `ML_after_CV/checkpoints` | ML model checkpoints path |

## Demo Storms

| Storm | Date | G-Scale | CME Speed | Bz (nT) | Flare | Industries Triggered |
|-------|------|---------|-----------|---------|-------|---------------------|
| `2024-10-G4` | Oct 2024 | G4 (Kp=8.3) | 1480 km/s | -28 | X1.8 / R3 | aviation, grid, maritime, telecom |
| `2024-05-G5` | May 2024 | G5 (Kp=9.0) | 2200 km/s | -46 | X5.8 / R5 | aviation, grid, maritime, telecom |

## Infrastructure

### Docker
```bash
docker compose up --build              # Full stack
docker build -f Dockerfile.backend .   # Backend only
docker build -f Dockerfile.frontend .  # Frontend only
```

### Kubernetes
```bash
kubectl apply -k k8s/staging/         # Staging overlay
kubectl apply -k k8s/production/      # Production (3 replicas, hardened)
```

### Terraform (AWS EKS)
```bash
cd infra/environments/staging && terraform init && terraform apply
cd infra/environments/production && terraform init && terraform apply
```

### ArgoCD GitOps
```bash
kubectl apply -f argocd/backend-staging.yaml
kubectl apply -f argocd/backend-production.yaml
```

### Monitoring
- **Metrics**: `GET /metrics` — Prometheus counters (request count, latency p99, errors)
- **Health**: `GET /health/ready` — dependency checks (ML models, CV detection, GenAI)
- **Runbooks**: `runbooks/` — playbooks for high-error-rate, high-latency, detection-failure, groq-outage
- **Chaos**: `chaos/` — Chaos Mesh experiments (CPU stress, network delay, pod kill)

## Testing

```bash
# All tests (64 total)
python -m pytest tests/ -v

# CV + detection only (51 tests)
python -m pytest tests/test_option_c.py -v

# Backend pipeline only (13 tests)
python -m pytest tests/test_pipeline.py -v
```

## Key Design Decisions

1. **Deterministic detector (Option C)** — Threshold algorithm on running-difference frames instead of CNN. Byte-identical output, no labeled data needed, no GPU required.
2. **NASA DONKI for physics** — CME speed/width from NASA's human-reviewed database. More defensible than learned regression.
3. **AgentScope over LangGraph** — Transparent message protocol, parallel asyncio.gather fan-out, registry-based agent dispatch.
4. **10-layer anti-hallucination** — RAG grounding, citation enforcement, severity consistency, LLM self-check, deterministic verifier, confidence scoring, safety flags.
5. **Token-budgeted prompts** — RAG context capped at 4000 tokens, self-check uses lighter 8B model to stay within Groq rate limits.
6. **Bridge, don't rewrite** — Backend bridges existing layers via schema adapter without modifying CV, GenAI, or embeddings code.
7. **Hexagonal architecture** — Ports and adapters pattern for testability; swap in-memory store for Supabase without touching pipeline code.

## Team

- **Parshva** - Data Engineer + ML Impact Models (Layer 2)
- **Neal** - CV Detection (Layer 1) + ML Pipeline
- **Priyanshu** - GenAI Advisory (Layer 3) + Backend Pipeline + Database
- **Tirth** - Frontend Dashboard (Layer 4) + DevOps + Deployment
