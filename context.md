# HelioOps — Project Context

> Paste this file into a fresh Claude chat to get the full picture of this repo.
> It is standalone: it covers what the project is, how it works, what the code
> actually does today, and where the docs and the code disagree.
>
> Generated 2026-08-21 from a full read of the repo at commit `232ea94`.

---

## 1. What this is

**HelioOps** is a real-time space weather platform. It detects geomagnetic storms
from solar imagery and generates regulatory-compliant operational advisories for
four industries: **aviation, power grid, maritime, telecom**.

It is a **4-person student/hackathon project**, built in one week (8–14 June 2026),
80 commits, currently dormant. It is engineered like a production system
(hexagonal architecture, k8s, Terraform, ArgoCD, chaos engineering) but has never
been deployed to a real cluster. Treat the DevOps layer as a *deliverable artifact*,
not live infrastructure.

- **Repo:** `https://github.com/Neal006/private-helioops.git` (branch `main`)
- **Local path:** `C:\Users\Tirth Patel\HelioOps_Private` (Windows — use PowerShell)
- **Working tree:** clean, matches origin

### Team & ownership

| Member | Layer | Commits |
|---|---|---|
| Neal (`Neal006`) | Layer 1 CV detection, ML integration, dashboard, backend security | 33 |
| Tirth (`trhatwork@gmail.com`) — *you* | Layer 4 frontend dashboard, DevOps, deployment | 22 |
| Priyanshu Doshi | Layer 3 GenAI advisory, verifier, backend pipeline, database | 14 |
| Parshva (`SoulBreaker9`) | Layer 2 ML impact models, synthetic data | 11 |

---

## 2. The four-layer pipeline

```
Solar imagery (FITS/PNG) + NOAA alerts
  │
  ├─ Layer 1  cv/            Deterministic CME detection on running-difference
  │                          frames + NASA DONKI physics + GOES XRS flare class
  │                          + DSCOVR L1 solar wind  →  StormEvent
  │
  ├─ Layer 2  ML_after_CV/   6 LightGBM quantile models (q0.025/q0.5/q0.975)
  │                          →  GPS L1 error ±95% CI, HF blackout prob ±95% CI
  │
  ├─ Layer 3  genai/         Deterministic G-scale routing → 4 parallel industry
  │                          agents (AgentScope + Groq Llama 3.3 70B + ChromaDB
  │                          RAG) → 10-layer anti-hallucination guardrails →
  │                          zero-LLM rule verifier  →  VerifiedAdvisory
  │
  └─ Layer 4  backend/ +     FastAPI REST + WebSocket; Next.js 14 dashboard.
              frontend/      Optional Supabase PostgreSQL persistence.
```

The core design bet: **LLMs generate prose, deterministic code owns every
safety-critical number.** Severity comes from a hardcoded G-scale matrix, and a
zero-LLM verifier corrects HF frequencies, reroute latitudes, GIC steps, and
GMDSS channels before anything reaches an operator. Every advisory carries a
6-step `ProvenanceTrace` from raw data to output.

### Only two storms exist

`2024-10-G4` (Oct 10 2024, G4, CME 1480 km/s, Kp 8.3, X1.8/R3) and
`2024-05-G5` (May 10 2024, G5, CME 2200 km/s, Kp 9.0, X5.8/R5).
Anything else 404s. **Adding a storm means editing two independently maintained
lists**: `cv/detect.py:38` `STORM_CONFIGS` *and* `backend/config.py:64`
`AVAILABLE_STORM_IDS`.

---

## 3. Repo map

