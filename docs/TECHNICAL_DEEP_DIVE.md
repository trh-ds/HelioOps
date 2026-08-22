# HelioOps — Technical Deep Dive

How each engineering domain is actually implemented in this repository, with file references.
Companion to [`PRODUCT_BRIEF.md`](./PRODUCT_BRIEF.md).

All four domains are present:

| Domain | Status | Where |
|---|---|---|
| 1. Full stack | ✅ | `backend/`, `frontend/`, `deployment/supabase/` |
| 2. DevOps | ✅ | `Dockerfile` (repo root), `deployment/`, `.github/workflows/` |
| 3. ML | ✅ | `backend/cv/` (computer vision), `backend/ml/` (impact regression) |
| 4. Agentic AI | ✅ | `backend/genai/`, `backend/embeddings/` |

> **Repo shape.** As of 2026-08-21 the tree is three folders — `backend/`, `deployment/`,
> `frontend/`. Every layer that used to be a top-level package (`cv/`, `ml/` ex-`ML_after_CV/`,
> `genai/`, `embeddings/`, `data/`, `tests/`) is now a `backend` subpackage. The Kubernetes /
> Terraform / ArgoCD / Chaos Mesh platform stack was deleted outright — see §2.7. File paths below
> are the current ones; `REFACTOR_MAP.md` maps old → new.

---

# 1. Full Stack

## 1.1 Backend — FastAPI with a hexagonal core

`backend/app.py` is deliberately thin. The interesting decision is that the pipeline does not import
`backend.cv…detect` or `backend.ml.inference` directly. It talks to **adapters**, which own every
call into a domain layer.

> **The abstract `ports/` package was deleted on 2026-08-21.** One interface per implementation is
> ceremony, not decoupling: the adapters already were the seam, and the ABCs above them only added a
> file to edit whenever a signature changed. The hexagonal property that matters — *the core never
> imports a layer* — is enforced by `TestNoCircularImports` and by the adapters being the only
> import site, not by an inheritance relationship.

```
backend/
├── adapters/                 the seam — every call into a domain layer goes through here
│   ├── detection_adapter.py     → wraps backend.cv.storm_event_generator.detect
│   ├── prediction_adapter.py    → wraps backend.ml.inference
│   ├── advisory_adapter.py      → wraps backend.genai.run_pipeline + verifier
│   ├── repository_adapter.py    → InMemoryResultRepository | SupabaseResultRepository
│   └── schema_adapter.py        → anti-corruption layer between layer schemas
├── pipeline.py               run_full_pipeline() / stream_full_pipeline(); owns the adapter singletons
├── app.py                    routes, CORS, middleware, WebSocket manager
├── health.py                 /health, /health/ready, /health/live, /metrics
├── middleware.py             security headers, request IDs, rate limit, input validation
├── config.py                 Pydantic BaseSettings — every knob from env
├── paths.py                  BACKEND_DIR / DATA_DIR / CHROMA_DIR / STUBS_DIR / CHECKPOINT_DIR
└── logging.py                structlog JSON setup
```

**Why adapters here specifically.** Storage swaps at runtime with zero pipeline changes —
`_build_result_repository()` in `app.py` reads `settings.RESULT_REPOSITORY` and returns either the
in-memory dict store or the Supabase-backed one. Same call sites. The same pattern makes the ML layer
mockable in tests without touching real checkpoints.

**There is exactly one of each adapter in the process.** `backend/pipeline.py` constructs
`detection_adapter`, `prediction_adapter`, `advisory_adapter` and `verification_adapter` at module
level, and `app.py` imports those same instances rather than building its own. Consequence worth
knowing: nothing under `backend/adapters/` may import `backend.pipeline` at module level — that closes
an import loop and makes `import backend.pipeline` fail on its own, invisibly under the full suite,
which imports something else first. Annotate with a string and import inside the function. Pinned by
`TestNoCircularImports`.

**The anti-corruption layer is the load-bearing part.** The CV layer and the GenAI layer were built
by different people with different schemas, and neither was rewritten to accommodate the other.
`backend/adapters/schema_adapter.py` translates between them:

| `cv.storm_event_generator.fusion.StormEvent` | `genai.models.StormEvent` | Transform |
|---|---|---|
| `storm_id` | `alert_id` | direct |
| `scales["G"]` (int) | `g_scale` (GScale enum) | `GScale(f"G{v}")`, clamped to `[1,5]` |
| `scales["S"]` / `["R"]` | `s_scale` / `r_scale` (str \| None) | `"S{v}"` if `> 0`, else `None` |
| derived from G | `kp_index` (float) | parsed from alert text, else `G→Kp` map |
| `cme["arrival_estimate"]` | `estimated_arrival_utc` | ISO 8601 parse |
| `noaa_alert_raw` | `raw_alert_text` | direct |

This is the "bridge, don't rewrite" principle: integration cost is paid once in one file, instead of
being smeared across four modules owned by four people.

## 1.2 API surface

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/detect/{storm_id}` | Runs all 5 stages. Validated + rate-limited. |
| GET | `/api/preflight/{storm_id}` | Read-only dry run of that same call — see §1.7 |
| GET | `/api/storms` | Available storms + summary of completed runs |
| GET | `/api/advisory/{advisory_id}` | Verified advisory + full provenance trace |
| GET | `/api/result/{storm_id}` | Complete stored pipeline result |
| WS | `/ws/stream` | Live pipeline event stream |
| GET | `/health` · `/health/ready` · `/health/live` | Three-tier health, see §2.3 |
| GET | `/metrics` | Prometheus text exposition format |

## 1.3 Real-time streaming

The WebSocket handler (`app.py:243`) accepts `{"action": "run_pipeline", "storm_id": "..."}` and then
iterates an async generator, forwarding each event as it is produced:

```python
async for event in stream_full_pipeline(storm_id):
    await _ws_manager.send(ws, event)
streamed_result = get_result(storm_id)
if streamed_result:
    _persist_result(streamed_result)     # persist after streaming, errors surfaced to client
