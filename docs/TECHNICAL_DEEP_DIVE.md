# HelioOps — Technical Deep Dive

How each engineering domain is actually implemented in this repository, with file references.
Companion to [`PRODUCT_BRIEF.md`](./PRODUCT_BRIEF.md).

All four domains are present:

| Domain | Status | Where |
|---|---|---|
| 1. Full stack | ✅ | `backend/`, `frontend/`, `supabase/` |
| 2. DevOps | ✅ | `Dockerfile.*`, `.github/workflows/`, `k8s/`, `infra/`, `argocd/`, `chaos/`, `runbooks/` |
| 3. ML | ✅ | `cv/` (computer vision), `ML_after_CV/` (impact regression) |
| 4. Agentic AI | ✅ | `genai/`, `embeddings/` |

---

# 1. Full Stack

## 1.1 Backend — FastAPI with a hexagonal core

`backend/app.py` is deliberately thin. The interesting decision is that the pipeline does not import
`cv.detect` or `ML_after_CV.inference` directly. It talks to **ports** (abstract interfaces), and
**adapters** provide the concrete implementations.

```
backend/
├── ports/                    abstract interfaces — the contract
│   ├── detection.py          DetectionPort
│   ├── prediction.py         PredictionPort
│   ├── advisory.py           AdvisoryPort, VerificationPort
│   └── repository.py         ResultRepository
├── adapters/                 concrete implementations — the plumbing
│   ├── detection_adapter.py     → wraps cv.detect
│   ├── prediction_adapter.py    → wraps ML_after_CV.inference
│   ├── advisory_adapter.py      → wraps genai.run_pipeline + verifier
│   ├── repository_adapter.py    → InMemoryResultRepository | SupabaseResultRepository
│   └── schema_adapter.py        → anti-corruption layer between layer schemas
├── pipeline.py               run_full_pipeline() / stream_full_pipeline()
├── app.py                    routes, CORS, middleware, WebSocket manager
├── health.py                 /health, /health/ready, /health/live, /metrics
├── middleware.py             security headers, request IDs, rate limit, input validation
├── config.py                 Pydantic BaseSettings — every knob from env
└── logging.py                structlog JSON setup
```

**Why ports and adapters here specifically.** Storage swaps at runtime with zero pipeline changes —
`_build_result_repository()` in `app.py:92` reads `settings.RESULT_REPOSITORY` and returns either the
in-memory dict store or the Supabase-backed one. Same interface, same call sites. The same pattern
makes the ML layer mockable in tests without touching real checkpoints.

**The anti-corruption layer is the load-bearing part.** The CV layer and the GenAI layer were built
by different people with different schemas, and neither was rewritten to accommodate the other.
`backend/adapters/schema_adapter.py` translates between them:

| `cv.fusion.StormEvent` | `genai.models.StormEvent` | Transform |
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
| GET | `/api/storms` | Available storms + summary of completed runs |
| GET | `/api/advisory/{advisory_id}` | Verified advisory + full provenance trace |
| GET | `/api/result/{storm_id}` | Complete stored pipeline result |
| WS | `/ws/stream` | Live pipeline event stream |
| GET | `/health` · `/health/ready` · `/health/live` | Three-tier health, see §2.5 |
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
`Content-Type`/`Authorization`. `tests/test_security.py` holds 23 tests over exactly these paths.

## 1.5 Frontend — Next.js 14 App Router

```
frontend/src/
├── app/
│   ├── page.tsx                          landing — scroll-driven frame sequence
│   ├── layout.tsx
│   └── dashboard/
│       ├── layout.tsx                    sidebar + topbar shell
│       ├── page.tsx                      overview
│       ├── pipeline/page.tsx             live WebSocket run view
│       ├── storms/page.tsx               storm list
│       ├── storms/[stormId]/page.tsx     storm detail
│       ├── results/[stormId]/page.tsx    full pipeline result
│       └── health/page.tsx               health + Prometheus metrics
├── components/
│   ├── dashboard/                        11 domain components
│   └── {ErrorBoundary,Toast,Skeleton,EmptyState,FrameScroller,...}.tsx
├── lib/{api,ws-client,utils}.ts
└── types/storm.ts                        mirrors the backend Pydantic models
```

