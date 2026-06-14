# HelioOps

Real-time space weather platform that detects geomagnetic storms from solar imagery and generates regulatory-compliant operational advisories for aviation, power grids, maritime, and telecom industries.

## Pipeline

```
Solar Imagery (FITS/PNG)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Layer 1 · cv/detect.py                             │
│  Deterministic CME detection on running-difference  │
│  frames + NASA DONKI physics + GOES XRS flare +     │
│  DSCOVR L1 solar wind → StormEvent                  │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2 · ML_after_CV/inference.py                 │
│  6 LightGBM quantile models (q0.025/q0.5/q0.975)   │
│  → GPS L1 error ± 95% CI, HF blackout prob ± 95% CI │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│  Layer 3 · genai/                                   │
│  Deterministic G-scale routing → 4 parallel         │
│  industry agents (AgentScope + Groq Llama 3.3 70B   │
│  + ChromaDB RAG) → 10-layer anti-hallucination →    │
│  deterministic verifier (zero LLM) → VerifiedAdvisory│
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│  Layer 4 · backend/ + frontend/                     │
│  FastAPI REST + WebSocket, Next.js 14 dashboard     │
│  Optional: Supabase PostgreSQL persistence          │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### Python (dev)

```bash
pip install -r requirements-backend.txt
pip install -r requirements-genai.txt
pip install -r requirements-data.txt

cp .env.example .env
# Set GROQ_API_KEY — free key at https://console.groq.com/keys

python -m backend.run
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

Run the demo pipeline:

```bash
curl -X POST http://localhost:8000/api/detect/2024-10-G4
```

### Docker (recommended)

```bash
docker compose up --build
# Backend:  http://localhost:8000
# Frontend: http://localhost:3000
```

The frontend waits for `/health/live` before starting.

## Demo Storms

Two pre-cached storms are available out of the box:

| Storm ID | Date | G-Scale | CME Speed | Kp | Flare |
|----------|------|---------|-----------|-----|-------|
| `2024-10-G4` | Oct 10, 2024 | G4 | 1480 km/s | 8.3 | X1.8 / R3 |
| `2024-05-G5` | May 10, 2024 | G5 | 2200 km/s | 9.0 | X5.8 / R5 |