```

The event vocabulary is stable and typed on both ends: `pipeline.stage`, `agent.thinking`,
`advisory.generated`, `verifier.check`, `pipeline.complete`, `agent.error`, `error`.

The same validation gates apply on the WebSocket path as on REST — format check, existence check,
rate limit — because a socket is a trust boundary too. Origin is checked against `CORS_ORIGINS`
before the handshake completes; a mismatch closes with code `4003`.

## 1.4 Security at the boundary

`backend/middleware.py` is small and does four specific jobs:

- **`SecurityHeadersMiddleware`** — sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `Content-Security-Policy: default-src 'self'`, and HSTS with a one-year max-age
  on every response.
- **`RequestIDMiddleware`** — stamps `X-Request-ID` on request state and response headers, so a
  structured log line can be tied to a specific client call.
- **`check_rate_limit()`** — one pipeline run per storm per 30 s. The pipeline is expensive (multiple
  LLM calls fanned out four ways); this stops a refresh loop from exhausting the Groq quota.
- **`validate_storm_id()`** — `^\d{4}-\d{2}-G[1-5]$`. An allowlist-shaped regex, applied before the
  ID reaches any filesystem or database path.

CORS is explicitly scoped: origins from settings, methods restricted to `GET`/`POST`, headers to
`Content-Type`/`Authorization`. `backend/tests/test_security.py` holds 23 tests over exactly these paths.

## 1.5 Frontend — Vite + React 18 SPA

> **Replaced the Next.js 14 App Router app on 2026-08-21** (`f21e277`). The Next build existed to
> serve a static marketing site plus one live console; App Router, TypeScript, Tailwind, framer-motion,
> GSAP, lenis, `@react-three/fiber` and `drei` were all paying a bundle and toolchain cost for
> behaviour a 50-line `pushState` router and raw `three` cover. Dependency count went from dozens to
> **three runtime packages**.

```
frontend/
├── index.html
├── vite.config.js            dev proxy: /api /health /metrics -> :8000, /ws -> ws://:8000
├── vercel.json               SPA catch-all rewrite
└── src/
    ├── main.jsx              mount
    ├── router.jsx            pushState + popstate + <Link> — no routing library
    ├── PageShell.jsx  Nav.jsx  Loader.jsx
    ├── Home.jsx              landing; three.js globe (helio-globe.js)
    ├── Problem.jsx  Industries.jsx  About.jsx     marketing copy, sourced from data.js
    ├── Dashboard.jsx         the live console — drives api.js
    ├── data.js               all static copy in one module
    ├── data.test.mjs         the contract test CI runs (`npm test`)
    ├── helio-globe.js        raw three.js, no react-three wrapper
    └── *.css                 one stylesheet per surface, no CSS framework
```

**Runtime dependencies, in full:** `react`, `react-dom`, `three@0.134`. Dev: `vite`,
`@vitejs/plugin-react`. There is no TypeScript, no eslint config and no Tailwind — which is why the
CI frontend job runs `npm test` and `npm run build` and nothing else (§2.2).

**Routing is 50 lines** (`router.jsx`). A four-page static site does not need a routing library:
`pushState`, a `popstate` listener and one anchor-scroll effect cover every navigation this app can
perform. `<Link>` defers to the browser on meta/ctrl/shift/alt-click so new-tab still works.

**API client (`src/api.js`).** Paths are **relative by default**, so the vite dev proxy forwards them
to uvicorn on :8000 and a single-origin deployment (one container serving both) needs no
configuration at all. Every path parameter is `encodeURIComponent`-wrapped. Failures parse the body
for `detail` and fall back to `statusText` — server stack traces never reach the user.

> ⚠️ **The split-deployment trap, and why the code carries a comment about it.** With the SPA on
> Vercel and the API on a Space, there is no backend at the SPA's origin — and `vercel.json` rewrites
> `/(.*)` to `/index.html`. So `fetch('/api/storms')` returns **the HTML shell with a 200**, and every
> call dies inside `res.json()` with a parse error that looks nothing like a routing bug. The fix is
> `VITE_API_URL` set to the API origin **at build time** — vite inlines `import.meta.env`, so a
> runtime environment variable does nothing — plus the SPA origin in the backend's `CORS_ORIGINS`.

**WebSocket (`streamPipeline`).** Derives its origin from the same `BASE` constant with a single
`^http → ws` regex, so there is exactly one place to configure the backend address. Malformed JSON is
dropped rather than thrown — one bad frame must not kill the stream. `pipeline.complete` fires the
caller's `onClose` while leaving the socket open, so a second run reuses it. The function returns a
close handle guarded on `readyState <= 1`.

**Failure containment.** The console renders detection and impact data even when advisory generation
fails — which is exactly the Groq-outage scenario: the backend still serves stages ① and ②, and the
UI is built not to blank on the absence of stage ③.

## 1.6 Data layer — Supabase Postgres

`deployment/supabase/001_schema.sql` defines 4 enums and 8 tables; `002_rls.sql` adds Row Level Security;
`003_seed.sql` loads the two demo storms.

| Table | Source of truth |
|---|---|
| `storm_events` | `backend/cv/storm_event_generator/fusion.py` → `StormEvent` |
| `impact_predictions` | `backend/ml/inference.py` → `ImpactPrediction` |
| `advisories` | `backend/genai/models.py` → `AdvisoryOutput` |
| `action_items` | `backend/genai/models.py` → `ActionItem` |
| `verified_advisories` | `backend/genai/contracts.py` → `VerifiedAdvisory` |
| `verifier_checks` | individual rule outcomes (pass / blocked) |
| `provenance_traces` | 6-step audit chain per advisory |
| `pipeline_runs` | denormalized execution summary |

The schema enforces domain invariants **in the database**, not only in application code:

```sql
confidence        REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
g_scale           SMALLINT NOT NULL CHECK (g_scale BETWEEN 0 AND 5),
hf_blackout_prob  REAL NOT NULL CHECK (hf_blackout_prob BETWEEN 0 AND 1),
UNIQUE (advisory_id, step)                       -- action step numbers cannot collide
REFERENCES storm_events(storm_id) ON DELETE CASCADE
```

Irregularly-shaped physics payloads (`cme`, `flare`, `l1_solar_wind`, `timeline`, `scales`) are
`JSONB` — they are read as whole documents, and forcing them into columns would buy nothing.
The values that are queried, constrained or joined on are real typed columns.

---

## 1.7 Pre-flight — the read-only dry run

`backend/preflight.py` (~300 lines) answers, without running anything: **which fallbacks will this
run hit, which cached sources physically disagree, and is the quota going to stall me?** Served by
`GET /api/preflight/{storm_id}`.

The motivation is specific to this pipeline. A run takes 65–80 s, and a run that quietly replayed a
stub because the FITS cache was missing produces a response *shaped identically* to a real one. The
degradation is designed in (§3.1) but it is invisible at the API boundary, which is exactly the
property that makes it dangerous in a demo.

### Response shape

```json
{
  "storm_id": "2024-10-G4",
  "ready": true,
  "estimated_duration_s": 70,
  "findings": [
    { "id": "cv_stub_replay", "severity": "warn", "title": "...", "detail": "..." }
  ]
}
```

`ready` is false only when a `block`-severity finding is present — today that is the rate limiter
alone. Severities are `block` / `warn` / `info`. `estimated_duration_s` is the running mean of
observed `pipeline_duration_seconds` from the metrics collector, falling back to 70 s.

### The four cross-source conflict rules

These run the **same parsers the real pipeline uses**, so a rule cannot pass preflight and then be
contradicted by the run. They catch data that is individually well-formed and jointly impossible:

| Rule | Condition | Why it is a conflict |
|---|---|---|
| `speed_disagreement` | L1 speed > 1.10 × CME launch speed | Arriving faster than launch is unphysical — one source is wrong |
| `speed_disagreement` | L1 speed < 0.30 × launch speed | Exceeds plausible drag-model deceleration; the sources may describe different events |
| `arrival_eta_mismatch` | \|DONKI arrival − L1 ETA\| > 12 h | Ballistic estimates carry ~10 h MAE; beyond 12 h the disagreement is real, not noise |
| `bz_northward_strong_g` | Cached Bz ≥ 0 while stub G ≥ 3 | Northward IMF does not drive strong geomagnetic storms, and `fuse()` will drop its Bz confidence term |
| `flare_r_mismatch` | Stub R ≥ 2 but GOES classifies R0 | The radio-blackout severity is unsupported by the flux record (`warn`) |
| `flare_r_mismatch` | \|stub R − flare R\| ≥ 2 | Two or more R-levels from the reference severity (`info`) |

### Three constraints that make it trustworthy rather than decorative

**1. Strictly read-only — and that is harder than it sounds.** Every cache file is `stat`-ed
*before* any parser touches it, because the ingestion clients (`donki_client`, `flare_classifier`,
`l1_client`) are cache-first-then-**network** and `mkdir` their cache directory on entry. Calling a
parser to "just check whether the data is there" would fetch and write. The module docstring states
the rule as a hard invariant and `test_preflight.py` pins it with a no-mkdir/no-fetch test.

**2. It does not consume the resource it reports on.** Two separate cases:

- `check_rate_limit()` **mutates on read** — it records the call. Preflight therefore uses a new
  non-mutating `peek_rate_limit()` in `middleware.py`, which returns seconds-until-allowed without
  recording. Without it, *checking* whether you may run would consume the run slot.
- Groq headroom is computed from **this process's own TPM accounting**, never by probing the Groq
  API — a probe would spend exactly the quota the check exists to protect. That makes it a soft
  signal, and the finding says so: other clients on the same key are invisible to it.

**3. It never hard-blocks.** Findings are advisory. The UI offers **Run anyway** even on a `block`,
and if preflight itself raises, the run starts directly. A diagnostic that can break the thing it
diagnoses is worse than no diagnostic.

### The UI gate

`Dashboard.jsx` routes **every** Run through the gate: `preflight → confirmation panel → start`. The
panel is progressive disclosure — a one-line summary with severity pills and the estimated duration,
findings collapsed behind `<details>`, and `Run` / `Run anyway` / `Cancel`. The button label itself
carries the signal: it reads `Run` when nothing serious surfaced and `Run anyway` when something did.

Shipped alongside it, a pre-existing bug fix worth noting because it is the same class of error as
the `knowledge_base` check (§2.3): **`/health/ready` answers 503 with the same body shape as 200**
when degraded. The frontend's `getHealth()` was routed through the throwing `json()` helper, so every
degraded state rendered as "unreachable" with no per-check pills — the health page hid exactly the
information it existed to show. It now parses unconditionally.

---

# 2. DevOps

The chain that is actually in the repo: **Docker → CI → observability → deployment.** A previous
revision carried a full Kubernetes platform stack; §2.7 says what happened to it and why.

## 2.1 Containers

There are **three** Dockerfiles, and knowing which is which matters:

| File | Built by | Serves |
|---|---|---|
| `Dockerfile` *(repo root)* | **Hugging Face Spaces**, and CI | the deployed backend, port 7860 |
| `deployment/Dockerfile.backend` | `docker compose`, and CI | local full-stack backend, port 8000 |
| `deployment/Dockerfile.frontend` | `docker compose`, and CI | local full-stack SPA, port 3000 |

> ⚠️ **HF Spaces builds the repo-root `Dockerfile` and nothing else** — different name, different
> path, so `deployment/Dockerfile.backend` is never picked up there. The two are kept in step by hand.
> Both are in the CI image matrix precisely so the deployed one is not the only untested image.

The root Dockerfile is short, and three of its lines are load-bearing in ways that are not obvious:

```dockerfile
FROM python:3.12-slim
RUN useradd -m -u 1000 user          # Spaces runs the container as UID 1000
USER user

