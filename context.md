# HelioOps — Project Context

> Paste this file into a fresh chat to get the full picture of this repo.
> It is standalone: it covers what the project is, how it works, what the code
> actually does today, and where the docs and the code disagree.
>
> **Regenerated 2026-08-22** from a full read of the repo at commit `2ea377a`.
> The previous revision described the pre-refactor 18-folder tree and is void;
> `REFACTOR_MAP.md` maps the old paths to the current ones.

---

## 1. What this is

**HelioOps** is a space-weather operations platform. It detects a coronal mass ejection (CME)
from coronagraph imagery, predicts what the resulting geomagnetic storm does to four industries,
and generates regulator-cited operational advisories — each one machine-verified against the
authoritative constants before an operator ever sees it.

The claim that distinguishes it from "an LLM over some PDFs" is the **verifier**: a zero-LLM rule
engine downstream of generation that *rewrites* unsafe values and records the correction. The
canonical case is an agent proposing "switch HF to 21 MHz"; 21 is not in the ICAO NAT set
`{3, 5, 8, 11, 17}`, so the verifier rewrites it to 5 MHz, logs a `VerifierCheck`, and streams the
block to the dashboard. The operator sees both the proposal and the enforcement.

**Demo/replay oriented.** Two anchor storms replay deterministically: `2024-10-G4` and
`2024-05-G5`. Live mode exists (`detect_live()`) but the cached path is what the demo runs.

### Team & ownership

| Owner | Layer |
|---|---|
| **Neal** | Layer 1 — CV detection, ML pipeline |
| **Parshva** | Layer 2 — data engineering, impact models |
| **Priyanshu** | Layer 3 — GenAI advisory, backend pipeline, database |
| **Tirth** | Layer 4 — frontend console, DevOps, deployment |

---

## 2. The five-stage pipeline

```
Solar imagery (CCOR-1 / LASCO FITS) + DONKI + GOES XRS + DSCOVR L1
        |
   (1) CV DETECTION        deterministic 9-step threshold detector, no RNG, no weights
        |                  fused with NASA physics -> StormEvent {confidence, G/S/R, kinematics}
        v
   (2) ML IMPACT           6 LightGBM quantile models (q025 / q500 / q975 x 2 targets)
        |                  -> GPS L1 error +/- 95% CI, HF blackout probability +/- 95% CI
        v
   (3) AGENTIC ADVISORY    4 industry agents in parallel, RAG over the real rulebooks
        |                  918 chunks, layered guardrails
        v
   (4) DETERMINISTIC VERIFIER   ICAO HF bands, GMDSS channels, reroute latitudes, NERC GIC
        |                       corrects the value; does not merely flag it
        v
   (5) DELIVERY            FastAPI REST + WebSocket -> React console -> optional Supabase
```

Every advisory carries a **6-step provenance trace**:
`raw_data -> detection -> impact -> retrieval -> verifier -> output`.

**Latency:** `/api/detect` takes **65–80 s** end to end. The `gpt-oss-120b` reasoning pass
dominates; host CPU is nearly irrelevant. Anything in the docs claiming 8–15 s is stale.

### Only two storms exist

`STORM_CONFIGS` in `backend/cv/storm_event_generator/detect.py` defines `2024-10-G4` and
`2024-05-G5`. `validate_storm_id()` enforces `^\d{4}-\d{2}-G[1-5]$` before anything touches a
filesystem or database path, and an ID that passes the regex but is not in `STORM_CONFIGS` 404s.

---

## 3. Repo map

Three folders, plus `.github/` (GitHub Actions requires it at the repo root) and `docs/`.