These are the only valid `storm_id` values — the pipeline rejects anything else with 404.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/detect/{storm_id}` | Run full 5-step pipeline |
| `GET` | `/api/storms` | List available + completed storms |
| `GET` | `/api/result/{storm_id}` | Full pipeline result for a completed storm |
| `GET` | `/api/advisory/{advisory_id}` | Single verified advisory + provenance trace |
| `WS` | `/ws/stream` | Real-time pipeline event streaming |
| `GET` | `/health` | Basic health |
| `GET` | `/health/ready` | Readiness — checks ML, CV, GenAI layers |
| `GET` | `/health/live` | Liveness — process check |
| `GET` | `/metrics` | Prometheus-format metrics |

Rate limit: 30 seconds between pipeline runs per storm ID.

### POST /api/detect/{storm_id}

```json
{
  "storm_id": "2024-10-G4",
  "cv_event": {
    "storm_id": "2024-10-G4",
    "confidence": 0.91,
    "scales": {"G": 4, "S": 0, "R": 3},
    "cme": {"speed_km_s": 1480, "angular_width_deg": 130, ...},
    "flare": {"class": "X1.8", "r_scale": 3, ...},
    "l1_solar_wind": {"bz_nt": -28.0, "speed_km_s": 650, ...}
  },
  "impact_prediction": {
    "gps_error_m": 12.81,
    "gps_error_ci_low": 6.59,
    "gps_error_ci_high": 13.28,
    "hf_blackout_prob": 0.898,
    "hf_blackout_ci_low": 0.657,
    "hf_blackout_ci_high": 0.927
  },
  "advisories": [...],
  "verified_advisories": [...],
  "provenance_traces": [...],
  "errors": [],
  "completed_at": "2024-10-10T19:58:59Z"
}
```

### WebSocket /ws/stream

Send:
```json
{"action": "run_pipeline", "storm_id": "2024-10-G4"}
```

Receive a stream of events:

| Event | When |
|-------|------|
| `pipeline.stage` | Each stage start/complete/fail |
| `agent.thinking` | Per-agent RAG, generation, self-check steps |
| `advisory.generated` | Per advisory — full `AdvisoryOutput` in `data` |
| `verifier.check` | Per rule check — `field`, `proposed`, `corrected_to` |
| `advisory.verified` | Per verified advisory |
| `pipeline.complete` | Pipeline finished — totals + error list |
| `pipeline.error` | Unrecoverable stage failure |
| `agent.error` | Individual agent failure |

## Environment Variables

All backend settings use the `HELIOOPS_` prefix. GenAI settings use `GROQ_` directly.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | — | **Yes** | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | No | Primary generation model |
| `GROQ_MAX_TOKENS` | `2048` | No | Max tokens per generation call |
| `GROQ_CHECKER_MODEL` | `llama-3.1-8b-instant` | No | Self-check model (lighter) |
| `MAX_PROMPT_TOKENS` | `4000` | No | RAG context token cap |
| `HELIOOPS_HOST` | `0.0.0.0` | No | Bind address |
| `HELIOOPS_PORT` | `8000` | No | Port |
| `HELIOOPS_WORKERS` | `1` | No | Uvicorn worker count |
| `HELIOOPS_RELOAD` | `true` | No | Hot reload (disable in prod) |
| `HELIOOPS_LOG_LEVEL` | `INFO` | No | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `HELIOOPS_LOG_FORMAT` | `json` | No | `json` or `console` |
| `HELIOOPS_ML_CHECKPOINT_DIR` | `ML_after_CV/checkpoints` | No | LightGBM `.pkl` path |
| `HELIOOPS_CHROMA_PERSIST_PATH` | `data/chroma_db` | No | ChromaDB path |
| `HELIOOPS_RESULT_REPOSITORY` | `memory` | No | `memory` or `supabase` |
| `HELIOOPS_SUPABASE_URL` | — | If supabase | Supabase project URL |
| `HELIOOPS_SUPABASE_ANON_KEY` | — | If supabase | Supabase anon key |

## Project Structure

```
HelioOps/
├── cv/                         # Layer 1: CV Detection
│   ├── detect.py               # Entry point: detect(storm_id), detect_live()
│   ├── preprocessing.py        # FITS → running-difference frames
│   ├── threshold_detector.py   # Radial-profile CME detector
│   ├── donki_client.py         # NASA DONKI CME physics API
│   ├── flare_classifier.py     # GOES XRS → X/M/C class + R-scale
│   ├── l1_client.py            # DSCOVR L1 solar wind (Bz, speed, density)
│   ├── fusion.py               # Multi-source fusion → StormEvent
│   └── cache_fits.py           # FITS → PNG conversion
│
├── ML_after_CV/                # Layer 2: Impact Prediction
│   ├── inference.py            # predict(storm_dict) → ImpactPrediction
│   ├── 01_data_generation_eda.py
│   ├── 02_train_and_tune.py
│   ├── 03_anchor_test.py
│   ├── checkpoints/            # 6 .pkl models (gps/hf × q025/q500/q975)
│   └── FINAL_RESULTS.md
│
├── genai/                      # Layer 3: Verified Advisory
│   ├── orchestrator.py         # AgentScope parallel fan-out
│   ├── impact_router.py        # Deterministic G-scale → severity matrix
│   ├── retriever.py            # ChromaDB query (BGE-small, cosine)
│   ├── guardrails.py           # Schema validation, severity check, self-check
│   ├── verifier.py             # Zero-LLM rule engine (ICAO, NERC, GMDSS)
│   ├── contracts.py            # VerifiedAdvisory, ProvenanceTrace schemas
│   ├── models.py               # Pydantic models: StormEvent, AdvisoryOutput
│   ├── config.py               # LLM + RAG config knobs
│   ├── agents/                 # aviation, grid, maritime, telecom agents
│   └── prompts/                # Industry-specific system prompts
│
├── embeddings/                 # RAG Knowledge Base
│   ├── embedder.py             # BGE-small-en-v1.5 wrapper
│   ├── chunker.py              # Token-aware chunking (512 tok, 64 overlap)
│   ├── retrieval.py            # Query → cosine search → formatted context
│   ├── collections.py          # ChromaDB collection management
│   ├── ingest_aviation.py      # NAT Doc 007 → aviation_kb (242 chunks)
│   ├── ingest_grid.py          # NERC TPL-007-4 → grid_kb (101 chunks)
│   ├── ingest_maritime.py      # IMO GMDSS 2019 → maritime_kb (2 chunks)
│   └── ingest_impact_matrix.py # NOAA scales → impact_matrix_kb (166 chunks)
│
├── backend/                    # Layer 4: FastAPI Server
│   ├── app.py                  # Endpoints, WebSocket, CORS, middleware
│   ├── pipeline.py             # run_full_pipeline(), stream_full_pipeline()
│   ├── adapter.py              # cv.StormEvent → genai.StormEvent bridge
│   ├── config.py               # Pydantic Settings (HELIOOPS_ prefix)
│   ├── logging.py              # structlog JSON setup
│   ├── health.py               # Health endpoints + Prometheus counters
│   ├── middleware.py           # Security headers, request ID, rate limiting
│   ├── ports/                  # Abstract interfaces (DetectionPort, etc.)
│   ├── adapters/               # Concrete implementations of ports
│   └── run.py                  # uvicorn entry point
│
├── frontend/                   # Next.js 14 Dashboard
│   └── src/                    # React + TypeScript + Tailwind
│
├── supabase/                   # PostgreSQL schema (optional persistence)
│   ├── 001_schema.sql          # 8 tables, enums, indexes, triggers
│   ├── 002_rls.sql             # Row Level Security
│   └── 003_seed.sql            # Demo data (G4 + G5 storms)
│
├── data/
│   ├── chroma_db/              # ChromaDB persistence
│   ├── cached/                 # FITS cache + annotated PNGs (gitignored)
│   ├── aviation/               # NAT Doc 007 PDF
│   ├── grid/                   # NERC TPL-007-4 PDFs
│   ├── maritime/               # IMO GMDSS 2019 PDF
│   └── impact_matrix/          # NOAA space weather scales
│
├── ml/stubs/                   # Fallback StormEvent JSON (G4 + G5)
├── tests/                      # 64 pytest tests
│   ├── test_option_c.py        # 51 CV detection tests
│   ├── test_pipeline.py        # 13 backend + ML tests
│   └── conftest.py
│
├── runbooks/                   # Operational playbooks
│   ├── detection-failure.md
│   ├── groq-outage.md
│   ├── high-error-rate.md
│   └── high-latency.md
│
├── k8s/                        # Kubernetes manifests (base, staging, prod)
├── infra/                      # Terraform: VPC + EKS modules
├── argocd/                     # ArgoCD GitOps application manifests
├── chaos/                      # Chaos Mesh experiments (staging only)
├── .github/workflows/ci.yml    # CI: lint → test → build → Docker
├── Dockerfile.backend          # Multi-stage Python 3.12
├── Dockerfile.frontend         # Multi-stage Node 20
├── docker-compose.yml
└── .env.example
```

## Layer Details

### Layer 1: CV Detection

`cv/detect.py` exposes two functions:

- `detect(storm_id, base_dir=".")` — deterministic replay from cached data. Same input → byte-identical output.
- `detect_live()` — hits live GOES XRS, DSCOVR, and DONKI endpoints.

**Fallback chain** (each step gracefully degrades):
1. PNGs in cache → use them; else fall back to stub JSON
2. Threshold detector finds CME → real bounding box; else use pre-defined stub bbox
3. DONKI cache → real CME kinematics; else fetch live; else use stub speed/width
4. `fuse()` succeeds → return StormEvent; else load stub JSON from `ml/stubs/`

**Confidence formula:**
```
confidence = 0.4 × detector_confidence
           + 0.2 × flare_signal
           + 0.2 × l1_wind_signal
           + 0.2 × cme_kinematic_signal