Stack: React 18 + TypeScript 5.5, Tailwind, `framer-motion` + GSAP + `lenis` for motion,
`three` / `@react-three/fiber` / `drei` for the 3D landing visuals, `lucide-react` for icons.
Tests run on Vitest + Testing Library + jsdom.

**Typed API client (`lib/api.ts`).** Every path parameter is `encodeURIComponent`-wrapped. Failures
raise a custom `ApiError` carrying the HTTP status so callers can branch programmatically. 5xx and
network errors retry once with exponential backoff (`500ms · 2^attempt`); 4xx does not retry, because
a 400 or 404 will not fix itself. Error bodies are parsed for `detail`/`message` and fall back to
status text — server stack traces are never surfaced to the user.

`parseMetrics()` converts the Prometheus text exposition format into a `Map<string, number>`,
skipping comments and rejecting non-finite values, so the health page can render backend counters
without a metrics library.

**WebSocket client (`lib/ws-client.ts`).** A small state machine (`DISCONNECTED` → `CONNECTING` →
`CONNECTED`) with a listener set. Reconnect backoff doubles from 1 s to a 30 s ceiling and resets on a
successful open. Malformed JSON is warned and dropped rather than thrown — one bad frame must not
kill the stream. A throwing listener is caught so one broken subscriber cannot starve the others.
`connect()` is idempotent. The `http(s)→ws(s)` URL rewrite is a single regex on the shared base URL,
so there is only one place to configure the backend address.

**Failure containment in the UI.** `ErrorBoundary` and `DashboardErrorBoundary` stop a render error
in one card from blanking the page. `Skeleton`, `EmptyState` and `Toast` cover the loading, empty and
error states explicitly — the dashboard renders detection and impact data even when advisories fail
to generate, which is exactly the Groq-outage scenario described in the runbook.

## 1.6 Data layer — Supabase Postgres

`supabase/001_schema.sql` defines 4 enums and 8 tables; `002_rls.sql` adds Row Level Security;
`003_seed.sql` loads the two demo storms.

| Table | Source of truth |
|---|---|
| `storm_events` | `cv/fusion.py` → `StormEvent` |
| `impact_predictions` | `ML_after_CV/inference.py` → `ImpactPrediction` |
| `advisories` | `genai/models.py` → `AdvisoryOutput` |
| `action_items` | `genai/models.py` → `ActionItem` |
| `verified_advisories` | `genai/contracts.py` → `VerifiedAdvisory` |
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

# 2. DevOps

The full chain is present: **Docker → CI → Kubernetes → Terraform → GitOps → observability → chaos →
runbooks.**

## 2.1 Containers

`Dockerfile.backend` is a two-stage build. The builder installs all three requirements files into
`--prefix=/install`; the runtime stage is a clean `python:3.12-slim` that copies only `/install` plus
application packages — build toolchains never reach the final image.

```dockerfile
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir --prefix=/install -r ... -r ... -r ...

FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY backend/ cv/ genai/ ML_after_CV/ embeddings/ ml/ tests/ ...
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1
```

OCI labels (`org.opencontainers.image.{title,description,source}`) make images self-describing in a
registry. `Dockerfile.frontend` does the equivalent multi-stage build on Node 20.

`docker-compose.yml` wires both services for local development, with the detail that matters:

```yaml
depends_on:
  backend:
    condition: service_healthy      # not merely "started"
```

The frontend waits for the backend's *health check* to pass, not just for its process to exist —
which avoids the classic race where the UI boots against an API still loading ML checkpoints.
`data/` and `ML_after_CV/checkpoints/` are bind-mounted so large artifacts stay out of the image.

## 2.2 CI — GitHub Actions

`.github/workflows/ci.yml`, on push and PR to `main`, five jobs:

```
lint-backend ─┐
test-backend ─┼─► docker-build   (needs: test-backend, build-frontend)
lint-frontend ─► build-frontend ─┘
```

- **lint-backend** — `ruff check` + `ruff format --check`
- **test-backend** — installs all three requirement sets, runs pytest with `GROQ_API_KEY=test-key`
- **frontend** — `npm ci`, `npm test` (src/data.test.mjs), `npm run build`. No lint or
  typecheck step: the SPA is plain JS with no eslint config and no tsconfig.
