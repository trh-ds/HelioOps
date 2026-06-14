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
│  ML_after_CV/         │  → GPS error 12.8m [6.6–13.3], HF blackout 90% [66–93%]
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
└──────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements-backend.txt
pip install -r requirements-genai.txt
pip install -r requirements-data.txt

# 2. Set Groq API key (get free key at https://console.groq.com/keys)
echo "GROQ_API_KEY=gsk_your_key" > .env

# 3. Start backend
python -m backend.run

# 4. Open Swagger docs
# http://localhost:8000/docs

# 5. Run pipeline
curl -X POST http://localhost:8000/api/detect/2024-10-G4
```

## Project Structure

```
HelioOps/
├── cv/                         # Layer 1: Heliospheric Detection
│   ├── detect.py               # Main entry — deterministic replay
│   ├── preprocessing.py        # FITS → running-difference images
│   ├── threshold_detector.py   # 9-step deterministic CME detector
│   ├── cache_fits.py           # CCOR-1 S3 + SOHO LASCO cache
│   ├── fusion.py               # StormEvent contract + fuse()
│   ├── donki_client.py         # NASA DONKI CME physics API
│   ├── flare_classifier.py     # GOES XRS → R-scale classification
│   └── l1_client.py            # DSCOVR L1 solar wind + ETA
│
├── ML_after_CV/                # Layer 2: Impact Intelligence
│   ├── inference.py            # LightGBM inference with 95% CIs
│   ├── 01_data_generation_eda.py
│   ├── 02_train_and_tune.py    # Quantile regression training
│   ├── 03_anchor_test.py       # G5 black-swan validation
│   └── checkpoints/            # 6 trained models (gps + hf × 3 quantiles)
│
├── genai/                      # Layer 3: Verified Advisory
│   ├── orchestrator.py         # AgentScope parallel fan-out
│   ├── impact_router.py        # Deterministic G-scale → severity matrix
│   ├── retriever.py            # ChromaDB RAG with MMR reranking
│   ├── verifier.py             # Zero-LLM rule engine
│   ├── guardrails.py           # Schema validation + hallucination detection
│   ├── contracts.py            # VerifiedAdvisory + ProvenanceTrace
│   ├── models.py               # Pydantic schemas
│   ├── config.py               # All config knobs
│   ├── agents/                 # Per-industry agents (aviation, grid, maritime, telecom)
│   └── prompts/                # Industry-specific system prompts
│
├── embeddings/                 # RAG Infrastructure
│   ├── embedder.py             # BGE-small-en-v1.5 + Redis cache
│   ├── retrieval.py            # Query + MMR reranking
│   ├── ingest_aviation.py      # NAT Doc 007 → ChromaDB
│   ├── ingest_grid.py          # NERC TPL-007-4 → ChromaDB
│   ├── ingest_maritime.py      # IMO GMDSS 2019 → ChromaDB
│   └── ingest_impact_matrix.py # NOAA/NESDIS → ChromaDB
│
├── backend/                    # Layer 4: FastAPI Server
│   ├── app.py                  # REST + WebSocket + health + metrics
│   ├── pipeline.py             # run_full_pipeline() — chains all layers
│   ├── adapter.py              # cv.StormEvent → genai.StormEvent bridge
│   ├── config.py               # Pydantic Settings (env vars + .env)
│   ├── logging.py              # Structured logging (structlog)
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
│   │   ├── repository_adapter.py
│   │   └── schema_adapter.py   # Anti-corruption layer
│   ├── run.py                  # uvicorn entry point
│   └── README.md               # Backend API documentation
│
├── frontend/                   # Next.js 14 Dashboard
│   └── src/                    # React components + Tailwind
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
│   └── test_pipeline.py        # Backend pipeline tests (13)
│
├── .github/
│   └── workflows/
│       └── ci.yml              # Lint + test + build (backend + frontend)
├── k8s/                        # Kubernetes manifests
│   ├── base/                   # Deployment, Service, ConfigMap, Ingress, ServiceMonitor
│   ├── staging/                # Staging overlay (debug-friendly)
│   └── production/             # Production overlay (hardened, 3 replicas)
├── infra/                      # Terraform IaC
│   ├── modules/                # Reusable VPC + EKS modules
│   └── environments/           # Staging + production tfvars
├── argocd/                     # ArgoCD application manifests
├── chaos/                      # Chaos Mesh experiments
├── runbooks/                   # Operational playbooks
├── .env.example                # Environment variable template
├── Dockerfile.backend          # Multi-stage Python backend image
├── Dockerfile.frontend         # Multi-stage Next.js frontend image
├── docker-compose.yml          # Local dev: backend + frontend
├── .env                        # GROQ_API_KEY (not committed)
├── requirements-backend.txt    # fastapi, uvicorn, structlog, pydantic-settings
├── requirements-genai.txt      # agentscope, langchain, groq
├── requirements-data.txt       # chromadb, sentence-transformers
└── .gitignore
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/detect/{storm_id}` | Run full 5-step pipeline |
| GET | `/api/storms` | List available + completed storms |
| GET | `/api/advisory/{advisory_id}` | Verified advisory + provenance trace |
| GET | `/api/result/{storm_id}` | Full pipeline result |
| WS | `/ws/stream` | Real-time pipeline event streaming |
| GET | `/health` | Health check |
| GET | `/health/ready` | Readiness (checks all dep layers) |
| GET | `/health/live` | Liveness (process check) |
| GET | `/metrics` | Prometheus-compatible metrics |

## Infrastructure

### Docker

```bash
# Build and run all services
docker compose up --build