```
HelioOps/
├── Dockerfile                 <- Hugging Face Spaces builds THIS, not deployment/Dockerfile.backend
├── README.md                  carries HF Spaces front matter — do not delete the --- block
├── AGENTS.md                  project memory: architecture, conventions, gotchas, decisions log
├── backend/                   FastAPI monolith — all four layers, one process
│   ├── app.py                 routes, CORS, middleware, WebSocket manager
│   ├── pipeline.py            5-stage orchestration; owns the adapter singletons
│   ├── paths.py               BACKEND_DIR / DATA_DIR / CHROMA_DIR / STUBS_DIR / CHECKPOINT_DIR / ML_DATA_DIR
│   ├── health.py              /health, /health/live, /health/ready, /metrics
│   ├── preflight.py           read-only pre-run conflict check (GET /api/preflight/{id})
│   ├── middleware.py          security headers, request IDs, rate limit, input validation
│   ├── config.py              Pydantic BaseSettings, HELIOOPS_ env prefix
│   ├── __init__.py            loads .env for EVERY entry point; sets LOKY_MAX_CPU_COUNT
│   ├── adapters/              the seam: detection / prediction / advisory / repository / schema
│   ├── cv/                    data_ingestion, image_threshold_algorithm, storm_event_generator, stubs
│   ├── ml/                    01_ 02_ 03_ scripts + inference.py + checkpoints/ (6 pkl, 527 KB)
│   ├── genai/                 agents/, prompts/, orchestrator, retriever, guardrails, verifier, llm
│   ├── embeddings/            chunker, embedder, collections, 5 ingest CLIs, retrieval
│   ├── data/                  aviation/ grid/ maritime/ telecom/ impact_matrix/ cached/ chroma_db/
│   └── tests/                 271 tests across 11 modules + conftest + fixtures
├── deployment/                Dockerfile.backend, Dockerfile.frontend, docker-compose.yml, supabase/
├── frontend/                  Vite + React 18 SPA (marketing pages + live console)
└── docs/                      PRODUCT_BRIEF, TECHNICAL_DEEP_DIVE, CV_ML_QNA, qna, DEPLOYMENT, HOW_TO_DEPLOY_BACKEND
```

**Stale directories in a working copy.** A local clone that predates the refactor may still hold
empty `cv/`, `ml/`, `genai/`, `embeddings/`, `tests/`, `data/`, `k8s/`, `infra/`, `argocd/`,
`chaos/`, `runbooks/`, `ML_after_CV/`, `backend/ports/` and `frontend/__tests__/` directories
containing nothing but `__pycache__`. None of them are tracked. They are leftovers, not code.

---

## 4. Backend (`backend/`)

### Routes

| Method | Path | Notes |
|---|---|---|
| POST | `/api/detect/{storm_id}` | all 5 stages; validated + rate-limited (1 run per storm per 30 s) |
| GET | `/api/preflight/{storm_id}` | read-only dry run — predicted fallbacks, cross-source conflicts, quota state |
| GET | `/api/storms` | available storms + summary of completed runs |
| GET | `/api/advisory/{advisory_id}` | verified advisory + provenance trace |
| GET | `/api/result/{storm_id}` | complete stored pipeline result |
| WS | `/ws/stream` | live event stream |
| GET | `/health`, `/health/live`, `/health/ready` | three tiers |
| GET | `/metrics` | Prometheus text exposition |

### WebSocket protocol

Client sends `{"action": "run_pipeline", "storm_id": "..."}`. Server streams:

```
pipeline.stage -> agent.thinking -> advisory.generated -> verifier.check -> pipeline.complete
                                            (agent.error | error)
```

The same validation gates apply as on REST — a socket is a trust boundary too. Origin is checked
against `CORS_ORIGINS` **before the handshake completes**; a mismatch closes with code `4003`,
which looks like a backend fault rather than a CORS error if you are not expecting it.

### Adapters — the seam

`backend/pipeline.py` never imports `backend.cv…`, `backend.ml` or `backend.genai` directly. It
constructs four adapter instances at module level; `app.py` imports **those same instances**, so
there is exactly one of each in the process.

The abstract `ports/` package was **deleted on 2026-08-21**. One interface per implementation is
ceremony, not decoupling. The property that matters — the core never imports a layer — is enforced
by `TestNoCircularImports`, not by inheritance.