- **build-frontend** — real `next build`, gated on lint
- **docker-build** — Buildx with GitHub Actions layer cache (`cache-from/to: type=gha`), builds both
  images, `push: false`

npm dependencies are cached via `cache-dependency-path: frontend/package-lock.json`.

> **Known gap:** most steps end in `|| true`, so they report but do not block. This was a deliberate
> hackathon-stage choice — `CI_CD_REQUIREMENTS.txt` documents that CI must stay green while ML
> checkpoints, ChromaDB and cached FITS data are missing from git. Removing `|| true` from
> `lint-backend` and `build-frontend` is the cheapest real hardening available, since neither depends
> on those artifacts.

## 2.3 Kubernetes

```
k8s/
├── base/            deployment, service, configmap, ingress, servicemonitor, kustomization
├── staging/         overlay
└── production/      overlay — 3 replicas, hardened
```

The base backend deployment covers the things that actually decide whether a rollout survives:

```yaml
readinessProbe:  { httpGet: { path: /health/ready, port: 8000 }, periodSeconds: 15 }
livenessProbe:   { httpGet: { path: /health/live,  port: 8000 }, periodSeconds: 30 }
resources:
  requests: { cpu: 250m, memory: 512Mi }
  limits:   { cpu: "1",  memory: 1Gi }
env:
  - name: GROQ_API_KEY
    valueFrom: { secretKeyRef: { name: helioops-secrets, key: groq-api-key } }
volumeMounts:
  - { name: ml-checkpoints, mountPath: /app/ML_after_CV/checkpoints, readOnly: true }
annotations:
  instrumentation.opentelemetry.io/inject-python: "true"
```

Four things worth calling out. **Distinct readiness and liveness endpoints** — readiness checks
dependency layers so a pod with unloaded models is pulled from the load balancer without being
killed; liveness is a bare process check, so a slow dependency never triggers a restart loop.
**Secrets by reference**, never in the manifest. **Checkpoints from a read-only PVC**, keeping model
weights out of the image and immutable at runtime. **OpenTelemetry auto-instrumentation** via
annotation — no application code change.

Kustomize overlays keep environments honest. Production:

```yaml
replicas: 3
strategy:
  type: RollingUpdate
  rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }   # zero-downtime
env:
  - { name: HELIOOPS_LOG_LEVEL, value: "WARNING" }    # quieter, cheaper logs
resources:
  requests: { cpu: 500m, memory: 1Gi }
  limits:   { cpu: "2",  memory: 2Gi }
```

`maxUnavailable: 0` means capacity never dips below the declared replica count during a deploy.

## 2.4 Infrastructure as Code + GitOps

**Terraform** (`infra/`) is split into reusable modules and per-environment roots:

```
infra/
├── modules/
│   ├── vpc/            main.tf, outputs.tf
│   └── eks-cluster/    main.tf, variables.tf
└── environments/
    ├── staging/main.tf
    └── production/main.tf
```

The EKS module parameterizes cluster version, node instance type, and min/desired/max scaling, names
resources `helioops-${var.environment}`, provisions IAM roles for cluster and node groups, places
nodes in private subnets, and outputs a ready-to-paste `aws eks update-kubeconfig` command.

**ArgoCD** (`argocd/`) closes the loop:

```yaml
source:      { repoURL: .../HelioOps, targetRevision: HEAD, path: k8s/production }
syncPolicy:
  automated: { prune: true, selfHeal: true }
  syncOptions: [ CreateNamespace=true, ApplyOutOfSyncOnly=true ]
```

`selfHeal` reverts manual `kubectl edit` drift back to the Git state; `prune` deletes resources
removed from Git. Git becomes the single source of truth, and rollback is `git revert` rather than an
SSH session.

## 2.5 Observability

**Structured logging.** `structlog` emits JSON in production (`HELIOOPS_LOG_FORMAT=json`) and
human-readable console output in development. Log lines are keyed events, not sentences:

```python
log.info("pipeline_completed", storm_id=storm_id, duration_seconds=round(duration, 3))
log.error("pipeline_error", storm_id=storm_id, error=str(exc))
```

That is directly queryable — filter by `storm_id`, aggregate `duration_seconds`, alert on
`pipeline_error` rate. Free-text logs cannot do any of that.