```
HelioOps_Private/
├── cv/                    Layer 1 — detect.py (entry), preprocessing.py,
│                          threshold_detector.py, donki_client.py,
│                          flare_classifier.py, l1_client.py, fusion.py,
│                          cache_fits.py
├── ML_after_CV/           Layer 2 — inference.py (entry), 01_data_generation_eda.py,
│                          02_train_and_tune.py, 03_anchor_test.py,
│                          data/synthetic_storms.csv, FINAL_RESULTS.md
│                          ⚠ checkpoints/ is ABSENT (see §6)
├── genai/                 Layer 3 — orchestrator.py, impact_router.py, retriever.py,
│                          guardrails.py, verifier.py, contracts.py, models.py,
│                          config.py, agents/{aviation,grid,maritime,telecom,base}.py,
│                          prompts/{...}.py
├── embeddings/            RAG build — embedder.py (BGE-small-en-v1.5), chunker.py,
│                          retrieval.py, collections.py, ingest_{aviation,grid,
│                          maritime,impact_matrix}.py
├── backend/               Layer 4 API — app.py, pipeline.py, adapter.py, config.py,
│                          logging.py, health.py, middleware.py, run.py,
│                          ports/{detection,prediction,advisory,repository}.py,
│                          adapters/{detection,prediction,advisory,repository,schema}_adapter.py
├── frontend/              Next.js 14 dashboard (see §5)
├── supabase/              001_schema.sql, 002_rls.sql, 003_seed.sql
├── ml/stubs/              Fallback StormEvent JSON for both storms — THIS IS WHY
│                          THE DEMO WORKS WITHOUT CACHED IMAGERY
├── data/                  Source regulatory PDFs (11 MB committed) + gitignored caches
├── tests/                 7 pytest files, 137 tests (see §7)
├── runbooks/              4 ops playbooks (detection-failure, groq-outage,
│                          high-error-rate, high-latency)
├── k8s/ infra/ argocd/ chaos/   IaC — real, well-formed, never deployed (§8)
├── docs/                  notebooklm_script.md, ml_research/eda_plots/,
│                          archived/{change_in_plan,ml_dl}.md
├── .github/workflows/ci.yml
├── Dockerfile.backend  Dockerfile.frontend  docker-compose.yml
├── requirements-{backend,genai,data}.txt
├── README.md              537 lines, the primary doc — mostly accurate, see §9
├── ARCHITECTURE_CHANGES.md   Narrative of the 11 production-hardening additions
├── CI_CD_REQUIREMENTS.txt    Team checklist of missing data artifacts — honest
└── pdf.md                    17-slide pitch deck narrative
```

---

## 4. Backend (`backend/`)

FastAPI, hexagonal architecture (ports = abstract interfaces, adapters = impls).

### Routes

| Method | Path | Handler | File:line |
|---|---|---|---|
| POST | `/api/detect/{storm_id}` | `detect_storm` | `backend/app.py:138` |
| GET | `/api/storms` | `list_storms` | `backend/app.py:187` |
| GET | `/api/advisory/{advisory_id}` | `get_advisory_endpoint` | `backend/app.py:207` |
| GET | `/api/result/{storm_id}` | `get_result_endpoint` | `backend/app.py:217` |
| WS | `/ws/stream` | `websocket_stream` | `backend/app.py:244` |
| GET | `/health` | | `backend/health.py:84` |
| GET | `/health/live` | | `backend/health.py:93` |
| GET | `/health/ready` | | `backend/health.py:98` |
| GET | `/metrics` | Prometheus text | `backend/health.py:146` |

Rate limit: 30s between pipeline runs per storm ID.

### WebSocket protocol

Send `{"action": "run_pipeline", "storm_id": "2024-10-G4"}`. Receive a stream of:
`pipeline.stage`, `agent.thinking`, `advisory.generated`, `verifier.check`,
`advisory.verified`, `pipeline.complete`, `pipeline.error`, `agent.error`.

### Middleware — order gotcha

`app.py` registers CORS (74) → SecurityHeaders (81) → RequestID (82). Starlette
**prepends**, so actual request-time execution is the reverse:
`RequestID → SecurityHeaders → CORS → route`. Undocumented anywhere else.

### Ports & adapters — partly decorative

- `CVDetectionAdapter` and `MLPredictionAdapter` are wired and live (`app.py:86-87`).
- `GenAIAdvisoryAdapter` / `GenAIVerificationAdapter` are instantiated at
  `app.py:88-89` but **never called** — `backend/pipeline.py` imports
  `genai.run_pipeline` / `genai.stream_pipeline` / `genai.verifier.verify_advisory`
  directly (`pipeline.py:125,138,288,318`). The advisory port layer is ornamental.
- `LiveDetectionAdapter` is named in `DetectionPort`'s docstring but **does not exist**.
- `FallbackPredictionAdapter` exists but is never wired; the real fallback lives
  inside `ML_after_CV/inference.py:predict()`.

### Two copies of the schema bridge — maintenance trap

`cv.fusion.StormEvent` and `genai.models.StormEvent` are different schemas. The
bridge exists **twice, with byte-identical logic**:
- `backend/adapter.py:45` `adapt_storm_event()` — **this is the live one**
  (imported inline at `pipeline.py:106` and `:256`)