`backend/adapters/schema_adapter.py` is the anti-corruption layer between
`cv.storm_event_generator.fusion.StormEvent` and `genai.models.StormEvent`. The two layers were
built by different people with different schemas and neither was rewritten; the integration cost is
paid once, in one file.

### Pre-flight (`backend/preflight.py`)

`GET /api/preflight/{storm_id}` is a **read-only dry run**: it predicts which fallbacks the run
will hit (stub replay, missing DONKI/flare/L1/alert caches), runs four cross-source physics
conflict rules using the *same parsers the real run uses*, and reports health, rate-limit and
Groq TPM state. Returns `{storm_id, ready, estimated_duration_s, findings[]}` with severities
`block` / `warn` / `info`.

Three invariants, each of which exists because breaking it is easy and silent:

- **Never fetches, never writes, never mkdirs.** Cache files are `stat`-ed *before* any parser
  runs, because the ingestion clients are cache-first-then-network and mkdir on entry.
- **Uses `peek_rate_limit()`, not `check_rate_limit()`** — the latter records the call, so
  checking whether you may run would consume the run slot.
- **Never probes the Groq API.** Headroom is this process's own TPM accounting; probing would
  spend the quota the check protects.

The Dashboard routes every Run through it: preflight -> confirm panel (summary pills +
`<details>` findings) -> `Run` / `Run anyway` / `Cancel`. It never hard-blocks, and if preflight
itself fails the run starts directly.

### Health checks

```python
health_collector.register("detection",      _check_detection)       # STORM_CONFIGS non-empty
health_collector.register("ml_models",      _check_ml)              # all 6 checkpoints load
health_collector.register("genai_module",   _check_genai)           # genai.impact_router importable
health_collector.register("knowledge_base", _check_knowledge_base)  # every KB holds chunks
```

`knowledge_base` exists because `genai_module` is an *import probe* that returns `True` against a
completely empty database, and `retrieve_chunks()` swallows storage errors and returns `[]`. Without
a chunk count there is no automatic signal anywhere in the system that RAG is dead.

### Result storage

`HELIOOPS_RESULT_REPOSITORY` picks `memory` (default) or `supabase`. In-memory means results are
lost on restart — fine for a demo, wrong for a deployment.

---

## 5. Frontend (`frontend/`)

**Vite + React 18 SPA.** Replaced the Next.js 14 App Router app on 2026-08-21. Runtime dependencies
in full: `react`, `react-dom`, `three@0.134`. No TypeScript, no Tailwind, no eslint config, no
router library.

```
frontend/src/
├── main.jsx  router.jsx  PageShell.jsx  Nav.jsx  Loader.jsx
├── Home.jsx  Problem.jsx  Industries.jsx  About.jsx   marketing pages (copy lives in data.js)
├── Dashboard.jsx                                      the live console
├── api.js            getHealth/getStorms/getResult/getAdvisory/runPipeline/streamPipeline
├── helio-globe.js    raw three.js, no react-three wrapper
├── data.js           all static copy in one module
└── data.test.mjs     what `npm test` runs
```

`router.jsx` is ~50 lines: `pushState`, a `popstate` listener, one anchor-scroll effect, and a
`<Link>` that defers to the browser on meta/ctrl/shift/alt-click.

**The API base is `VITE_API_URL`** — NOT the Next-era `NEXT_PUBLIC_API_URL`, which nothing reads.
Vite inlines it at **build** time, so a runtime environment variable does nothing. Empty default =
relative paths, which is correct for the dev proxy and for single-origin deploys, and **wrong on
Vercel**, where the catch-all rewrite answers `/api/*` with `index.html` and a 200, so every call
dies inside `res.json()`.

`vite.config.js` proxies `/api`, `/health`, `/metrics` to `http://127.0.0.1:8000` and `/ws` to
`ws://127.0.0.1:8000`, so local dev needs no configuration at all.

> **Port note:** vite binds IPv6 only. `http://localhost:3000` works; `http://127.0.0.1:3000` gets
> connection-refused. If 3000 is occupied vite silently moves to 3001 and prints it.

---

## 6. ⚠ What is missing on a fresh clone