**Health checks** (`backend/health.py`) use a registry so new dependencies join without editing the
endpoint:

```python
health_collector.register("detection",    _check_detection)   # cv.detect.STORM_CONFIGS non-empty
health_collector.register("ml_models",    _check_ml)          # all 6 LightGBM checkpoints loaded
health_collector.register("genai_module", _check_genai)       # genai.impact_router importable
```

`/health/ready` returns **503** if any check fails, with a per-check breakdown — so a degraded pod is
removed from service and the reason is visible in the response body, not buried in logs.

**Metrics.** `/metrics` emits hand-rolled Prometheus exposition format — uptime, pipeline
requests/errors, average and p99 duration, detection and advisory counts, WebSocket connections. The
duration list is capped at 1000 samples and trimmed to the most recent 500, a deliberate bound so an
in-memory latency buffer cannot grow without limit. `k8s/base/servicemonitor.yaml` registers a
Prometheus Operator `ServiceMonitor` scraping `/metrics` every 30 s.

> **Known gap:** counters and the rate limiter live in process memory. Correct at one replica;
> at three, each pod reports and rate-limits independently. Redis-backed counters are the fix when
> horizontal scale becomes real.

## 2.6 Chaos engineering

`chaos/` holds three Chaos Mesh experiments, all scoped to the `staging` namespace and scheduled, not
manual:

| File | Kind | Schedule |
|---|---|---|
| `pod-kill.yaml` | `PodChaos`, `action: pod-kill`, `mode: one` | `@every 72h` |
| `network-delay.yaml` | `NetworkChaos` — injected latency | weekly |
| `cpu-stress.yaml` | `StressChaos` — CPU pressure | every 2 weeks |

`mode: one` kills a single pod, verifying that the remaining replicas absorb traffic and the
Deployment reschedules — the exact behaviour readiness probes and `maxUnavailable: 0` are supposed to
guarantee. Production is never targeted.

## 2.7 Runbooks

`runbooks/` — `high-error-rate.md`, `high-latency.md`, `detection-failure.md`, `groq-outage.md`.
Each carries alert name, severity, SLO impact, symptoms, copy-pasteable diagnostic commands,
tiered mitigation, and escalation. From `groq-outage.md`:

```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | head -5
kubectl logs -l app=helioops,component=backend --tail=200 -n production | grep "rate_limit\|429"
```

It also states blast radius honestly: if Groq is down, detection and ML still work, the verifier
cannot run (it has no advisory to check), and the frontend shows impact data without advisory cards.
That is the behaviour the UI's error boundaries and empty states were built for — the runbook and the
component tree agree with each other.

## 2.8 Configuration

`backend/config.py` uses Pydantic `BaseSettings`: every knob comes from an environment variable with
a typed default, documented in `.env.example`. Log level, log format, port, workers, CORS origins,
ChromaDB path, ML checkpoint directory, repository backend, and all Supabase settings are
environment-driven, so staging and production differ by configuration alone — never by code.

---

# 3. ML

Two distinct ML surfaces: **computer vision** for detection (`cv/`) and **supervised quantile
regression** for impact (`ML_after_CV/`). Both run on CPU.

## 3.1 CV detection — and why there is no CNN

The original design used a CNN (`cv/cmecnn.py`). It was **removed and replaced** by a deterministic
threshold detector. The reasoning, recorded in `cv/README.md`:

1. No labeled training data exists for coronagraph CME segmentation.
2. NASA DONKI already publishes authoritative, human-reviewed kinematics.
3. A deterministic detector is reproducible, testable, and needs no GPU.

This is the most important engineering judgement in the repository: the team removed the
machine-learning component from the vision layer because a threshold algorithm plus an authoritative
physics API produced *more defensible* output than a model trained on labels that do not exist.

### The 9-step algorithm (`cv/threshold_detector.py`)

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

Detection alone is not a storm assessment. `cv/fusion.py` combines four independent sources with a
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

`ML_after_CV/` predicts two operationally meaningful quantities from storm features:

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

### Measured results (`FINAL_RESULTS.md`)