COPY --chown=user backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --chown=user is load-bearing, not style: ChromaDB opens chroma.sqlite3
# read-write (sqlite WAL). Without it UID 1000 cannot write the WAL, Chroma
# raises, retrieve_chunks() swallows it, and every advisory is silently ungrounded.
COPY --chown=user backend/ backend/

# Bake the embedder AFTER `USER user`. As root it caches to /root/.cache, which
# UID 1000 cannot read at runtime -> a silent ~90s re-download on first request.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
```

Both failure modes above are **silent** — the container starts, answers `/health/live`, and serves
ungrounded advisories or eats a 90-second cold start. `/health/ready`'s `knowledge_base` check
(§2.3) is what turns the first one into a visible 503.

Only `backend/requirements.txt` is installed — the dev set (pytest, ruff, sunpy, optuna, matplotlib,
pdfplumber) never reaches the image. `.dockerignore` excludes the training scripts by the
`backend/ml/0*.py` glob, which is why **those files must keep their numeric prefix**: renaming them
silently ships training code in a serving image.

`deployment/docker-compose.yml` wires both services for local development, with two details that
matter:

```yaml
frontend:
  build:
    args:
      VITE_API_URL: http://localhost:8000   # build arg, NOT a runtime env var — vite inlines it
  depends_on:
    backend:
      condition: service_healthy            # not merely "started"
```

The frontend waits for the backend's *health check* to pass, not just for its process to exist —
avoiding the classic race where the UI boots against an API still loading ML checkpoints. And
`VITE_API_URL` is a **build arg** because vite inlines `import.meta.env` at build time; passing it as
an environment variable does nothing at all. (`NEXT_PUBLIC_API_URL` was the Next-era name and nothing
has read it since the SPA rewrite.)

> **Note for anyone editing a healthcheck:** `python:3.12-slim` ships **no `curl`**. Container
> healthchecks must shell out to python (or node, on the frontend image) instead.

## 2.2 CI — GitHub Actions

`.github/workflows/ci.yml`, on push and PR to `main`, three jobs:

```
backend  ─┐
          ├─► images   (needs: backend, frontend)