| Missing | Effect | Fix |
|---|---|---|
| **Cached FITS / PNGs** | gitignored (too large). `detect()` silently falls back to `backend/cv/stubs/*.json` | run `cache_fits` then `preprocessing` |
| **`.env`** | no `GROQ_API_KEY`; every advisory becomes `ESCALATE TO SPECIALIST` | `cp .env.example .env`, set the key |
| **AWS CLI** | `cache_fits.sync_ccor1` shells out to `aws s3 sync --no-sign-request`; it is not a pip dependency | install the AWS CLI, or skip CCOR-1 |

**Committed and present:** the 6 ML checkpoints, the ChromaDB store (918 chunks, ~20 MB), the
synthetic training set, and the CV stub events. None of those need regenerating to serve.

### Other landmines

- **Windows console is cp1252.** `→` or `—` in argparse help or `print()` raises
  `UnicodeEncodeError`. Logging survives (it substitutes); argparse does not. Keep CLI strings ASCII.
- **`HELIOOPS_CHROMA_PERSIST_PATH` relative values resolve against the REPO ROOT.** They used to
  resolve against `backend/`, turning the shipped `backend/data/chroma_db` into
  `backend/backend/data/chroma_db` — a path Chroma happily *creates*. Every KB read 0,
  `retrieve_chunks()` swallowed it, every advisory was ungrounded, nothing was logged. Pinned by
  `test_runtime_paths.py`.
- **Two `chromadb.PersistentClient` instances on one directory** produce
  `Error executing plan: Internal error` under concurrent access. `genai/retriever.py` and
  `embeddings/` share one via `collections.get_client()`.
- **`genai` reads `GROQ_API_KEY` from `os.getenv`**, not `settings.GROQ_API_KEY`. Settings uses the
  `HELIOOPS_` prefix, so that field is always empty and its "not set" warning is spurious.
- **The advisory field is `sources_cited`, not `citations`.** Any RAG-liveness check grepping for
  `citations` reports a false failure.
- **`backend/ml/0*.py` must keep the numeric prefix** — `.dockerignore` excludes the training
  scripts by that glob. Renaming them silently ships training code in the serving image.
- **`python:3.12-slim` has no `curl`** — container healthchecks must use python or node.
- **joblib shells out to `wmic`** to count physical cores; Windows 11 build 26xxx does not ship it,
  so every ML run dumped a subprocess traceback. `backend/__init__.py` sets `LOKY_MAX_CPU_COUNT` to
  logical//2 — it must be **strictly below** `os.cpu_count()` or loky still probes.
- **`_pick_key()` in `genai/llm.py` waits in an unbounded `while True`.** Neither the per-call
  timeout nor `GROQ_MAX_RETRIES` bounds it. With every key parked, `/api/detect` and `/ws/stream`
  stall for minutes with no error and no client-side timeout either.
- **Nothing under `backend/adapters/` may import `backend.pipeline` at module level** — it closes an
  import loop and makes `import backend.pipeline` fail on its own, invisibly under the full suite.
- **`check_rate_limit()` mutates on read** — it records the call. Anything read-only (preflight, a
  status probe) must use `peek_rate_limit()` instead, or merely *looking* consumes the slot.
- **`/health/ready` answers 503 with the same body shape as 200** when degraded. `getHealth()` in
  the frontend parses unconditionally; routing it through the throwing `json()` helper made every
  degraded state render as "unreachable" with no check pills.
- **Preflight must stat before it parses.** The ingestion clients are cache-first-then-*network*
  and mkdir on entry, so calling a parser to "just check" would fetch and write. Pinned by a
  no-mkdir/no-fetch test.

---

## 7. Running it

Everything runs from the repo root with `PYTHONPATH=.`.

```bash
pip install -r backend/requirements-dev.txt    # requirements.txt alone = serving only
cp .env.example .env                           # set GROQ_API_KEY
PYTHONPATH=. uvicorn backend.app:app --reload  # API on :8000

cd frontend && npm ci && npm run dev           # console on :3000, proxied to :8000
```