```

**Output — `StormEvent`:**
```python
StormEvent(
    storm_id="2024-10-G4",
    confidence=0.91,
    scales={"G": 4, "S": 0, "R": 3},
    cme={"speed_km_s": 1480, "angular_width_deg": 130, ...},
    flare={"class": "X1.8", "r_scale": 3, ...},
    l1_solar_wind={"bz_nt": -28.0, "speed_km_s": 650, ...},
    noaa_alert_raw="G4 Watch...",
)
```

Run standalone:
```bash
python -m cv.detect --storm 2024-10-G4
python -m cv.detect --storm 2024-05-G5 --dry-run
python -m cv.detect --live
```

### Layer 2: ML Impact Prediction

Six LightGBM models trained with pinball loss (quantile regression). Each model is an independent `.pkl` file; monotonicity is enforced post-prediction via `sorted()`.

**Models:**
- `gps_q025.pkl`, `gps_q500.pkl`, `gps_q975.pkl` — GPS L1 position error (meters)
- `hf_q025.pkl`, `hf_q500.pkl`, `hf_q975.pkl` — HF radio blackout probability (0–1)

**9 input features extracted from StormEvent:**

| Feature | Source |
|---------|--------|
| `g_scale` | `scales["G"]` |
| `kp_index` | G→Kp map: `{1:5, 2:6, 3:7, 4:8.3, 5:9}` |
| `bz_nt` | `l1_solar_wind["bz_nt"]` |
| `wind_speed_km_s` | `l1_solar_wind["speed_km_s"]` |
| `cme_speed_km_s` | `cme["speed_km_s"]` |
| `cme_width_deg` | `cme["angular_width_deg"]` |
| `r_scale` | `scales["R"]` |
| `geomag_lat_bin` | hardcoded `1` (mid-latitude) |
| `local_time_bin` | hardcoded `1` (dayside) |

**Fallback:** If any checkpoint is missing, returns conservative defaults: GPS=20m [8–35m], HF=85% [60–95%].

**Validated performance on synthetic data:**

| Metric | GPS Error | HF Blackout |
|--------|-----------|-------------|
| R² | 0.9858 | 0.9577 |
| MAE | 0.15 m | 3.2% |
| PICP (95% CI coverage) | 96.4% | 94.7% |
| G5 anchor: predicted | 17.5 m | 84.3% |
| G5 anchor: required | > 15 m | > 80% |

Note: models were trained on synthetic data generated from physical proxy rules. Production deployment requires re-training on NASA OMNIWeb historical data.

### Layer 3: GenAI Advisory

**Routing (deterministic):**

`genai/impact_router.py` maps G-scale to industry severity with no LLM involvement:

| G-Scale | Aviation | Grid | Maritime | Telecom |
|---------|----------|------|----------|---------|
| G1 | LOW | LOW | NONE | NONE |
| G2 | MEDIUM | MEDIUM | LOW | LOW |
| G3 | HIGH | HIGH | MEDIUM | MEDIUM |
| G4 | CRITICAL | CRITICAL | HIGH | HIGH |
| G5 | CRITICAL | CRITICAL | CRITICAL | CRITICAL |

Only industries with severity ≥ LOW receive an advisory.

**Per-agent pipeline (runs in parallel for each triggered industry):**

1. Build ChromaDB query from storm parameters
2. Retrieve: top 8 chunks from industry KB + top 4 from impact_matrix_kb
3. Drop chunks below 0.35 cosine similarity
4. Generate advisory (Groq Llama 3.3 70B, temp=0.1, JSON mode)
5. Validate Pydantic schema — every `action_item` must have `source_ref`
6. Check severity ≥ deterministic matrix minimum
7. Cross-check `sources_cited` against retrieved chunk IDs
8. Run self-check (separate Groq call, lighter `GROQ_CHECKER_MODEL`)
9. Compute confidence score
10. Apply safety flags (non-blocking audit markers)
11. Retry up to 3× with error text injected into prompt; else return `ESCALATE_TO_SPECIALIST` fallback

**Confidence score:**
```
score = avg(chunk cosine similarities)
      + 0.02 × (action items with verified source_ref)
      - 0.08 × (action items with missing/unverifiable source_ref)
      + 0.10 if avg similarity > 0.6