frontend ─┘
```

- **backend** — `pip install -r backend/requirements-dev.txt`, then
  `ruff check backend/ --ignore=E501,F403,E402` and `pytest backend/tests -q` with
  `GROQ_API_KEY: test-key`.
- **frontend** — `npm ci`, `npm test` (`src/data.test.mjs`), `npm run build`. **No lint or typecheck
  step**, and that is deliberate: this is a plain JS Vite app with no eslint config, no tsconfig and
  no typescript dependency. The old job ran `npm run lint` and `npx tsc --noEmit`, both carried over
  from the deleted Next.js app, so it could only ever fail.
- **images** — Buildx with GitHub Actions layer cache (`cache-from/to: type=gha`), over a matrix of
  all three Dockerfiles, `push: false`.

> **What changed from the earlier revision.** Steps no longer end in `|| true` — the hackathon-era
> escape hatch that let lint and test failures report without blocking. Both gates are now real.
> `push: false` remains: there is no CD, and images never reach a registry.

**The one test that can wreck the CI budget.** `test_api_endpoints.py::test_valid_storm_id_returns_200_or_500_or_429`
runs the **real pipeline against the real Groq API** — the only live-network test in the suite. With
quota free the whole suite is ~45 s; with the key pool saturated, or with CI's placeholder
`GROQ_API_KEY`, that single test drags it to 9–12 minutes.

## 2.3 Health checks and readiness

`backend/health.py` uses a registry, so a new dependency joins without editing the endpoint:

```python
health_collector.register("detection",      _check_detection)       # STORM_CONFIGS non-empty
health_collector.register("ml_models",      _check_ml)              # all 6 checkpoints load
health_collector.register("genai_module",   _check_genai)           # genai.impact_router importable
health_collector.register("knowledge_base", _check_knowledge_base)  # every KB holds chunks
```

`/health/ready` returns **503** if any check fails, with a per-check breakdown — so a degraded
instance is removed from service and the reason is in the response body, not buried in logs.

**Why `knowledge_base` had to exist as its own check.** `genai_module` is an *import probe*: it
returns `True` against a completely empty database. And `retrieve_chunks()` swallows storage errors
and returns `[]`. So a ChromaDB that was unreadable — or, as actually happened with a misresolved
`HELIOOPS_CHROMA_PERSIST_PATH`, silently **created empty at the wrong path** — produced confident
ungrounded advisories with no error anywhere in the system. Counting chunks per collection is the
only automatic signal that RAG is alive. Pinned by `backend/tests/test_runtime_paths.py`.

## 2.4 Observability

**Structured logging.** `structlog` emits JSON in production (`HELIOOPS_LOG_FORMAT=json`) and
human-readable console output in development. Log lines are keyed events, not sentences:

```python
log.info("pipeline_completed", storm_id=storm_id, duration_seconds=round(duration, 3))
log.error("pipeline_error", storm_id=storm_id, error=str(exc))
```

That is directly queryable — filter by `storm_id`, aggregate `duration_seconds`, alert on
`pipeline_error` rate. Free-text logs cannot do any of that.

**Metrics.** `/metrics` emits hand-rolled Prometheus exposition format — uptime, pipeline
requests/errors, average and p99 duration, detection and advisory counts, WebSocket connections. The
duration list is capped at 1000 samples and trimmed to the most recent 500: a deliberate bound so an
in-memory latency buffer cannot grow without limit.

> **Known gap:** counters and the rate limiter live in **process memory**. Correct at one replica; at
> three, each instance reports and rate-limits independently. A shared store (Redis) is the fix, and
> it is a prerequisite for horizontal scaling meaning anything — not an optimisation.

## 2.5 Configuration

`backend/config.py` uses Pydantic `BaseSettings`: every knob comes from an environment variable with
a typed default, documented in `.env.example`. Log level and format, host/port/workers, CORS origins,
ChromaDB path, ML checkpoint directory, repository backend and Supabase settings are all
environment-driven, so environments differ by configuration alone — never by code.

Three configuration facts that have each cost a debugging session:

| Fact | Consequence if forgotten |
|---|---|
| Relative `HELIOOPS_CHROMA_PERSIST_PATH` resolves against the **repo root** | It used to resolve against `backend/`, turning the shipped `backend/data/chroma_db` into `backend/backend/data/chroma_db` — a path Chroma happily *creates*. Every KB read 0. |
| `genai` reads `GROQ_API_KEY` from `os.getenv`, **not** `settings.GROQ_API_KEY` | Settings uses the `HELIOOPS_` prefix, so that field is always empty and its "not set" warning is spurious. `backend/__init__.py` loads `.env` for every entry point. |
| Production CORS origins are **defaults in `config.py`**, not deploy-only secrets | `HELIOOPS_CORS_ORIGINS` *replaces* the list rather than extending it, so a forgotten or partial secret silently `4003`s the WebSocket — which reads as a backend fault, not a config one. |

Never hardcode a runtime path: import it from `backend/paths.py`, which resolves `BACKEND_DIR`,
`DATA_DIR`, `CHROMA_DIR`, `STUBS_DIR`, `CHECKPOINT_DIR` and `ML_DATA_DIR` absolutely and cwd-proof.

## 2.6 Deployment targets

The backend is **one stateless container** — a single FastAPI process, no queue, no worker, no second
service — that reads `backend/data` from the image.

| Target | Status | Notes |
|---|:--:|---|
| Frontend → **Vercel** | 🟢 live | project `frontend`, alias `frontend-olive-six-50.vercel.app` |
| Backend → **Hugging Face Spaces** | 🟡 build-ready | root `Dockerfile`, free CPU tier (2 vCPU / 16 GB) |
| Also runs on | — | Cloud Run · Fly · Render, all with scale-to-zero |

Cold start is dominated by loading the BGE embedder and ChromaDB (~10–20 s) — which is why the
embedder is baked into the image rather than downloaded on first request. If scale-to-zero cold
starts matter more than idle cost, keep one warm instance.

**Why direct CORS instead of a Vercel rewrite:** a rewrite adds a hop, cannot proxy `/ws/stream`, and
would split REST and WS across two paths. One origin plus one CORS list covers both.

Procedures: [`DEPLOYMENT.md`](./DEPLOYMENT.md) (both halves, latency budget, failure modes) and
[`HOW_TO_DEPLOY_BACKEND.md`](./HOW_TO_DEPLOY_BACKEND.md) (backend-only: secrets, verification,
troubleshooting).

## 2.7 What was deleted, and why

An earlier revision of this repo carried `k8s/` (Kustomize base plus staging/production overlays and a
ServiceMonitor), `infra/` (Terraform modules for a VPC and an EKS cluster), `argocd/` (GitOps
Applications), `chaos/` (three scheduled Chaos Mesh experiments) and `runbooks/` (four incident
runbooks). All of it was **deleted on 2026-08-21**.

The reasoning, stated plainly: **a Kubernetes platform for two containers was the single largest cost
item in the project, and it contradicts the scale-to-zero target.** The application is one stateless
process. An EKS cluster to run it costs more per month than the entire rest of the stack combined and
buys nothing the platform-managed targets in §2.6 do not already provide. Keeping manifests nobody
applies is worse than not having them: they make the repo *claim* an operational maturity that was
never exercised.

Deleted alongside it, for the same reason — scaffolding around an algorithm is not the algorithm:

| Removed | Why |
|---|---|
| `agentscope` | supplied a message envelope that a plain `dict` covers |
| `langchain-core`, `langchain-groq` | supplied two dicts and an attribute read; pure cold-start weight |
| `redis`, `fakeredis` | backed an embedding cache for a one-shot offline ingest over 7 PDFs — a cache for a command nobody runs twice |

The design notes for all of it survive in git history and in `REFACTOR_MAP.md`.

---

# 3. ML

Two distinct ML surfaces: **computer vision** for detection (`cv/`) and **supervised quantile
regression** for impact (`backend/ml/`). Both run on CPU.

## 3.1 CV detection — and why there is no CNN

The original design used a CNN (`cv/cmecnn.py`). It was **removed and replaced** by a deterministic
threshold detector. The reasoning, recorded in `cv/README.md`:

1. No labeled training data exists for coronagraph CME segmentation.
2. NASA DONKI already publishes authoritative, human-reviewed kinematics.
3. A deterministic detector is reproducible, testable, and needs no GPU.

This is the most important engineering judgement in the repository: the team removed the
machine-learning component from the vision layer because a threshold algorithm plus an authoritative
physics API produced *more defensible* output than a model trained on labels that do not exist.

### The 9-step algorithm (`backend/cv/image_threshold_algorithm/threshold_detector.py`)

```
1. Annular mask            exclude occulter disc + far field
2. Per-frame μ/σ           statistics computed inside the mask only
3. Bright threshold        bright_mask = diff > μ + 2.5σ
4. Morphological open+close  remove speckle, close gaps
5. Connected components    take the largest
6. Bounding box            Cartesian, normalized, padded
7. CPA + angular width     polar geometry about the occulter centre
8. Confidence              f(area, SNR)
9. Annotate + save PNG
```

Operating on **running-difference frames** (`cv/preprocessing.py`) is what makes a plain threshold
viable: subtracting consecutive frames removes the static corona and leaves only what moved, so the
CME is the dominant bright structure rather than one feature among many.

Two implementation details carry real weight:

- **`_circular_mean_deg()`** computes the circular mean via `atan2(mean(sin), mean(cos))`. Position
  angles wrap at 0/360°; a naive arithmetic mean of 350° and 10° gives 180° — pointing the CME in
  exactly the wrong direction. This is the "correct on edge cases" version, not the shorter one.
- **`find_occulter_center()`** measures the occulter at runtime instead of trusting the
  `DEFAULT_CENTER_XY = (256, 256)` constant, because LASCO and CCOR-1 differ and a real instrument is
  never perfectly centred. The constants are calibration defaults, not assumptions.

Every tunable is a named module constant — `SIGMA_THRESHOLD = 2.5`, `ANNULAR_OUTER_PX = 220`,
`MIN_BRIGHT_PX = 40`, `CONF_AREA_SCALE = 300.0` — so the detector can be retuned per instrument
without touching the algorithm.

**Determinism guarantee:** no RNG anywhere in the path. The same `diff_frame` yields an identical
dict and byte-identical PNG on every run — which is what makes the 43 tests in
`tests/test_option_c.py` meaningful rather than flaky.

### Multi-source physics fusion

Detection alone is not a storm assessment. `backend/cv/storm_event_generator/fusion.py` combines four independent sources with a
weighted confidence:

```
confidence = 0.4·detection + 0.2·flare + 0.2·solar_wind + 0.2·cme
```

| Source | Client | Contributes |
|---|---|---|
| Coronagraph imagery | `threshold_detector.py` | Detection confidence, bbox, angular width |
| NASA DONKI | `donki_client.py` | CME speed, angular width, direction |
| GOES XRS | `flare_classifier.py` | Flare class (X/M/C) → R-scale |
| DSCOVR L1 | `l1_client.py` | Bz, Bt, density, solar wind speed, ETA |

Imagery gets the largest single weight but cannot exceed 40% — no single sensor can drive the
assessment alone. The output `StormEvent` carries `confidence`, `scales {G,S,R}`, `cme`, `flare`,
`l1_solar_wind`, `timeline` and `noaa_alert_raw`.

### Graceful degradation

Every stage has a defined fallback, ordered most- to least-desirable:

```
PNGs present     → use them         else → cache_fits.py must run
Detector fires   → real bbox        else → stub bbox_norm
DONKI cached     → real physics     else → fetch live → on failure → stub speed
StormEvent built → return it        else → load ml/stubs/storm_event_{id}.json
```

The system always returns a usable `StormEvent`. It never returns a half-populated object or raises
into the API layer.

## 3.2 Impact prediction — LightGBM quantile regression

`backend/ml/` predicts two operationally meaningful quantities from storm features:

- **GPS L1 position error** (metres)
- **HF radio blackout probability** (0–1)

### Six models, not two

```
StormEvent → feature extraction → 6 LightGBM models → ImpactPrediction
                                   ├── gps_q025 / gps_q500 / gps_q975
                                   └── hf_q025  / hf_q500  / hf_q975
