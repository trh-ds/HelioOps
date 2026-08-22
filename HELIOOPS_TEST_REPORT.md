# HelioOps — End-to-End Test Report
**Date:** 2026-08-21 · **Scope:** unit, integration, user, domain-expert, security, build
**Result:** 399 tests passing · 8 deployment blockers · 27 further findings

> Placed outside the `HelioOps/` git repo on purpose — the repo's tracked `.md` files were
> deliberately deleted and this should not reintroduce one.

---

## Verdict — do not deploy yet

Application logic is sound and the safety architecture is real. The deployment path is
broken in eight independent places, each a first-run failure:

`kubectl apply -k` fails before a pod is scheduled → fix that, the pod never reaches Ready →
fix that, the browser bundle calls `localhost:8000` → fix that, the RAG knowledge base isn't
in the image.

None of it was caught because **every CI quality gate ends in `|| true`**.
All eight blockers are mechanical — roughly a day of work.

---

## What was actually run

| Discipline | Method | Result |
|---|---|---|
| Unit — backend | `pytest tests/` (9 files) | **144 pass**, 1 xfail, 0 fail |
| Unit — frontend | `vitest run` (24 files) | **255 pass**, 0 fail |
| Integration | Live FastAPI + Next.js, real WebSocket pipeline runs, both demo storms | Runs; 3 defects |
| User | Chrome against the running dashboard | Health page misleads |
| Domain expert | Verifier / matrix / ML features vs NOAA, ICAO NAT, NERC, IMO | 2 substantive gaps |
| Security | Path traversal, SQLi, XSS, oversized input, WS origin forgery | Holds; 1 origin bypass |
| Build & supply chain | `tsc --noEmit`, `next build`, `npm audit`, Docker/k8s static review | Blockers found |

**Two gaps were closed during testing to unblock the rest:**
- RAG store was empty (0 chunks in all 5 collections). Running the four ingest scripts reproduced
  the documented counts exactly (aviation 242, grid 101, impact_matrix 166, maritime 2) — this
  turned 6 failing retrieval tests green.
- The 6 ML checkpoints were absent. Retraining reproduced them (PICP 95.92% / 94.23% vs 96.40% /
  94.77% claimed, 469 KB) and the G5 anchor test passes at 18.20 m / 88.35%.

Both artifacts remain untracked/gitignored — that is blocker B3.

---

## Deployment blockers (8)

### B1 — The k8s overlays are not Kustomizations
`deployment/k8s/production/kustomization.yaml` and the staging equivalent both contain
`kind: Deployment`, not `kind: Kustomization`. They are strategic-merge patches wearing the wrong
filename, and neither references `../base`. `kustomize build` fails outright, so ArgoCD — pointed
at `path: deployment/k8s/production` — never syncs. The base manifests are applied by no path at all.

**Fix:** rename each to `backend-patch.yaml`; add a real `kustomization.yaml` per overlay with
`resources: [../base]` and `patches: [backend-patch.yaml]`.

### B2 — Referenced PVC does not exist
`backend-deployment.yaml` mounts `claimName: ml-checkpoints-pvc`. No PVC manifest exists in the
repo and the base kustomization doesn't list one. Pod stays `Pending` forever.

**Fix:** checkpoints are 469 KB — drop the PVC and bake them in (`COPY ML_after_CV/checkpoints/`).

### B3 — ML checkpoints are gitignored; every storm returns identical impact
`.gitignore:21` excludes `*.pkl`, so none of the 6 quantile models ship. `predict()` silently
falls back to fixed values, indistinguishable from a real prediction in the response schema.

    checkpoints loaded: 0 /6
    G5 extreme   GPS= 20.00m [8.00-35.00]  HF=0.8500
    G1 minor     GPS= 20.00m [8.00-35.00]  HF=0.8500
    IDENTICAL OUTPUT FOR G1 AND G5? True

    after retraining —
    G5 extreme   GPS= 18.74m [12.90-20.58]  HF=0.8758
    G1 minor     GPS=  1.37m [ 0.46- 4.07]  HF=0.4418    anchor test PASS