- `backend/adapters/schema_adapter.py:42` `adapt_storm_event()` — imported at
  `app.py:56`, never called. Dead.

Fixing a bug in one will not fix the other.

### Two copies of result state

`backend/pipeline.py:44-45` keeps module-global `_RESULTS` / `_ADVISORY_INDEX`
dicts that are **always in-memory**, regardless of `HELIOOPS_RESULT_REPOSITORY`.
The swappable `result_repo` (memory ↔ Supabase) is populated separately by
`_persist_result()` in `app.py` and only serves the GET endpoints. The README's
"swap persistence with one env var" is true for reads, not for the pipeline's own
bookkeeping.

---

## 5. Frontend (`frontend/`)

Next.js 14 App Router, React 18, TypeScript, Tailwind 3.4. Dark theme only.

### Routes

| Path | File |
|---|---|
| `/` | `src/app/page.tsx` — marketing landing, scroll-scrubbed 178-frame canvas animation |
| `/dashboard` | `src/app/dashboard/page.tsx` — ⚠ **duplicate/stale** copy of the storms list |
| `/dashboard/storms` | `src/app/dashboard/storms/page.tsx` — the real storm list (skeletons, empty state, error boundary) |
| `/dashboard/storms/[stormId]` | detail: CV scales, CME/solar wind, impact, run-pipeline button |
| `/dashboard/pipeline` | WebSocket pipeline runner + live progress + event stream |
| `/dashboard/results/[stormId]` | full results: advisories, verified advisories, provenance |
| `/dashboard/health` | health/readiness + parsed Prometheus metrics, 10s auto-refresh |

### Key files

- `src/lib/api.ts` — typed fetch wrapper, `ApiError`, 1 retry w/ backoff on 5xx,
  `parseMetrics()` Prometheus text parser. Base URL: **`NEXT_PUBLIC_API_URL`**
  (defaults `http://localhost:8000`).
- `src/lib/ws-client.ts` — `WsClient` singleton, auto-reconnect 1s→30s cap, pub/sub.
- `src/types/storm.ts` (321 lines) — single source of truth, hand-mirrored from
  `backend/pipeline.py`, `genai/models.py`, `genai/contracts.py`. Includes a
  `WsEvent` discriminated union with runtime type guards. **Not generated — keep
  in sync manually when backend schemas change.**
- `next.config.mjs` — dev `rewrites()` proxy `/api`, `/health`, `/metrics`, `/ws` → `localhost:8000`.

### Components

`components/`: EmptyState, ErrorBoundary, Footer, FrameScroller, Navbar,
SectionOverlay, Skeleton, Toast.
`components/dashboard/`: AdvisoryCard, DashboardErrorBoundary, ImpactDisplay,
MetricsDisplay, PipelineProgress, ProvenanceChain, Sidebar, StormCard, StreamLog,
TopBar, VerifiedAdvisoryCard.

### Styling

Tailwind tokens: `deep.black #09090b`, `deep.900/800/700`, `aurora #00FF9D`
(brand green, + light/dark/glow), `warm #f59e0b`. Fonts: Space Grotesk (display/body),
JetBrains Mono. Utilities in `globals.css`: `.glass`, `.glass-strong`,
`.gradient-text*`. Conditional classes via `cn()` (`clsx` + `tailwind-merge`).

### Frontend cruft

- `three`, `@react-three/fiber`, `@react-three/drei`, `lenis` — installed, **zero
  imports**. Dead weight from an abandoned 3D hero.
- `eslint-config-next ^16.2.9` alongside `next ^14.2.35` — accidental major bump.
- Navbar/Footer links all `href="#"`; "Sign In" button has no handler.
- `frontend/dashboard_implementation.md` — a planning doc left in the tree.

### Frontend tests

Vitest 4.1.8 + jsdom + Testing Library. `npm test` (run) / `npm run test:watch`.
**24 files, 255 test cases** — 19 component/page tests, 4 lib tests, 1 types test.

---

## 6. ⚠ What is missing on a fresh clone

This is the single most important section. The repo **ships without three
artifacts** and every layer degrades silently rather than failing loudly.
`CI_CD_REQUIREMENTS.txt` documents this in the team's own words.