```

Each target gets three independently trained quantile regressors: 2.5th, 50th, 97.5th percentile.
The 2.5–97.5 pair *is* the 95% confidence interval, produced directly by the models rather than
estimated afterwards from residuals.

**Why quantile regression here.** A single number is operationally useless for a safety decision. A
dispatcher choosing whether to close a polar route needs the plausible worst case, not just the
expectation. Training with **pinball loss** at three quantiles yields that directly.

**Nine features** extracted from the CV `StormEvent`: `g_scale`, `kp_index` (via the
`{0:0, 1:5, 2:6, 3:7, 4:8.3, 5:9}` map), `bz_nt`, `wind_speed_km_s`, `cme_speed_km_s`,
`cme_width_deg`, `r_scale`, plus `geomag_lat_bin` and `local_time_bin` (defaulted to mid-latitude /
dayside).

### Training methodology

| Technique | Purpose |
|---|---|
| **GroupKFold** splitting | Prevents temporal leakage — frames of one storm cannot straddle train/test |
| **Optuna** | Hyperparameter search over LightGBM |
| **Pinball loss** | The correct objective for quantile targets |
| **PICP / PINAW** | Evaluates interval *calibration*, not just point accuracy |
| **Physical anchor test** | `03_anchor_test.py` — G5 black-swan validation |

### Measured results

The checkpoints in the repo were retrained on 2026-08-22. `02_train_and_tune.py` prints these two
numbers at the end of every run — they are the ones worth quoting:

| Target | **PICP** *(nominal 95%)* | **PINAW** *(interval width)* |
|---|:--:|:--:|
| GPS L1 error | **95.90%** | 0.0369 |
| HF blackout probability | **94.21%** | 0.1941 |

**PICP is the number that matters, and PINAW is what stops it being gamed.** PICP says: when the
model claims 95% confidence, the truth falls inside the stated interval 95.9% / 94.2% of the time.
On its own that is trivially cheated — predicting `(−∞, +∞)` scores 100% coverage and is useless — so
PINAW reports the *cost* of the coverage. Both land within ~1 point of nominal at a narrow width,
which is the entire claim the quantile objective makes.

**Point-accuracy metrics (R², MAE, RMSE) are deliberately not quoted here.** They are printed by the
training script and they are circular by construction: the models are fit to synthetic rows generated
from hand-written rules, so R² measures how well LightGBM recovered those rules. Quoting a 0.98 as if
it were forecast skill is exactly the claim this project does not make. See
[`CV_ML_QNA.md`](./CV_ML_QNA.md) §8.1.

**Live on the two anchor storms, through the serving path:**

| Storm | Scales | GPS error | 95% CI | HF blackout | 95% CI |
|---|:--:|:--:|:--:|:--:|:--:|
| `2024-10-G4` | G4 S2 R3 | 11.23 m | 6.83 – 13.67 | 0.932 | 0.870 – 0.999 |
| `2024-05-G5` | G5 S3 R5 | 22.02 m | 13.34 – 25.92 | 0.947 | 0.928 – 1.000 |

**The anchor test is a gate, not a report.** `03_anchor_test.py` runs **two** anchors through
`inference.predict()` — the serving path, so training/serving skew cannot pass unnoticed:

| Anchor | Assertion |
|---|---|
| 2024-05 G5 (CME 1800 km/s, Bz −40 nT) | GPS > 15 m **and** HF > 0.80 |
| quiet baseline (G0/R0, 400 km/s, Bz +2 nT) | GPS < 2 m **and** HF < 0.60 |
| both together | G5 impact strictly exceeds the quiet baseline on both targets |

The quiet baseline and the ordering check are the point: **a constant model passes any single-storm
floor.** The script `exit(1)`s on failure — it previously caught its own `AssertionError` and exited
0, which meant the physics gate could not gate anything.

> **Stated honestly:** training data is **synthetic** — 4,800 rows, 120 storms × 40 frames, seed 42,
> committed as `backend/ml/data/synthetic_storms.csv`. A real-data track *was* built against NASA
> OMNI2 (1996–2025) and then **deleted on 2026-08-22**: OMNI supplies every driver and no label, and
> the labels needed (IONEX TEC, GOES XRS+SEP) are not published in the required form. A scaffolded
> pipeline that cannot be trained is indistinguishable in the tree from one that can, so it went —
> 296 MB and ~1,500 lines, recoverable from git history if label builders ever land.

### Two production-hardening details

**Quantile monotonicity.** Independently trained quantile models can *cross* — q97.5 can land below
q50, producing an inverted, nonsensical interval. Enforced post-prediction:

```python
ci_low, median, ci_high = sorted([q025, q500, q975])   # guarantees ci_low ≤ median ≤ ci_high
```

One `sorted()` call removes a whole class of invalid output.

**Conservative fallback.** If checkpoints are missing, inference returns GPS = 20 m and
HF = 85% — deliberately *pessimistic* values. In a safety system the fallback must fail toward
caution, never toward "all clear". The `/health/ready` check reports the degraded state
independently, so a fallback is visible rather than silent.

Checkpoints total under 500 KB and run on CPU.

---

# 4. Agentic AI

The most technically dense layer: four LLM agents running in parallel over a RAG knowledge base, with
ten anti-hallucination controls and a deterministic rule engine downstream.

## 4.1 Topology

```
                    StormEvent
                        │
                ┌───────▼────────┐
                │  route_storm() │  deterministic G-scale → severity matrix, NO LLM
                │ impact_router  │
                └───────┬────────┘
                        │  asyncio.create_task — parallel fan-out
        ┌───────────┬───┴───────┬───────────┐
        ▼           ▼           ▼           ▼
    Aviation      Grid      Maritime     Telecom      (each: RAG → LLM → guardrails)
        └───────────┴───┬───────┴───────────┘
                        │  event-queue drain + fan-in
                ┌───────▼────────┐
                │ verify_advisory│  deterministic rule engine, ZERO LLM calls
                └───────┬────────┘
                        ▼
          (VerifiedAdvisory, ProvenanceTrace) → API → dashboard → Postgres