| Metric | GPS L1 error | HF blackout |
|---|---|---|
| R² | 0.9858 | 0.9577 |
| MAE | 0.1463 m | 0.0320 (3.2%) |
| RMSE | 0.4420 m | 0.0433 (4.3%) |
| **PICP** (target 95%) | **96.40%** | **94.77%** |
| PINAW (interval width) | 0.0466 | 0.1942 |

PICP is the number that matters most. It says: when the model claims 95% confidence, the true value
falls inside the stated interval 96.4% / 94.8% of the time. The intervals are honest — and the low
PINAW says they are tight rather than trivially wide.

**Anchor test.** Fed the May 2024 G5 storm (CME 1800 km/s, Kp 9.0), the model predicted 17.50 m GPS
error (requirement: > 15 m) and 84.27% HF blackout probability (requirement: > 80%). This checks that
the model extrapolates into the rare-event regime rather than regressing toward the training mean —
the failure mode that makes an R² of 0.98 worthless in an emergency.

> **Stated honestly in the repo:** training data is **synthetic** (`data/synthetic_storms.csv`). The
> R² measures how well the model learned the physical proxy rules it was generated from. The
> documented next step is retraining on NASA OMNIWeb historical data.

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

`genai/impact_router.py` holds a hard-coded matrix. No model chooses severity:

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

## 4.3 Orchestration — AgentScope over LangGraph

`genai/orchestrator.py` uses AgentScope's `Msg` + `TextBlock` protocol with `asyncio` for
concurrency. Adding an industry is a one-line registry entry:

```python
_AGENT_REGISTRY: dict[str, type] = {
    "aviation": AviationAgent, "grid": GridAgent,
    "maritime": MaritimeAgent, "telecom": TelecomAgent,
}
```

The chosen rationale over LangGraph: a transparent message protocol with no graph-compilation step,
plain `asyncio.gather` fan-out instead of the `Send` API for dynamic dispatch, and a debuggable call
stack.

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

`genai/contracts.py` defines the typed hand-off between layers, so teams could build in parallel
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

| Suite | Tests | Covers |
|---|---|---|
| `tests/test_option_c.py` | 43 | CV detection, fusion, determinism |
| `tests/test_security.py` | 23 | Headers, validation, rate limiting, CORS |
| `tests/test_cv_preprocessing.py` | 21 | FITS/PNG loading, running difference |
| `tests/test_api_endpoints.py` | 16 | REST contract |
| `tests/test_pipeline.py` | 13 | End-to-end pipeline orchestration |
| `tests/test_middleware.py` | 12 | Middleware behaviour |
| `tests/test_retrieval.py` | 9 | RAG retrieval and similarity filtering |
| **Python total** | **≈137** | |
| `frontend/__tests__/` | **≈255** | 19 component suites + api, api-retry, ws-client, parseMetrics, types |

Frontend coverage is weighted toward the failure paths that matter in an operations console: 29 API
client tests, 24 WebSocket tests (reconnect backoff, malformed frames, listener isolation), 12
metrics-parsing tests, and dedicated error-boundary suites.

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
| ML trained on synthetic data | Reported R² measures rule-learning, not real-world accuracy | Retrain on NASA OMNIWeb historical data |
| CI steps end in `\|\| true` | Lint/test failures do not block merges | Drop `\|\| true` from `lint-backend` and `build-frontend` first — neither needs missing artifacts |
| Rate limiter + metrics in process memory | Incorrect beyond one replica | Redis-backed counters |
| Checkpoints and ChromaDB not in git | CI runs shallow; fallbacks engage | Shared object storage or an artifact step (tracked in `CI_CD_REQUIREMENTS.txt`) |
| `docker-build` has `push: false` | No CD; images never reach a registry | GHCR push with `CR_PAT` once secrets are in place |
| `maritime_kb` has 2 chunks | Thin retrieval ⇒ frequent `LOW_COVERAGE` | Ingest more IMO source material |
| In-memory repository is the default | Results lost on restart unless Supabase is configured | Set `RESULT_REPOSITORY=supabase` in deployed environments |
| Two demo storms wired for replay | Live mode exists but is not the demo path | Broaden `STORM_CONFIGS`, exercise `detect_live()` |

The gaps are documented in the repo rather than hidden, which is the right posture — but the CI
`|| true` and the in-memory repository default are the two that would bite first in a real
deployment.