| Missing | Consequence |
|---|---|
| `ML_after_CV/checkpoints/*.pkl` (6 models) | `predict()` always hits the fallback branch (`inference.py:111`) and returns hardcoded **GPS 20.0 m [8–35], HF 85% [60–95]** for *every* storm. The G4/G5 numbers in the README's example JSON are unreachable until someone runs `02_train_and_tune.py`. Also: **`lightgbm` and `joblib` are in no requirements file**; `joblib` is imported in a try/except and silently disables ML. |
| `data/chroma_db/` | ChromaDB `PersistentClient` silently creates an **empty** DB. `retrieve_chunks()` returns `[]`, prompts get `[NO CONTEXT RETRIEVED]`, `sources_cited` fails validation, all 3 retries exhaust, and **every** advisory becomes the `ESCALATE_TO_SPECIALIST` fallback with `LOW_COVERAGE`. Looks like a bug; is actually "you forgot to run the ingest scripts." |
| `data/cached/{ccor1,lasco,donki,xrs,l1}/` | Only `data/cached/alerts/*.txt` exists. **This one is fine** — `cv/detect.py:129-133` falls back to `ml/stubs/storm_event_*.json`, which *are* committed, so Layer 1 works end-to-end out of the box exactly as documented. |

Fix RAG with:
```powershell
python -m embeddings.ingest_aviation
python -m embeddings.ingest_grid
python -m embeddings.ingest_maritime
python -m embeddings.ingest_impact_matrix
```

### Other landmines

- **`GROQ_API_KEY` is required but never fails fast.** `backend/config.py:45`
  defaults to `""` and only `warnings.warn`s. The app boots fine; every advisory
  then fails with an auth error deep inside a pipeline run as an `agent.error`
  event. Free key: <https://console.groq.com/keys>.
- **Offline = 200 OK with empty advisories.** Every stage of `run_full_pipeline`
  is wrapped in try/except and continues. Failures land quietly in `result.errors`.
- **`HELIOOPS_CHROMA_PERSIST_PATH` and `HELIOOPS_ML_CHECKPOINT_DIR` are dead env
  vars.** They're in `config.py`, `.env.example`, the README, and even the k8s
  ConfigMap — but `genai/config.py:17`, `embeddings/config.py:2`, and
  `ML_after_CV/inference.py:25` all hardcode their own paths. Setting them does nothing.
- **`_prewarm_embedder()` (`genai/orchestrator.py:41-46`)** loads a BGE
  sentence-transformers model on the first pipeline call. No internet + no HF
  cache = hang or hard fail. The comment warns of a PyTorch "cannot copy out of
  meta tensor" race if the prewarm is skipped.
- **Rate limiter is process-local** (`backend/middleware.py:41,63`). With
  `HELIOOPS_WORKERS>1` each worker has its own limit, defeating the 30s guarantee.
- **`SupabaseResultRepository` makes synchronous `httpx.Client` calls** inside
  async handlers — blocks the event loop on every pipeline completion.

---

## 7. Running it

### Local (PowerShell)

```powershell
pip install -r requirements-backend.txt
pip install -r requirements-genai.txt
pip install -r requirements-data.txt

Copy-Item .env.example .env
# then set GROQ_API_KEY in .env

python -m backend.run       # http://localhost:8000  |  docs at /docs
```

Frontend:
```powershell
cd frontend
npm ci --legacy-peer-deps
npm run dev                 # http://localhost:3000
```

Trigger a run:
```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/detect/2024-10-G4
```

CV standalone:
```powershell
python -m cv.detect --storm 2024-10-G4
python -m cv.detect --live
```

### Docker

```powershell
docker compose up --build
```
backend `8000` (healthcheck `/health/live`), frontend `3000` (waits for backend
healthy, `NEXT_PUBLIC_API_URL=http://backend:8000`). Volumes mount `./data` and
`./ML_after_CV/checkpoints` into the backend.

### Tests

```powershell
pytest tests/ -v            # 137 tests across 7 files
npm --prefix frontend test  # 255 tests across 24 files
```

| File | tests | note |
|---|---|---|
| `tests/test_option_c.py` | 43 | CV detection/fusion/preprocessing/DONKI/flare/L1 |
| `tests/test_security.py` | 23 | headers, rate limiter, storm-ID regex, CORS, WS origin |
| `tests/test_cv_preprocessing.py` | 21 | |
| `tests/test_api_endpoints.py` | 16 | |
| `tests/test_pipeline.py` | 13 | ML inference, adapter, integration |
| `tests/test_middleware.py` | 12 | |
| `tests/test_retrieval.py` | 9 | ⚠ **requires a populated `data/chroma_db`** |