```

## 4.2 Deterministic routing — the LLM is not in charge

`backend/genai/impact_router.py` holds a hard-coded matrix. No model chooses severity:

| | Aviation | Grid | Maritime | Telecom |
|---|---|---|---|---|
| **G1** | LOW | LOW | NONE | NONE |
| **G2** | MEDIUM | MEDIUM | LOW | LOW |
| **G3** | HIGH | HIGH | MEDIUM | MEDIUM |
| **G4** | CRITICAL | CRITICAL | HIGH | HIGH |
| **G5** | CRITICAL | CRITICAL | CRITICAL | CRITICAL |

Sourced from NOAA Space Weather Scales and NESDIS impact briefings. Industries below their trigger
tier return `triggered=False` and no agent is spawned for them.

**Why this is not an agent decision.** Operators need certainty that G4 always means CRITICAL for
aviation — not HIGH because a sampler drifted. Determinism here also makes the whole routing layer
unit-testable and auditable, and it becomes the floor that guardrail #5 enforces the LLM against.

## 4.3 Orchestration — plain asyncio, no framework

`backend/genai/orchestrator.py` fans out with `asyncio.gather` behind a semaphore
(`GENAI_MAX_CONCURRENCY`). Adding an industry is a one-line registry entry:

```python
_AGENT_REGISTRY: dict[str, type] = {
    "aviation": AviationAgent, "grid": GridAgent,
    "maritime": MaritimeAgent, "telecom": TelecomAgent,
}
```

> **AgentScope and LangChain were both dropped on 2026-08-21**, replaced by a **45-line groq
> wrapper** (`backend/genai/llm.py`). The honest accounting of what they were providing: AgentScope
> supplied a `Msg` + `TextBlock` message envelope that a plain `dict` covers, and
> `langchain-core` + `langchain-groq` supplied two dicts and an attribute read. Neither offered a
> graph, a scheduler or a retry policy this pipeline uses — the fan-out is four concurrent calls with
> no conditional edges — so both were pure cold-start weight on a container that is trying to
> scale to zero.

What remains is the property that mattered anyway: **a debuggable call stack.** There is no graph
compilation step between the code and the four HTTP requests, and there is exactly **one** Groq call
site — `genai/llm.py::complete_json`. Every retry, rate-limit park and key-pool decision lives in
that one function.

**Streaming while running.** `stream_pipeline()` is an async generator. Agents push events into an
`asyncio.Queue` via a callback; the orchestrator drains the queue on a 50 ms tick while tasks are
in flight, so the dashboard sees agents thinking *live* rather than after completion:

```python
while True:
    all_done = all(t.done() for t in agent_tasks)
    while not event_queue.empty():
        yield event_queue.get_nowait()
    if all_done:
        break
    await asyncio.sleep(0.05)
# final drain — events queued between the last check and completion
```

The post-loop final drain is the correctness detail: without it, events enqueued between the last
poll and task completion would be silently dropped.

**The embedder prewarm.** A genuine concurrency bug, fixed at the source:

```python
def _prewarm_embedder() -> None:
    """Load BGE model once in the main thread before parallel asyncio.to_thread calls.
    Prevents race condition: multiple threads calling _get_model() simultaneously
    causes 'Cannot copy out of meta tensor' PyTorch error."""
    from embeddings.embedder import _get_model
    _get_model()