Containers:

```bash
docker compose -f deployment/docker-compose.yml up --build
```

Tests and gates:

```bash
PYTHONPATH=. pytest backend/tests -q                      # 271 tests
PYTHONPATH=. ruff check backend/ --ignore=E501,F403,E402
PYTHONPATH=. python backend/ml/03_anchor_test.py          # exits non-zero on failure
cd frontend && npm test
```

Offline pipelines — **not needed to serve**; their output is committed:

```bash
PYTHONPATH=. python -m backend.cv.data_ingestion.cache_fits --storm 2024-10-G4
PYTHONPATH=. python -m backend.cv.data_ingestion.donki_client --prefetch --storm 2024-10-G4
PYTHONPATH=. python -m backend.cv.image_threshold_algorithm.preprocessing --storm 2024-10-G4
PYTHONPATH=. python -m backend.cv.storm_event_generator.detect --storm 2024-10-G4
PYTHONPATH=. python -m backend.embeddings.ingest_aviation      # + grid / maritime / telecom / impact_matrix
PYTHONPATH=. python backend/ml/01_data_generation_eda.py
PYTHONPATH=. python backend/ml/02_train_and_tune.py
PYTHONPATH=. python backend/ml/03_anchor_test.py
```

> All five ingest CLIs default their cache paths to `BACKEND_DIR`, not the CWD. They used to default
> to the CWD while `detect()` resolved from `backend.paths`, so the documented repo-root commands
> wrote FITS/JSON where the detector never looked and detection degraded to the stub forever.

---

## 8. CI and deployment

### CI (`.github/workflows/ci.yml`)

Three jobs: `backend` (ruff + pytest), `frontend` (`npm ci`, `npm test`, `npm run build`), and
`images` (Buildx over all three Dockerfiles, `push: false`).

- **The `|| true` escape hatch is gone.** Both gates block now.
- **No frontend lint/typecheck**, deliberately: no eslint config, no tsconfig, no typescript
  dependency. The old job ran `npm run lint` and `npx tsc --noEmit`, carried over from the deleted
  Next.js app, so it could only ever fail.
- **`test_api_endpoints.py::test_valid_storm_id_returns_200_or_500_or_429` hits the real Groq API** —
  the only live-network test in the suite. Free quota: ~45 s for the whole suite. Saturated keys or
  CI's placeholder `GROQ_API_KEY`: 9–12 minutes.

### The Kubernetes stack is gone

`k8s/`, `infra/` (Terraform, EKS), `argocd/`, `chaos/` (Chaos Mesh) and `runbooks/` were deleted on
2026-08-21. A Kubernetes platform for two containers was the single largest cost item in the project
and it contradicts the scale-to-zero target. Also dropped, same reasoning: `agentscope`,
`langchain-core`, `langchain-groq`, `redis`, `fakeredis`.

### Deployment

| Target | Status |
|---|---|
| Frontend → Vercel | 🟢 live — `frontend-olive-six-50.vercel.app` |
| Backend → Hugging Face Spaces | 🟡 build-ready (root `Dockerfile`, CPU basic, port 7860) |

**HF Spaces builds the repo-root `Dockerfile`.** `deployment/Dockerfile.backend` is never picked up
there; the two are kept in step by hand. Two lines in that file are load-bearing and neither is
style: `COPY --chown=user` (ChromaDB opens `chroma.sqlite3` read-write for the sqlite WAL) and
baking the embedder **after** `USER user` (as root it caches to `/root/.cache`, which UID 1000
cannot read, costing a silent ~90 s re-download on the first request).

### Supabase (optional)

`deployment/supabase/` holds `001_schema.sql` (4 enums, 8 tables, DB-level CHECK constraints),
`002_rls.sql` and `003_seed.sql`. Set `HELIOOPS_RESULT_REPOSITORY=supabase` to use it.

---

## 9. Docs vs. reality