`tests/conftest.py` provides session-scoped `g4_fixture()` from
`tests/fixtures/march_2024_g4.json` and puts the project root on `sys.path`.

---

## 8. Infra & CI — real code, never deployed

### CI (`.github/workflows/ci.yml`)

Triggers on push/PR to `main`. Jobs: `lint-backend`, `test-backend`,
`lint-frontend`, `build-frontend`, `docker-build`.

**Every lint and test step is wrapped in `|| true`** — they cannot fail the build.
Only `npm run build` and the two Docker builds can actually fail CI. `test-backend`
runs just `test_pipeline.py` + `test_option_c.py` (56 of 137 tests) with
`GROQ_API_KEY: test-key`; the other 5 test files never run in CI.
`CI_CD_REQUIREMENTS.txt` states this openly: *"CI is configured with `|| true` so
it passes even without data, but tests will be shallow."*

### k8s / Terraform / ArgoCD / chaos

All well-formed and plausible, but nothing indicates a real deployment:

- `k8s/base/` — backend (2 replicas, readiness `/health/ready`, liveness
  `/health/live`, `GROQ_API_KEY` from a `helioops-secrets` Secret, PVC for
  checkpoints), frontend, service, ingress, configmap, servicemonitor, kustomization.
  Overlays: `staging` (2 replicas, DEBUG/console) and `production` (3 replicas,
  WARNING/json, RollingUpdate maxSurge 1 / maxUnavailable 0).
  Ingress host is **`helioops.example.com`** — placeholder.
- `infra/` — Terraform VPC + EKS modules, `us-east-1`, EKS 1.30, production node
  group `m7i.xlarge` (min 3 / max 20 / desired 5). **No tfstate anywhere.**
- `argocd/` — Application manifests pointing at
  **`https://github.com/trh-ds/HelioOps`**, which is *not* the actual remote
  (`Neal006/private-helioops`). They would sync against the wrong repo. Same stale
  URL appears in `ARCHITECTURE_CHANGES.md` and the Dockerfiles.
- `chaos/` — Chaos Mesh CRDs scoped to `namespace: staging` only: pod-kill (72h),
  network-delay (200ms, weekly, 10 min), cpu-stress (2 workers @ 80%, biweekly, 5 min).

### Dependency hygiene

No exact pins anywhere. `requirements-data.txt` has **zero version constraints**
on any of its 10 packages (`chromadb`, `openai`, `tiktoken`, `pypdf`, `pdfplumber`,
`python-dotenv`, `sentence-transformers`, `redis`, `fakeredis`, `numpy`).
`Dockerfile.backend` also copies `tests/` into the production image.

### Supabase (optional)

`HELIOOPS_RESULT_REPOSITORY=supabase` + `HELIOOPS_SUPABASE_URL` +
`HELIOOPS_SUPABASE_ANON_KEY`. Apply `001_schema.sql` → `002_rls.sql` →
`003_seed.sql`. 8 tables: `storm_events`, `impact_predictions`, `advisories`,
`action_items`, `verified_advisories`, `verifier_checks`, `provenance_traces`,
`pipeline_runs`, plus 4 enums, 9 indexes, and an `updated_at` trigger.

---

## 9. README vs. reality

The README (537 lines) is unusually good, but these claims are stale:

| README says | Code says |
|---|---|
| "64 tests" | **137** `def test_` functions across 7 files; `test_option_c.py` has 43, not 51 |
| RAG retrieves "top 8 industry + top 4 impact_matrix" chunks | `genai/config.py:35-36`: `RAG_TOP_K=5`, `RAG_IMPACT_MATRIX_TOP_K=2` |
| `HELIOOPS_CHROMA_PERSIST_PATH` / `HELIOOPS_ML_CHECKPOINT_DIR` configurable | Both dead — paths hardcoded in 3 modules |
| "Swap repository without touching pipeline code" | True for GET endpoints; `pipeline.py` keeps a parallel always-in-memory store |
| `backend/adapter.py` is *the* bridge | Two byte-identical implementations exist; the one in `adapters/schema_adapter.py` is dead |
| "AgentScope over LangGraph" | Both stacked — `genai/agents/base.py:32-34` and `guardrails.py:24-25` import **`langchain_core` + `langchain_groq.ChatGroq`** alongside `agentscope.message`. Groq calls go through LangChain, not AgentScope |
| LightGBM R²=0.9858 / 0.9577, PICP 96.4% / 94.7% | Real numbers, but **on synthetic data**, and no `.pkl` ships — production needs retraining on NASA OMNIWeb |
| `PredictionPort` docstring: `FallbackPredictionAdapter` handles unavailability | Class is dead code; the real fallback is inside `inference.py` |
| `DetectionPort` docstring: `LiveDetectionAdapter` | Does not exist |