Cascades: `/health/ready` checks `len(_MODELS) >= 6`, returns **503 degraded** forever, readiness
probe never passes, Service ends up with zero endpoints. A 100% outage independent of B1/B2.

**Fix:** un-ignore and commit `ML_after_CV/checkpoints/*.pkl` (469 KB), or train during image build.
Same for `data/chroma_db/`, untracked for the same reason.

### B4 — Frontend bundle hardcodes localhost:8000
`NEXT_PUBLIC_API_URL` is inlined by Next at *build* time. `Dockerfile.frontend` declares no `ARG`
before `RUN npm run build`, so the bundle compiles with the fallback `http://localhost:8000`.
Setting it as a runtime env in k8s or compose has zero effect. Compounding: the configured value
`http://helioops-backend:8000` is cluster-internal DNS a browser can't resolve anyway.

**Fix:** the Ingress already routes `/api`, `/health`, `/metrics` to the backend on the same host —
set `NEXT_PUBLIC_API_URL=""` and use same-origin relative paths. Remove the misleading runtime env.

### B5 — The container has no knowledge base
`Dockerfile.backend` copies `backend/ cv/ genai/ ML_after_CV/ embeddings/ ml/ tests/` but never
`data/`. No Chroma store, no regulatory PDFs, and no volume supplies them.
`HELIOOPS_CHROMA_PERSIST_PATH` points at a nonexistent directory, so every agent retrieves
`[NO CONTEXT RETRIEVED]` — disabling anti-hallucination layers 1, 2, 3 and 6 at once.

**Fix:** `COPY data/ data/` with the ingested store baked in. Drop `COPY tests/` — fixtures don't
belong in a production image.