| Doc | Status |
|---|---|
| `README.md` | ✅ current (rewritten 2026-08-22) — keep the HF front matter block |
| `AGENTS.md` | ✅ current — the authoritative project memory |
| `docs/PRODUCT_BRIEF.md` | ✅ current |
| `docs/TECHNICAL_DEEP_DIVE.md` | ✅ current |
| `docs/CV_ML_QNA.md` | ✅ current — judge-facing CV+ML Q&A |
| `docs/qna.md` | ✅ current — pitch Q&A |
| `docs/DEPLOYMENT.md` · `docs/HOW_TO_DEPLOY_BACKEND.md` | ✅ current |
| `REFACTOR_MAP.md` | 📌 **historical** — a record of the 2026-08-21 collapse, not a description of today |
| `HELIOOPS_TEST_REPORT.md` | 📌 **historical** — a dated snapshot; its verdict and blocker list are resolved |

---

## 10. Domain reference (for reading the code)

| Term | Meaning |
|---|---|
| **CME** | Coronal mass ejection — a blob of magnetised plasma thrown off the Sun |
| **Coronagraph** | Instrument that occults the solar disk so the faint corona is visible (CCOR-1, LASCO) |
| **G / S / R scales** | NOAA severity scales: G = geomagnetic, S = solar radiation, R = radio blackout, each 1–5 |
| **Kp index** | Planetary geomagnetic activity, 0–9. `G4 ≈ Kp 8.3`, `G5 ≈ Kp 9` |
| **Bz** | North–south component of the interplanetary magnetic field. **Southward (negative) is what couples energy into the magnetosphere** |
| **L1** | Lagrange point 1, ~1.5 M km sunward. DSCOVR sits there and buys 15–60 min of warning |
| **DONKI** | NASA's human-reviewed database of CME analyses (speed, angular width, direction) |
| **GOES XRS** | X-ray sensor that sets the flare class (C/M/X) and therefore the R scale |
| **R☉** | Solar radius, 695,700 km — the standard length unit in coronagraph work |
| **GIC** | Geomagnetically induced current — what heats grid transformers |
| **GMDSS** | Global Maritime Distress and Safety System — the maritime rulebook |
| **ICAO NAT Doc 007** | North Atlantic operations manual; source of the HF band set `{3, 5, 8, 11, 17}` MHz |
| **NERC TPL-007-4** | The GMD planning standard for the North American grid |
| **PICP** | Prediction Interval Coverage Probability — fraction of truths inside the interval |
| **PINAW** | Prediction Interval Normalised Average Width — the *cost* of that coverage |
| **Pinball loss** | The correct objective for quantile regression |

**Measured ML calibration:** PICP **95.90%** GPS / **94.21%** HF against a nominal 95%, at PINAW
0.0369 / 0.1941. R²/MAE are deliberately not quoted — the models are fit to synthetic rows generated
from hand-written rules, so those metrics measure rule-recovery, not forecast skill.

**Knowledge base:** 918 chunks — aviation 242, maritime 214, telecom 195, impact_matrix 166,
grid 101. Embedded with BGE-small (384-dim, CPU).

---

## 11. If you're picking this up

1. **Read `AGENTS.md` first.** It is the project memory: conventions, gotchas and the decisions log
   with the *reasoning*, not just the outcome.
2. **Never hardcode a runtime path** — import it from `backend.paths`.
3. **One Groq call site**: `backend.genai.llm.complete_json`. Do not add an LLM client.
4. **CV imports use the full stage path**: `from backend.cv.storm_event_generator.detect import detect`.
   There are no re-export shims; the stage package docstrings are the map.
5. **Fallbacks log at WARNING and continue.** Only genuinely unrecoverable input raises. Every
   external client is cache-first: hit → disk, miss → fetch + write, network failure → stale cache →
   hardcoded fallback dict.
6. **Known flake:** `test_retrieval.py` fails ~1 full-suite run in 3 with a chromadb segment-reader
   `InternalError`. It passes standalone (11/11) and KB counts stay correct. Pre-existing chromadb
   bug, mitigated by a retry in `collections.py`, not fixed. Do not go hunting for it in the CV or
   RAG code — it is not there.