# Backend only
docker build -f Dockerfile.backend -t helioops-backend .

# Frontend only
docker build -f Dockerfile.frontend -t helioops-frontend .
```

### Kubernetes

```bash
# Apply base manifests
kubectl apply -f k8s/base/

# Staging overlay
kubectl apply -k k8s/staging/

# Production overlay
kubectl apply -k k8s/production/
```

### Terraform (AWS EKS)

```bash
# Stage: plan + apply
cd infra/environments/staging
terraform init
terraform plan
terraform apply

# Production: plan + apply
cd infra/environments/production
terraform init
terraform plan
terraform apply
```

### ArgoCD GitOps

```bash
kubectl apply -f argocd/backend-staging.yaml
kubectl apply -f argocd/backend-production.yaml
```

### Monitoring

- **Metrics**: `GET /metrics` — Prometheus-compatible counters and gauges
- **Health**: `GET /health/ready` — readiness with dependency checks
- **Runbooks**: `runbooks/` — operational playbooks for alerts
- **Chaos**: `chaos/` — Chaos Mesh experiments for staging

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLM generation |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model ID |
| `GROQ_MAX_TOKENS` | No | `2048` | Max generation tokens |
| `HELIOOPS_HOST` | No | `0.0.0.0` | Server bind address |
| `HELIOOPS_PORT` | No | `8000` | Server port |
| `HELIOOPS_LOG_LEVEL` | No | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `HELIOOPS_LOG_FORMAT` | No | `json` | Log format (json/console) |
| `HELIOOPS_WORKERS` | No | `1` | Uvicorn worker count |
| `HELIOOPS_RELOAD` | No | `true` | Hot reload (dev only) |
| `HELIOOPS_CHROMA_PERSIST_PATH` | No | `data/chroma_db` | ChromaDB path |
| `HELIOOPS_ML_CHECKPOINT_DIR` | No | `ML_after_CV/checkpoints` | Model checkpoints path |

## Demo Storms

| Storm | Date | G-Scale | CME Speed | GPS Error | HF Blackout |
|-------|------|---------|-----------|-----------|-------------|
| 2024-10-G4 | Oct 2024 | G4 (Kp=8.3) | 1480 km/s | 12.8m | 90% |
| 2024-05-G5 | May 2024 | G5 (Kp=9.0) | 1800 km/s | 20.8m | 92% |

## Key Design Decisions

1. **Deterministic detector (Option C)** — Threshold algorithm on running-difference frames instead of CNN. Byte-identical output, no labeled data needed.
2. **DONKI for physics** — CME speed/width from NASA's human-reviewed database. More defensible than learned regression.
3. **AgentScope over LangGraph** — Transparent message protocol, parallel asyncio.gather, registry-based dispatch.
4. **10-layer anti-hallucination** — RAG grounding, citation enforcement, severity consistency, LLM self-check, deterministic verifier.
5. **Bridge, don't rewrite** — Backend bridges existing layers without modifying CV, GenAI, or embeddings code.

## Testing

```bash
# All tests (64 total)
python -m pytest tests/test_option_c.py tests/test_pipeline.py -v

# CV + detection only (51 tests)
python -m pytest tests/test_option_c.py -v

# Backend pipeline only (13 tests)
python -m pytest tests/test_pipeline.py -v
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLM generation |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model ID |
| `GROQ_TEMPERATURE` | No | `0.1` | Near-deterministic generation |

## Team

- **Neal** — CV Detection (Layer 1) + ML Impact Models (Layer 2)
- **Priyanshu** — GenAI Advisory (Layer 3) + Backend Pipeline
- **Tirth** — Frontend Dashboard (Layer 4) + Deployment