```

Four agents hitting a lazy-loaded singleton from four `asyncio.to_thread` workers raced on PyTorch's
meta-tensor materialization. One eager load in the main thread, before any fan-out, removes the race
for every caller — rather than adding a lock to each agent.

**Fault isolation.** `asyncio.gather(..., return_exceptions=True)` in the batch path, and per-task
`try/except` in the streaming path, mean one failed agent yields an `agent.error` event while the
other three still deliver advisories.

## 4.4 RAG infrastructure

```
data/{aviation,grid,maritime,impact_matrix}/*.pdf
   └── loaders.py → chunker.py → embedder.py (BGE-small) → ChromaDB
                                                            ├── aviation_kb        242 chunks
                                                            ├── grid_kb            101 chunks
                                                            ├── impact_matrix_kb   166 chunks
                                                            ├── maritime_kb          2 chunks
                                                            └── telecom_kb           0 chunks
```

Real regulatory sources, ingested from PDF: ICAO **NAT Doc 007** (2025), **NERC TPL-007-4** plus
benchmark GMD and transformer-thermal documents, **IMO GMDSS** (2019), and the NOAA/NESDIS space
weather scales and impact memos.

**Embedding choice — BGE-small-en-v1.5:** 384-dim, fast on CPU, and *asymmetric* — a query prefix is
applied at query time but not at index time, which is what the model was trained for and what makes
it outperform MiniLM on retrieval. Vectors are stored L2-normalized, so cosine similarity is
recovered as `1 - dist/2` with no extra computation.

**ChromaDB `PersistentClient`** is embedded — no server process, no network hop, no extra container
in the deployment.

**Chunking:** 512 tokens with 64-token overlap, token-aware via `tiktoken`. Overlap prevents a
procedure step from being severed at a chunk boundary and losing its context.

**Retrieval per agent:** top-8 from the industry KB plus top-4 from the impact matrix, filtered at
0.35 cosine similarity, both queried in parallel through `asyncio.to_thread`. Context is formatted as
labelled blocks carrying `chunk_id`, `source` and `similarity` — which is what makes citation
verification possible downstream.

## 4.5 The per-agent pipeline

Every agent runs the same 11 steps inside `IndustryAgentBase.run_async()` (`genai/agents/base.py`);
subclasses supply only a system prompt and a KB query template:

```
 1. Build KB query from storm parameters (G/Kp/S/R)
 2. Parallel ChromaDB retrieval — industry KB (top 8) + impact matrix (top 4)
 3. Format context — labelled blocks with chunk_id, source, similarity
 4. Generate — Groq Llama 3.3 70B, temperature 0.1, JSON mode
 5. Validate schema — Pydantic, fails fast on missing source_ref
 6. Severity consistency — LLM cannot go below the deterministic matrix
 7. LLM self-check — separate Groq call in critic mode
 8. Confidence score — multi-factor
 9. Safety flags — non-blocking audit markers
10. Retry loop — up to 3 attempts, errors injected into the next prompt
11. Safe fallback — ESCALATE_TO_SPECIALIST if all retries fail
```

## 4.6 Ten anti-hallucination layers

| # | Technique | Where | Effect |
|---|---|---|---|
| 1 | RAG-only grounding | system prompt | Training knowledge forbidden; cite provided context only |
| 2 | Citation enforcement | prompt + Pydantic | Every action needs `source_ref`; missing ⇒ validation failure ⇒ retry |
| 3 | Retrieval quality gate | `retriever.py` | Chunks below 0.35 cosine dropped before the LLM sees them |
| 4 | JSON schema enforcement | Groq JSON mode + Pydantic | Structurally valid output, then type/constraint validation |
| 5 | Deterministic severity override | `guardrails.py` | LLM below matrix minimum ⇒ `SEVERITY_MISMATCH` flag |
| 6 | Source existence check | `guardrails.py` | `sources_cited` cross-checked against retrieved chunks ⇒ `CITATION_GAP` |
| 7 | LLM self-check | `guardrails.py` | Second call audits numeric values and regulation codes against context |
| 8 | Retry with error injection | `agents/base.py` | Validation errors fed back: "FIX THESE: …" |
| 9 | Confidence score | `guardrails.py` | Multi-factor score exposed to reviewers |
| 10 | Conservative fallback | `agents/base.py` | All retries exhausted ⇒ `ESCALATE TO SPECIALIST` |

**Confidence formula:**

```
base_score        = mean cosine similarity across retrieved chunks
+ citation_bonus  = +0.02 per action_item with a verified source_ref
- citation_penalty= -0.08 per action_item missing/unverifiable source_ref
+ coverage_bonus  = +0.10 if base_score > 0.6
confidence_score  = clamp(score, 0.0, 1.0)
```

The penalty is 4× the bonus — asymmetric on purpose. A fabricated citation is far more dangerous than
a missing bonus is valuable. Below 0.50 the advisory is flagged `LOW_CONFIDENCE`.

**Safety flags** are audit markers, not blocks: `SEVERITY_MISMATCH`, `HALLUCINATION_DETECTED`,
`LOW_COVERAGE`, `LOW_CONFIDENCE`, `CITATION_GAP`, `GENERATION_FAILED`. The advisory still reaches the
operator with its caveats attached, rather than vanishing — an operator with a flagged advisory is
better off than an operator with nothing.

**Why a separate self-check call.** The generating model is in "write" mode; a fresh call in "critic"
mode catches inconsistencies the generator cannot see in a single pass. Cost: one extra call per
industry — deliberately routed to the lighter `llama-3.1-8b-instant` checker model to stay within
Groq rate limits while the 70B model does generation.

**Retry with error injection** (#8) is the mechanism that makes the rest converge: the model is shown
its own validation errors and asked to fix them, so a missing `source_ref` is usually corrected on
attempt two rather than burning all three.

## 4.7 The deterministic verifier

`genai/verifier.py` — zero LLM calls, runs after every agent completes.

| Rule | Industry | Valid set | Detection |
|---|---|---|---|
| HF frequency | aviation, maritime | `{3, 5, 8, 11, 17}` MHz (ICAO NAT) | regex `(\d+)\s*MHz` |
| Reroute latitude | aviation | G3→78°N, G4→70°N, G5→60°N | regex `(\d+)\s*°?\s*N` |
| GIC operating step | grid | NERC TPL-007-4 Appendix B | keyword match |
| GMDSS channel | maritime | valid distress/working channels | keyword match |

The worked example: the model writes `"21 MHz"` → regex extracts `21` → `21 ∉ {3,5,8,11,17}` →
`status="blocked"`, `corrected_to=5` (ICAO G4+ default backup) → the action text is **corrected
in place** → logged and streamed as a `verifier.check` WebSocket event that the dashboard renders as
a visible block.

```python
verified, trace = verify_advisory(advisory, storm.model_dump(mode="json"), impact_assessment)
# verified.verifier.status              == "passed_with_corrections"
# verified.verifier.checks[0].field     == "hf_band"
# verified.verifier.checks[0].proposed  == 21
# verified.verifier.checks[0].corrected_to == 5
```

**Why this exists.** RAG reduces hallucination; it does not eliminate it. Models still fabricate
specific numeric values even with correct context in the window. The verifier is fast, fully
auditable, and — critically — **corrects rather than merely rejects**, so a single bad frequency does
not discard three otherwise-correct action items.

## 4.8 Contracts and provenance

`backend/genai/contracts.py` defines the typed hand-off between layers, so teams could build in parallel
against a fixed interface:

- **`ImpactAssessment`** (ML → GenAI) — `storm_id`, `model_version`, `low_confidence`,
  `source` (`"model"` | `"severity_floor"`), and a list of `ImpactMetric` each carrying
  `{domain, metric, value, ci_low, ci_high, ci_level, qualifier}`.
- **`VerifiedAdvisory`** (GenAI → delivery) — `advisory_id`, `storm_id`, `industry`, `severity`,
  `numbered_actions` (verifier-corrected plain text), `timing_window`, `technical_details`,
  `cited_procedure`, `verifier` result, `provenance_ref`, `requires_human`.
- **`ProvenanceTrace`** — `trace_id`, `advisory_id`, and a 6-step chain:
  `raw_data → detection → impact → retrieval → verifier → output`.

The `source: "model" | "severity_floor"` field is a small but telling design choice: a consumer can
tell whether a number came from a real model prediction or from a conservative fallback, and treat it
accordingly.

## 4.9 Configuration

Every knob in `genai/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Generation |
| `GROQ_CHECKER_MODEL` | `llama-3.1-8b-instant` | Self-check (lighter, cheaper) |
| `GROQ_TEMPERATURE` | `0.1` | Near-deterministic; > 0 required by Groq JSON mode |
| `GROQ_MAX_TOKENS` | `2048` | Per generation call |
| `MAX_PROMPT_TOKENS` | `4000` | RAG context budget cap |
| `RAG_TOP_K` | `8` | Industry KB chunks |
| `RAG_IMPACT_MATRIX_TOP_K` | `4` | Impact matrix chunks |
| `RAG_MIN_SIMILARITY` | `0.35` | Cosine floor |
| `RAG_LOW_COVERAGE_THRESHOLD` | `3` | Fewer valid chunks ⇒ `LOW_COVERAGE` |
| `MAX_RETRY_ATTEMPTS` | `3` | Before safe fallback |
| `SELF_CHECK_ENABLED` | `True` | Toggle critic pass |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | Flag boundary |

`telecom_kb` is intentionally left empty, so the telecom agent produces a `LOW_COVERAGE` advisory —
a live demonstration that the system reports thin evidence rather than inventing content to fill a
gap.

---

# 5. Testing

`PYTHONPATH=. pytest backend/tests -q` — **271 tests collected**, all green.

| Suite | Test fns | Covers |
|---|--:|---|
| `backend/tests/test_option_c.py` | 43 | CV detector geometry, flare/DONKI math, the `fuse()` contract |
| `backend/tests/test_llm_ratelimit.py` | 31 | TPM accounting, key-pool rotation, 429 parking, retry bounds |
| `backend/tests/test_security.py` | 23 | Headers, validation, rate limiting, CORS |
| `backend/tests/test_cv_preprocessing.py` | 22 | FITS fixes, running difference, **batch png/diff layout round-trip** |
| `backend/tests/test_verifier.py` | 21 | The ICAO NAT and GMDSS rule engine |
| `backend/tests/test_pipeline.py` | 17 | Schema adaptation, orchestration, **WS event contract**, import guard |
| `backend/tests/test_api_endpoints.py` | 16 | REST contract — includes the only live-network test |
| `backend/tests/test_middleware.py` | 12 | Middleware behaviour |
| `backend/tests/test_retrieval.py` | 11 | RAG retrieval and similarity filtering |
| `backend/tests/test_runtime_paths.py` | 9 | 🔴 Chroma/checkpoint path resolution |
| `backend/tests/test_preflight.py` | 25 | Read-only guarantee, every conflict rule, quota shape, e2e |

**Frontend:** `npm test` runs `src/data.test.mjs` — a plain-node contract test over the static copy
module. There is no Vitest/jsdom suite: the ~255-test component suite belonged to the deleted Next.js
app and went with it. An untracked `frontend/__tests__/` directory may still exist in a working copy;
it is not in git and CI does not run it.

**Four tests exist because of a bug that shipped silently**, and each pins the fix:

| Test | What it stops recurring |
|---|---|
| `TestNoCircularImports` | an adapter importing `backend.pipeline` at module level — breaks `import backend.pipeline` on its own, invisible under the full suite |
| `TestStreamEventContract` | `genai`'s own `pipeline.complete` forwarded raw, colliding with the terminal event so the frontend stops before verification |
| `TestBatchLayoutRoundTrip` | the write path and read path drifting apart on `png/` + `diff/`, silently degrading `detect()` to the stub forever |
| `TestChromaPathResolution` | a relative chroma path resolving against `backend/` instead of the repo root — every KB empty, every advisory ungrounded, nothing logged |
| `TestGuardrailsWiring` | `self_check_hallucination()` swallowing every exception, so a broken call site turns the guard off with no error anywhere |

> **Known flake:** `test_retrieval.py` fails roughly 1 full-suite run in 3 with a chromadb
> segment-reader `InternalError`. It passes standalone (11/11) and KB counts stay correct — a
> pre-existing chromadb bug, mitigated by a retry in `collections.py`, not fixed.

---

# 6. Cross-cutting patterns

Five ideas recur in every layer, and they are what make the system coherent rather than four projects
in a trench coat:

1. **Deterministic where it must be, generative where it helps.** Detection, routing and verification
   have no randomness. The LLM writes prose inside boundaries it cannot move.
2. **Fail conservative, fail visible.** Every fallback errs toward caution — stub events, 20 m/85%
   defaults, `ESCALATE TO SPECIALIST` — and every degradation is reported through a flag, a health
   check, or a log event. Nothing degrades silently.
3. **Contracts before implementation.** Pydantic models and `contracts.py` fixed the interfaces so
   four people could build four layers concurrently; the schema adapter absorbs the mismatch at one
   seam.
4. **Auditability is structural.** Provenance traces, verifier check records, retrieval similarities
   and confidence scores are first-class schema fields — in Postgres, in the API response, and on
   screen. None of it is reconstructed from logs after the fact.
5. **Bridge, don't rewrite.** The backend integrated four independently-built layers without
   modifying any of them, by paying the translation cost once in an anti-corruption layer.

---

# 7. Known gaps

Consolidated from the sections above, in rough priority order:

| Gap | Impact | Fix |
|---|---|---|
| ML trained on synthetic data | Reported R² measures rule-recovery, not forecast skill | Blocked, not deferred — needs an IONEX/GOES label builder that no public dataset supplies (§3.2) |
| `_pick_key()` waits in an unbounded `while True` | With every Groq key parked, `/api/detect` and `/ws/stream` **stall for minutes** with no error and no client-side timeout | Bound the wait and surface a 503; neither the per-call timeout nor `GROQ_MAX_RETRIES` bounds it today |
| Rate limiter + metrics in process memory | Incorrect beyond one replica | A shared store (Redis) — a prerequisite for scaling, not an optimisation |
| `docker-build` has `push: false` | No CD; images never reach a registry | GHCR push once registry secrets are in place |
| In-memory repository is the default | Results lost on restart unless Supabase is configured | Set `HELIOOPS_RESULT_REPOSITORY=supabase` in deployed environments |
| No cached FITS/PNGs in git (too large) | `detect()` silently falls back to `backend/cv/stubs/*.json` | Run `cache_fits` + `preprocessing`, or ship an artifact step |
| Two demo storms wired for replay | Live mode exists but is not the demo path | Broaden `STORM_CONFIGS`, exercise `detect_live()` |
| `test_retrieval.py` flake (~1 run in 3) | Full-suite runs go red on a chromadb-internal error | Upstream chromadb bug; mitigated by a retry in `collections.py` |
| `/api/detect` takes 65–80 s | Not a demo-friendly latency | Dominated by the `gpt-oss-120b` reasoning pass; a pooled key set is the only real lever |

**Closed since the previous revision of this document:** CI steps no longer end in `|| true` (both
gates are real); ChromaDB and the 6 checkpoints **are** committed, so CI no longer runs against
fallbacks; `maritime_kb` is fully ingested at 214 chunks and the corpus totals 918.

The gaps are documented in the repo rather than hidden, which is the right posture — but the unbounded
key wait and the in-memory repository default are the two that would bite first in a real deployment.