### B6 — Backend healthcheck calls a binary the image lacks *(static — Docker unavailable here)*
`HEALTHCHECK … CMD curl -f …` on `python:3.12-slim`. Slim Debian ships no `curl` and no `wget`,
and the Dockerfile installs neither. Container is permanently `unhealthy`, so `docker compose up`
hangs forever at `depends_on: condition: service_healthy` and the frontend never starts.
(The frontend's own `wget` check is fine — Alpine busybox provides it.)

**Fix:** `CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health/live')"`

### B7 — CORS allows only localhost
`CORS_ORIGINS` defaults to three localhost origins; the ConfigMap never overrides it. Deployed,
every browser API call is blocked and the WebSocket closes with 4003.

**Fix:** add `HELIOOPS_CORS_ORIGINS` to the ConfigMap with the real Ingress host.

### B8 — In-memory state behind three replicas
`RESULT_REPOSITORY` defaults to `memory`; the ConfigMap doesn't change it. Production runs
3 replicas × 2 workers = 6 processes. A `POST /api/detect` completing on one process is invisible
to the other five, so `GET /api/result` 404s roughly five times in six. The rate limiter is the
same module-level dict — the "one run per storm per 30s" guard is 6× looser than intended,
against a paid Groq quota.

**Fix:** `HELIOOPS_RESULT_REPOSITORY=supabase` (the adapter exists), or one replica until shared
state is wired. Move the rate limiter to Redis or accept per-pod semantics explicitly.

---

## Domain-expert findings

The deterministic architecture is the right one, and the severity matrix matches spec in all
20 cells. Two findings are substantive.

### D1 — Decimal frequencies bypass the ICAO check *(High)*
`_check_hf_frequencies` matches `(\d+)\s*MHz`. On `"5.5 MHz"` the integer group captures the
*fractional* digit and passes as though the value were 5. Same for 121.5 MHz — the VHF emergency
frequency, wrong by an order of magnitude for an HF fallback:

    blocked  g4 | 'Switch to 21 MHz'                  -> proposed=21 corrected=5   correct
    pass     g4 | 'Switch to 5.5 MHz'                 -> proposed=5              WRONG
    pass     g4 | 'Monitor 121.5 MHz guard frequency' -> proposed=5              WRONG

This is the single rule the design is advertised on. It works for the demo case (21 MHz) and fails
for any decimal — and decimals are what aviation frequencies look like.

**Fix:** match `(\d+(?:\.\d+)?)\s*MHz`, compare as float, replace by match span rather than
`str.replace` (which currently rewrites every occurrence of the value in the sentence).

### D2 — Routing ignores R-scale and S-scale *(High)*
`route_storm()` reads `storm.g_scale` and nothing else. G, S and R are independent NOAA scales with
different physics and arrival times: flare photons (R) ~8 minutes, SEP protons (S) 30 min–hours,
CME (G) 1–3 days.

    G1 + R5 (total HF blackout, sunlit side) + S5 (extreme radiation storm)
        aviation   severity=LOW       triggered=True
        grid       severity=LOW       triggered=True
        maritime   severity=NONE      triggered=False
        telecom    severity=NONE      triggered=False

During a total HF blackout the telecom and maritime agents are never spawned and aviation is rated
lowest tier — while polar HF is unusable and crew radiation dose is the live decision. R and S reach
the agent prompts but have no influence on severity or triggering. This inverts the headline
aviation use case, which ICAO NAT Doc 007 frames around polar-cap absorption and dose.

**Fix:** make the matrix take the max across scales — keep the G row, add R and S rows for
aviation/telecom/maritime, route on the highest resulting tier. Stays fully deterministic.

### D3 — Two of four verifier rules can only pass, never block *(Medium)*
`_check_gic_steps` and `_check_gmdss_channels` append `status="pass"` on a match and return empty
otherwise — no blocked branch. An invalid value produces *no check at all*.
`GMDSS_VALID_FREQUENCIES_KHZ` (9 entries) is defined and never referenced.

    ['pass']   'Initiate load shedding'         ok
    NO-CHECK   'Blow up the transformer'        unverified
    NO-CHECK   'Use Channel 99 for distress'    unverified
    NO-CHECK   'Broadcast on 9999 kHz'          unverified

Grid and maritime — half the industries — have no numeric enforcement.

**Fix:** extract channel/frequency tokens, test membership, emit `blocked` with a corrected value.
Wire up the unused kHz table.

### D4 — "Nothing was checked" is reported as "passed" *(Medium)*
When no rule matches, `verify_advisory` sets `status="passed"` and `verifier_conf = 1.0`. An
advisory nothing could verify is indistinguishable — in the API, the provenance chain and the
dashboard — from one that passed every rule at full confidence. With D3, most maritime and grid
advisories land here.

**Fix:** add an `unverified` status with confidence below 1.0; surface it distinctly.

### D5 — Two of nine ML features are hardcoded at inference *(Medium)*
`_extract_features` sets `geomag_lat_bin = 1` and `local_time_bin = 1` as literal constants. Both
vary in training. Geomagnetic latitude is the dominant driver of GPS scintillation — auroral-zone
error is far worse than mid-latitude — so the deployed model cannot express the distinction it was
trained on, and answers a narrower question than the published metrics claim.

**Fix:** plumb both through the API (the operator knows their region and local time), or drop them
and retrain so reported R² describes what ships.

### D6 — Telecom has no knowledge base; maritime has almost none *(High)*

| Collection | Chunks | Extracted text | State |
|---|---:|---:|---|
| aviation_kb | 242 | 488,709 ch | Good |
| impact_matrix_kb | 166 | 187,914 ch | Good |
| grid_kb | 101 | 168,071 ch | Good |
| maritime_kb | 2 | 4,016 ch | 6.3% unmapped-font garbage |
| telecom_kb | 0 | — | No ingest script exists |

There is no `ingest_telecom.py`. Because anti-hallucination layer 1 forbids training knowledge, the
telecom agent can only fabricate or escalate. Maritime extracted 4 KB from a 421 KB IMO GMDSS manual
— the cover page, containing `(cid:NN)` tokens — so its citations cannot be grounded in real
procedure text.

**Fix:** add an ITU-R / telecom source and ingest script. Re-extract the IMO PDF with OCR (it is
image-based). Add a post-ingest assertion that each collection exceeds a minimum chunk count.

---

## User & integration findings

The dashboard is genuinely well built — storm list, pipeline runner, live WebSocket streaming and
the staged progress rail all work. Three defects are operator-visible.

### U1 — The health page hides the failure it exists to show *(High)*
With ML models down, `/health/ready` correctly returns **503** with
`{"status":"degraded","checks":{"ml_models":false}}`. The typed API client throws `ApiError` on any
non-OK response, `Promise.allSettled` marks it rejected, `setReady` is never called, and the
`{ready && …}` block renders nothing.

Full rendered page text captured from the browser:

    SERVICE STATUS
    Status      ok          <- from /health, always 200
    Version     0.1.0
    PROMETHEUS METRICS
    UPTIME 8m · PIPELINE REQUESTS 0 · ERROR RATE 0.0% · WS CONNECTIONS 3
    [ dependency checks section absent — ml_models:false never shown ]

This exactly inverts the intent that a fallback be "visible, not silent". An operator reading
20 m GPS error has no way to learn it came from a hardcoded fallback.

**Fix:** readiness endpoints legitimately return 503 with a body — special-case it in `getReady()`,
parse and return the JSON on 503, render `degraded` as a warning state.

### U2 — The Advisory stage never leaves the spinner *(Medium)*
The backend emits `pipeline.stage` `status:"started"` for `advisory_generation`, and `"failed"` on
the error path — but never `"completed"` on success. Every other stage emits both. `buildSteps()`
leaves the step `active` forever, so a finished run shows *Advisory — ACTIVE* above
*Verification — DONE*, with the completion banner already displayed.

**Fix:** emit the missing `advisory_generation / completed` event in the success branch of
`stream_full_pipeline`.

### U3 — "undefined verified" rendered to the operator *(Medium)*
`StreamLog.tsx` renders `` `… ${event.total_advisories} advisories, ${event.total_verified} verified` ``
but the captured payload is:

    {"event": "pipeline.complete", "total_advisories": 3,
     "industries": ["aviation", "maritime", "telecom"],
     "timestamp": "2026-08-21T07:00:40Z"}          <- no total_verified field

Producing *"Pipeline complete — 4 advisories, undefined verified"* in the event stream.

**Fix:** add `total_verified` to the payload; make the WS event types a shared contract rather than
two hand-maintained shapes.

### U4 — A failed agent silently shrinks the advisory set *(Medium)*
Fault isolation works — one `agent.error` doesn't stop the others — but the missing industry then
vanishes with no operator-visible warning. A G5 run, where the matrix rates all four industries
CRITICAL, returned only three: `["aviation","maritime","telecom"]` — grid absent. The completion
banner reports the reduced count as if expected.

**Fix:** include `expected_industries` alongside `industries` in `pipeline.complete`; render the
difference as a warning.

### U5 — Ingress rewrite breaks every API route; no WebSocket path *(High, static)*
The Ingress sets `nginx.ingress.kubernetes.io/rewrite-target: /` with a plain `pathType: Prefix` on
`/api`. With no capture group, nginx rewrites `/api/detect/2024-10-G4` to `/` — the backend receives
the root path for every call. No rewrite is needed; the backend already serves those prefixes.

Separately, the WS client connects to `/ws/stream` and the Ingress has no `/ws` rule — it falls
through to the catch-all `/` and lands on the frontend. Live streaming is unroutable in Kubernetes.

**Fix:** delete the `rewrite-target` annotation; add a `/ws` path to `helioops-backend:8000`; raise
`proxy-read-timeout`; replace the `helioops.example.com` placeholder.

### U6 — WebSocket origin check is a prefix match *(Medium)*
`origin.startswith(o)` accepts any origin beginning with an allowed string, and an absent Origin
header skips the check entirely:

    OK        origin='http://localhost:3000'              intended
    OK        origin='http://localhost:3000.evil.com'     cross-site hijack
    REJECTED  origin='https://attacker.com'               403
    OK        origin=''                                   no gate

**Fix:** exact membership — `origin in allowed`. Decide deliberately whether a missing Origin should
be admitted; if non-browser clients need access, give them a token.

---

## Why none of this was caught

### P1 — Every CI quality gate is neutralised *(High)*
Lint, format, backend tests and TypeScript typecheck all end in `|| true`. Only `npm run build` and
the two image builds can fail the pipeline. The backend job runs 2 of 9 test files. The six
retrieval tests that failed on a clean checkout would never have turned the build red.

**Fix:** drop `|| true` from all four steps; run `pytest tests/`, not two files. Add a step
asserting checkpoint and Chroma collection counts are non-zero.

### P2 — The safety layer has zero tests *(High)*
Across all 9 backend test files:

    verifier            0 files, 0 lines   <- the correction engine
    impact_router       0 files, 0 lines   <- the severity matrix
    guardrails          0 files, 0 lines   <- the 10 anti-hallucination layers
    fusion                 4 files, 7 lines
    inference              2 files, 7 lines
    threshold_detector     2 files, 3 lines

The three deterministic components the entire "the LLM is boxed in" argument rests on are the three
with no coverage. D1, D3 and D4 are each a single assertion away from having been caught.

**Fix:** add `tests/test_verifier.py` and `tests/test_impact_router.py`. Table-drive them: the 20
matrix cells, and the frequency cases in D1 — including `5.5` and `121.5`.

### P3 — Six high-severity npm advisories *(Medium)*
`next@14.2.35` carries advisories for App Router XSS with CSP nonces, cache poisoning via RSC
cache-busting collisions, HTTP request smuggling in rewrites, and several DoS vectors. Also
`brace-expansion`, `js-yaml`, `nanoid`.

**Fix:** `npm audit fix` clears all six without a major bump. Add `npm audit --audit-level=high`
to CI, without `|| true`.

### P4 — Dead configuration that looks live *(Medium)*
The ConfigMap sets `HELIOOPS_ML_CHECKPOINT_DIR` and `backend/config.py` exposes `ML_CHECKPOINT_DIR`
— but `inference.py` hardcodes `Path(__file__).parent / "checkpoints"` and reads neither. Likewise
`next.config.mjs` rewrites `/api/*` to `http://localhost:8000` unconditionally, including in
production builds, where nothing listens on that port inside the frontend pod.

**Fix:** make `inference.py` read the setting; gate the dev rewrites on
`process.env.NODE_ENV !== 'production'`.

### Lower priority
- **Error responses echo raw input.** `"Invalid storm_id format: <500 chars>"` reflected verbatim — truncate and escape.
- **RLS grants `anon_read USING (true)`** on all 8 tables. If the frontend never talks to Supabase directly, drop the anon role.
- **Ingestion is not offline-safe.** The HuggingFace metadata probe raises `RuntimeError: Cannot send a request, as the client has been closed` instead of falling back to the local cache; `HF_HUB_OFFLINE=1` is the workaround. Pin it in the Dockerfile for hermetic builds.
- **Training script is CWD-dependent** — `02_train_and_tune.py` only works when run from inside `ML_after_CV/`.
- **`_load_models()` caches partial failure permanently** — a partially-loaded `_MODELS` dict short-circuits every later retry.
- **`RELOAD` defaults to `True`** in `config.py`. The ConfigMap overrides it, but a dev default in a prod settings class is one missing env var from a bad day.

---

## What holds up

- **Input validation is genuinely solid.** Path traversal, SQL injection, XSS payloads, a 500-char storm ID and encoded traversal all rejected at the boundary, with a defence-in-depth allowlist behind the regex. Held on both HTTP and WebSocket paths.
- **Fail-safe behaviour is correct.** With no Groq key, all four agents fail and the system returns `ESCALATE TO SPECIALIST` with `confidence_score: 0.0`, `validation_passed: false` and a `GENERATION_FAILED` flag — rather than a plausible-looking advisory. The hardest thing to get right, and it is right.
- **The severity matrix matches spec exactly** — all 20 G-scale × industry cells, trigger tiers as documented.
- **The ML training pipeline reproduces its published numbers.** PICP 95.92% / 94.23% vs 96.40% / 94.77% claimed; 469 KB checkpoints; G5 anchor test passes at 18.20 m / 88.35%. Quantile monotonicity via `sorted()` works as described.
- **RAG ingestion reproduces its documented chunk counts exactly** once the HF offline flag is set.
- **The frontend is in good shape.** 255 tests pass, `tsc --noEmit` clean, `next build` produces a standalone bundle with sensible route sizes (87 KB shared JS). WS backoff state machine and ErrorBoundary isolation behave as documented.
- **Streaming works end to end.** A full pipeline run over WebSocket delivered 47 ordered events — staged progress, per-agent thinking, advisories, completion — rendered live in the dashboard.

---

## Recommended order

### Day 1 — make it deployable
1. Un-ignore and commit the checkpoints and Chroma store (B3). Everything downstream needs Ready.
2. Rewrite the two overlay files as real Kustomizations; delete the PVC mount (B1, B2).
3. Fix both Dockerfiles — `COPY data/`, drop `COPY tests/`, replace the `curl` healthcheck (B5, B6).
4. Move the frontend to same-origin; fix the Ingress: drop `rewrite-target`, add `/ws` (B4, U5).
5. Set `CORS_ORIGINS` and `RESULT_REPOSITORY` in the ConfigMap, or drop to one replica (B7, B8).

### Day 2 — close the safety gaps
6. Fix the decimal-frequency regex; add table-driven verifier tests (D1, P2).
7. Give the GMDSS and GIC rules a blocked branch; add the `unverified` status (D3, D4).
8. Extend routing to R and S scales (D2) — the largest domain change, and the one that most affects
   what operators actually see.
9. Turn CI back on — remove every `|| true`, run the full suite, assert non-zero artifact counts (P1).

### Then
10. Fix the three streaming defects — missing `completed` event, `total_verified`, health page 503 (U1, U2, U3).
11. Source a telecom KB and OCR the IMO manual (D6), with a minimum-chunk assertion.
12. Resolve the hardcoded ML features (D5) so published metrics describe what ships.
13. Clear the npm advisories and tighten the WS origin check (P3, U6).

---

## A note on the architecture

None of the above criticises the design. The determinism/generative split, the correcting verifier,
the provenance chain and the conservative fallbacks are the right answers to this problem, and the
fail-safe path is implemented correctly. What this audit found is that the safety architecture is
under-tested at exactly the points where it is load-bearing, and that the deployment layer has never
been executed — every blocker is a first-run failure, not a subtle one.

---

## Changes made to the working tree during testing
All revertible; nothing committed.

- `HelioOps/.gitignore` — fixed `infra/**` → `deployment/infra/**` (broken by the earlier folder move)
- `HelioOps/data/chroma_db/` — populated by running the four ingest scripts (untracked)
- `HelioOps/ML_after_CV/checkpoints/` — 6 models trained (gitignored)
- Installed `langchain-groq` (was missing) and `frontend/node_modules`

## Caveats
- **B6** (`curl` absent from `python:3.12-slim`) and **B1 / U5** (kustomize, Ingress rewrite) are
  static findings — Docker, kubectl and kustomize are not available in this environment, so they
  were not executed. Everything else in this report was run and observed.