Also: `genai/contracts.py`'s `ImpactMetric` / `ImpactAssessment` are vestigial —
nothing in the live pipeline imports them. Many modules reference a design doc
`imp.md §7.2` that **is not in the repo**.

`genai/orchestrator.py:165` drains its `asyncio.Queue` by polling every 50 ms
(`await asyncio.sleep(0.05)`) rather than awaiting the queue — adds up to 50 ms
per streamed event and busy-polls while agents run.

---

## 10. Domain reference (for reading the code)

**Severity routing** (`genai/impact_router.py`, deterministic, zero LLM):

| G | Aviation | Grid | Maritime | Telecom |
|---|---|---|---|---|
| G1 | LOW | LOW | NONE | NONE |
| G2 | MEDIUM | MEDIUM | LOW | LOW |
| G3 | HIGH | HIGH | MEDIUM | MEDIUM |
| G4 | CRITICAL | CRITICAL | HIGH | HIGH |
| G5 | CRITICAL | CRITICAL | CRITICAL | CRITICAL |

**Deterministic verifier rules** (`genai/verifier.py`, zero LLM):

| Rule | Industry | Valid set | On violation |
|---|---|---|---|
| HF frequency | aviation, maritime | `{3,5,8,11,17}` MHz (ICAO NAT) | corrected to nearest |
| Reroute latitude | aviation | G3→78°N, G4→70°N, G5→60°N | corrected to threshold |
| GIC operating step | grid | NERC TPL-007-4 App. B keywords | blocked |
| GMDSS channel | maritime | valid distress/working channels | blocked |

Status values: `passed` / `passed_with_corrections` / `blocked`.

**Safety flags:** `SEVERITY_MISMATCH`, `HALLUCINATION_DETECTED`, `LOW_COVERAGE`,
`LOW_CONFIDENCE`, `CITATION_GAP`, `GENERATION_FAILED`.

**RAG collections** (when built): `aviation_kb` 242 chunks (NAT Doc 007),
`grid_kb` 101 (NERC TPL-007-4), `impact_matrix_kb` 166 (NOAA scales),
`maritime_kb` 2 (IMO GMDSS 2019), `telecom_kb` **0 — intentionally empty**, so
telecom advisories always carry `LOW_COVERAGE` by design.

**ML features (9):** `g_scale`, `kp_index` (G→Kp map `{1:5,2:6,3:7,4:8.3,5:9}`),
`bz_nt`, `wind_speed_km_s`, `cme_speed_km_s`, `cme_width_deg`, `r_scale`,
`geomag_lat_bin` (hardcoded 1), `local_time_bin` (hardcoded 1).

**Env vars:** `HELIOOPS_` prefix for backend, `GROQ_` for LLM. Full list in
`.env.example`. Only `GROQ_API_KEY` is genuinely required.

---

## 11. If you're picking this up

Highest-value cleanups, roughly in order:

1. **Delete `backend/adapters/schema_adapter.py`** and its `app.py:56` import — a
   dead duplicate of `backend/adapter.py` that will eventually cause a
   fix-in-the-wrong-place bug.
2. **Make `GROQ_API_KEY` fail fast** at startup instead of warning, or make the
   degraded mode obvious in the API response.
3. **Fix or delete the dead env vars** (`HELIOOPS_CHROMA_PERSIST_PATH`,
   `HELIOOPS_ML_CHECKPOINT_DIR`) — they're documented in four places and wired to nothing.
4. **Remove `|| true` from CI** and add the 5 unrun test files, or the test suite
   is decoration.
5. **Delete `frontend/src/app/dashboard/page.tsx`** (redirect to `/dashboard/storms`)
   and drop `three`/`@react-three/*`/`lenis`.
6. **Update the README's stale numbers** (test count, RAG top-k) — the rest of it
   is genuinely accurate and worth keeping.
7. Add `lightgbm` + `joblib` to a requirements file, or document that ML is
   opt-in and the shipped default is the conservative fallback.