score = clamp(score, 0.0, 1.0)
```

**Safety flags:**

| Flag | Trigger |
|------|---------|
| `SEVERITY_MISMATCH` | LLM severity < deterministic matrix minimum |
| `HALLUCINATION_DETECTED` | Self-check found unsupported claims |
| `LOW_COVERAGE` | Fewer than 3 chunks above similarity threshold |
| `LOW_CONFIDENCE` | `confidence_score < 0.50` |
| `CITATION_GAP` | `source_ref` not in retrieved chunk IDs |
| `GENERATION_FAILED` | All 3 retries exhausted |

**Deterministic verifier (zero LLM, runs after all agents):**

| Rule | Industry | Valid Set | Action on Violation |
|------|----------|-----------|---------------------|
| HF frequency | aviation, maritime | `{3, 5, 8, 11, 17}` MHz (ICAO NAT) | Blocked, corrected to nearest valid |
| Reroute latitude | aviation | G3→78°N, G4→70°N, G5→60°N | Blocked, corrected to threshold |
| GIC operating step | grid | NERC TPL-007-4 Appendix B keywords | Blocked if not matched |
| GMDSS channel | maritime | Valid GMDSS distress/working channels | Blocked if not matched |

Verifier status values: `passed` / `passed_with_corrections` / `blocked`.

**RAG knowledge bases:**

| Collection | Source | Chunks |
|------------|--------|--------|
| `aviation_kb` | NAT Doc 007 | 242 |
| `grid_kb` | NERC TPL-007-4 | 101 |
| `impact_matrix_kb` | NOAA space weather scales | 166 |
| `maritime_kb` | IMO GMDSS 2019 | 2 |
| `telecom_kb` | (empty — intentional) | 0 |

Telecom agents always produce `LOW_COVERAGE` advisories by design; no authoritative telecom regulatory document has been ingested.

To rebuild ChromaDB from source PDFs:
```bash
python -m embeddings.ingest_aviation
python -m embeddings.ingest_grid
python -m embeddings.ingest_maritime
python -m embeddings.ingest_impact_matrix
```

### Layer 4: Backend

Hexagonal architecture — domain logic depends on abstract `backend/ports/*` interfaces; `backend/adapters/*` provide concrete implementations. Swap the repository (in-memory ↔ Supabase) or any layer implementation without touching pipeline code.

**Schema bridge:** `cv.fusion.StormEvent` and `genai.models.StormEvent` are different schemas. `backend/adapter.py` translates between them:

| CV field | GenAI field | Transform |
|----------|-------------|-----------|
| `storm_id` | `alert_id` | direct |
| `scales["G"]` (int) | `g_scale` (GScale enum) | `GScale(f"G{v}")` clamped [1,5] |
| `scales["S"]` (int) | `s_scale` (str or None) | `f"S{v}"` if > 0 |
| `scales["R"]` (int) | `r_scale` (str or None) | `f"R{v}"` if > 0 |
| derived | `kp_index` | parsed from alert text or G→Kp map |
| `cme["arrival_estimate"]` | `estimated_arrival_utc` | ISO parse |
| `noaa_alert_raw` | `raw_alert_text` | direct |

**Persistence:** Default is in-memory (`HELIOOPS_RESULT_REPOSITORY=memory`). Set to `supabase` and provide `HELIOOPS_SUPABASE_URL` + `HELIOOPS_SUPABASE_ANON_KEY` to persist results across restarts.

## Database (Supabase, optional)

8 PostgreSQL tables with Row Level Security:

| Table | Purpose |
|-------|---------|
| `storm_events` | CV layer output |
| `impact_predictions` | ML quantile regression results |
| `advisories` | GenAI advisory output per industry |
| `action_items` | Individual actions within each advisory |
| `verified_advisories` | Post-verifier advisory |
| `verifier_checks` | Individual rule check results |
| `provenance_traces` | 6-step audit chain per advisory |
| `pipeline_runs` | Denormalized pipeline execution summary |

Apply in order via Supabase SQL editor:
```bash
supabase/001_schema.sql   # tables + indexes + triggers
supabase/002_rls.sql      # RLS policies
supabase/003_seed.sql     # demo data
```

## Testing

```bash
# All 64 tests
pytest tests/ -v

# By layer
pytest tests/test_option_c.py -v    # 51 CV tests
pytest tests/test_pipeline.py -v    # 13 backend + ML tests

# By class
pytest tests/test_pipeline.py::TestMLInference -v
pytest tests/test_pipeline.py::TestAdapter -v
pytest tests/test_pipeline.py::TestFullPipeline -v
```

## Infrastructure

### Kubernetes

```bash
kubectl apply -k k8s/staging/
kubectl apply -k k8s/production/    # 3 replicas, hardened
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

- `GET /metrics` — Prometheus counters: pipeline request count, error count, latency p99, WebSocket connections
- `GET /health/ready` — dependency check: ML checkpoints, CV cache, GenAI config
- `runbooks/` — step-by-step playbooks for: detection failure, Groq outage, high error rate, high latency
- `chaos/` — Chaos Mesh experiments (CPU stress, network delay, pod kill) — staging only, scheduled

## Key Design Decisions

**Deterministic detector over CNN** — No labeled coronagraph dataset exists at the required scale. Threshold detection on running-difference frames with NASA DONKI physics produces reproducible, auditable results with no GPU dependency.

**LightGBM over neural nets for impact** — Quantile regression produces calibrated 95% confidence intervals. A neural net would require distributional output layers and additional calibration; LightGBM with pinball loss achieves this directly. Six independent models + post-hoc `sorted()` enforcement handle quantile crossing.

**AgentScope over LangGraph** — Parallel fan-out via `asyncio.gather` + `asyncio.Queue` event drain is more transparent than LangGraph's `Send` API for dynamic dispatch. The `_AGENT_REGISTRY` dict makes adding/removing industries a one-line change.

**Deterministic verifier after LLM** — LLMs hallucinate specific technical values even with RAG grounding. The verifier catches and corrects safety-critical errors (wrong HF frequency, wrong reroute latitude) before advisories reach operators. It produces a `ProvenanceTrace` — a 6-step audit chain from raw data to output — which the frontend renders.

**Bridge, don't rewrite** — The CV and GenAI layers have different `StormEvent` schemas developed independently. `backend/adapter.py` bridges them without modifying either layer.

**In-memory first, Supabase opt-in** — The default `memory` repository means the system runs with zero external dependencies beyond Groq. Switching to Supabase for persistence is a single env var change.

## Team

| Member | Ownership |
|--------|-----------|
| Parshva | Layer 2: ML impact models, synthetic data pipeline |
| Neal | Layer 1: CV detection, ML pipeline integration, dashboard, backend security |
| Priyanshu | Layer 3: GenAI advisory, verifier, backend pipeline, database |
| Tirth | Layer 4: Frontend dashboard, DevOps, deployment |
