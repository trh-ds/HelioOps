# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-08-22 | Sessions logged: 4

## Identity
HelioOps — space-weather storm pipeline. Detects a CME from coronagraph imagery,
predicts sector impact, and generates verified operator advisories. Demo/replay
oriented: two anchor storms (2024-10-G4, 2024-05-G5) replay deterministically.

## Layout
Three folders, plus `.github/` (GitHub Actions requires it at the repo root).
```
backend/     FastAPI monolith: adapters/ cv/ ml/ genai/ embeddings/ data/ tests/
deployment/  Dockerfile.backend, Dockerfile.frontend, docker-compose.yml, supabase/
frontend/    Vite + React 18 SPA (static; three.js globe). Marketing pages only — no API calls yet.
```

## Stack & Commands
Python 3.12 + FastAPI backend, Vite/React 18 static frontend, ChromaDB RAG, LightGBM ML.
Everything is run from the repo root with `PYTHONPATH=.`.
```
pip install -r backend/requirements-dev.txt   # requirements.txt alone = serving only
pytest backend/tests -q                       # 244 tests
ruff check backend/ --ignore=E501,F403,E402
uvicorn backend.app:app --reload              # API on :8000
cd frontend && npm ci && npm run dev   # vite dev server; npm run build -> dist/
docker compose -f deployment/docker-compose.yml up --build
```
Offline pipelines (not needed to serve — their output is committed):
```
python -m backend.cv.data_ingestion.cache_fits --storm 2024-10-G4              # raw FITS
python -m backend.cv.data_ingestion.donki_client --prefetch --storm 2024-10-G4 # + flare, l1
python -m backend.cv.image_threshold_algorithm.preprocessing --storm 2024-10-G4
python -m backend.cv.storm_event_generator.detect --storm 2024-10-G4
python -m backend.embeddings.ingest_aviation                                   # + grid/maritime/impact
python backend/ml/01_data_generation_eda.py    # synthetic set + EDA plots (seed 42)
python backend/ml/02_train_and_tune.py         # regenerates the 6 checkpoints
python backend/ml/03_anchor_test.py            # physics gate; exits non-zero on failure
```

## Current State & Focus
- Works: all 4 layers end-to-end; 244 tests green; every REST + WS endpoint verified
  against a live uvicorn; ruff clean.
- 2026-08-21: repo collapsed to backend/ deployment/ frontend/. Dropped agentscope,
  langchain-core, langchain-groq, redis, fakeredis. All runtime paths resolve from
  `backend/paths.py`, never from cwd.
- No cached FITS/PNGs in repo (gitignored, too large) — `detect()` falls back to
  `backend/cv/stubs/*.json` until `cache_fits` + `preprocessing` are run.
- CV layer restructured 2026-08-21 into three stage packages (see Architecture).
- No cached FITS/PNGs in repo (gitignored, too large) — `detect()` therefore falls
  back to `ml/stubs/storm_event_*.json` until `cache_fits` + `preprocessing` are run.
- 2026-08-22: the ML layer is SYNTHETIC-ONLY and the real-data track is DELETED.
  `backend/ml/` is now 4 files + 6 checkpoints (764 KB, was 296 MB): the generator,
  the trainer, the anchor gate, `inference.py`. Retrained and re-verified end to end:
  PICP 95.9% GPS / 94.2% HF, anchor gate passes, both storms serve through the API.
  Gone: OMNI2 corpus, `features.py`, `00_fetch_omni.py`, `01_omni_eda.py`,
  `04_hpo_pods.py`, `PIPELINE.md`, `POD_SETUP.md`. It was permanently blocked on labels.
- 2026-08-22: backend is deploy-ready for HF Spaces — root `Dockerfile` + README
  front matter committed, production CORS origins are defaults, `/health/ready`
  now covers the KB. Not yet pushed to a Space.
- 2026-08-22: frontend LIVE on Vercel (project `frontend`, alias
  frontend-olive-six-50.vercel.app); custom domain heliops.dpdns.org not yet pointed.
  Backend not deployed. Runbooks: docs/DEPLOYMENT.md, docs/HOW_TO_DEPLOY_BACKEND.md.
- Chroma corpus fully populated: 918 chunks (aviation 242, maritime 214, telecom 195,
  impact_matrix 166, grid 101). Confirmed live through retrieval, not just sqlite.
- frontend/ is a marketing SPA (hardcoded copy in src/data.js) PLUS a live console:
  src/Dashboard.jsx drives src/api.js against /api/detect, /api/result and /ws/stream.
- 2026-08-22: pre-flight conflict check shipped — GET /api/preflight/{storm_id}
  predicts fallbacks/conflicts/quota before a run; Dashboard gates Run behind a
  confirm panel (summary + expandable findings, Run anyway / Cancel). Never
  hard-blocks; preflight failure starts the run directly.
- Flaky: `tests/test_retrieval.py` intermittently fails with a chromadb
  InternalError under full-suite ordering; passes when run alone. Not CV-related.

## Architecture
```
cv.data_ingestion  ->  cv.image_threshold_algorithm  ->  cv.storm_event_generator
  FITS/DONKI/XRS/L1     preprocess + threshold detect      fuse -> StormEvent
                                                                |
backend.pipeline --(ports/adapters)--> backend.ml.inference ---+--> genai.orchestrator
```
- One FastAPI process serves everything; there is no queue, worker, or second service.
- Hexagonal backend: `backend/pipeline.py` never imports `cv`/`ML_after_CV`/`genai`
  directly — it calls the four adapter instances it owns at module level
  (`detection_adapter`, `prediction_adapter`, `advisory_adapter`,
  `verification_adapter`). `app.py` imports those same instances from `pipeline`;
  there is exactly one of each in the process.
- `cv.storm_event_generator.fusion.StormEvent` is the contract every downstream
  layer reads. `backend/adapters/schema_adapter.py` maps it to `genai.models.StormEvent`.
- Every CV step has a fallback: missing PNGs -> stub, no detection -> stub bbox,
  no DONKI record -> stub speed, fuse() raises -> stub JSON. It never hard-fails.
- Detection is deterministic: no RNG, no trained weights. Same frames -> same bytes.

## File Map
```
cv/data_ingestion/cache_fits.py        — sync_ccor1 (S3), fetch_lasco (sunpy Fido), fetch_storm
cv/data_ingestion/donki_client.py      — fetch_cme_analyses, select_best_cme, cme_to_fields
cv/data_ingestion/flare_classifier.py  — classify_flare (R_SCALE_MAP), fetch_and_classify_flare
cv/data_ingestion/l1_client.py         — fetch_l1_wind (DSCOVR speed/Bz/density + ETA)
cv/image_threshold_algorithm/preprocessing.py       — load_ccor1_frame, running_difference,
                                                      preprocess, find_occulter_center,
                                                      batch_preprocess_directory (+CLI)
cv/image_threshold_algorithm/threshold_detector.py  — detect_cme_in_frame (9 steps),
                                                      detect_cme_in_sequence, annotate_and_save,
                                                      load_cached_sequence
cv/storm_event_generator/fusion.py     — StormEvent schema, fuse() confidence weighting
cv/storm_event_generator/detect.py     — STORM_CONFIGS, detect(), detect_live(), CLI entry
backend/app.py                         — FastAPI: /api/detect, /api/storms, /ws/stream, /health
backend/pipeline.py                    — adapter-driven 5-stage orchestration;
                                         owns the adapter singletons
backend/health.py                      — /health, /health/ready probes, /metrics counters
backend/preflight.py                   — run_preflight(): read-only pre-run conflict check
                                         (GET /api/preflight/{id}); stat-first, never fetches/mkdirs
backend/paths.py                       — BACKEND_DIR/DATA_DIR/CHROMA_DIR/STUBS_DIR/CHECKPOINT_DIR
backend/__init__.py                    — loads .env for every entry point
backend/genai/llm.py                   — the only Groq call (complete_json)
backend/embeddings/store.py            — embed_and_upsert; no cache layer
backend/embeddings/collections.py      — get_client(): the single ChromaDB client
backend/adapters/                      — detection/prediction/advisory/repository/schema adapters
ml/inference.py                        — LightGBM quantile regression on a StormEvent dict
ml/01_data_generation_eda.py           — generate_synthetic_data (seed 42), run_eda -> data/eda_plots
ml/02_train_and_tune.py                — Optuna 15 trials/quantile, GroupKFold on storm_id -> 6 pkls
ml/03_anchor_test.py                   — physics gate: G5 floor + quiet baseline + ordering; exits 1 on fail
Dockerfile                             — HF Spaces build (repo root); deployment/Dockerfile.backend is NOT used there
genai/orchestrator.py                  — RAG advisory generation + verifier + guardrails
ml/stubs/storm_event_*.json            — deterministic fallback StormEvents
tests/test_preflight.py                — peek/cache/conflict-rule/e2e preflight coverage
tests/test_pipeline.py                 — schema adaptation, full pipeline, WS event
                                         contract, standalone-import guard
tests/test_option_c.py                 — detector geometry, flare/DONKI math, fuse contract
tests/test_cv_preprocessing.py         — FITS fixes + batch png/diff layout round-trip
docs/DEPLOYMENT.md                     — HF Spaces + Vercel runbook, latency budget, failure modes
docs/HOW_TO_DEPLOY_BACKEND.md          — backend-only HF Spaces procedure: root Dockerfile, secrets, verify, troubleshoot
docs/CV_ML_QNA.md                      — judge-facing Q&A for CV + ML layers: 9-step detector, coupling
                                         functions, quantile/CQR methodology, glossary, hostile Qs
```

## Conventions
- CV imports are always the full stage path: `from backend.cv.storm_event_generator.detect import detect`.
  No re-export shims in `__init__.py` — the stage package docstrings are the map.
- Every external client is cache-first: cache hit -> disk, miss -> fetch + write,
  network failure -> stale cache -> hardcoded fallback dict. Never raise to the caller.
- Fallbacks log at WARNING and continue; only genuinely unrecoverable input raises.
- Keep argparse help/description strings ASCII (see Gotchas).
- Never hardcode a runtime path; import it from `backend.paths`.
- One Groq call site: `backend.genai.llm.complete_json`. Don't add an LLM client.
- Nothing under `backend/adapters/` may import `backend.pipeline` at module level
  (see Gotchas) — annotate with a string and import inside the function.
- Tests are plain pytest classes, no fixtures beyond `tmp_path` and `unittest.mock.patch`.

## Dependencies & Gotchas
- Windows console is cp1252: `→`/`—` in argparse help or `print()` raises
  UnicodeEncodeError. Logging survives (it substitutes), argparse does not.
- `batch_preprocess_directory()` writes `<root>/png/` + `<root>/diff/`;
  `load_cached_sequence()` reads exactly that. Both are gitignored. If the two
  drift apart, `detect()` silently degrades to the stub — pinned by
  `TestBatchLayoutRoundTrip`.
- `find_occulter_center()`'s radius must reach the `_meta.txt` sidecar or the
  detector falls back to `DEFAULT_OCCULTER_R = 80` for every frame.
- `cache_fits.sync_ccor1` shells out to the AWS CLI (`aws s3 sync --no-sign-request`);
  it is not a pip dependency. sunpy is only needed for the May 2024 LASCO storm.
- `load_ccor1_frame()` must keep its `target_size` default: the LASCO archive mixes
  512² and 1024² frames and `running_difference()` broadcasts across them.
- DONKI/GOES/DSCOVR endpoints need no auth. genai reads `GROQ_API_KEY` straight from
  `os.getenv` (populated by `backend/__init__.py`), NOT from `settings.GROQ_API_KEY` —
  settings uses the `HELIOOPS_` env prefix, so that field is always empty and its
  "not set" warning is spurious.
- Two `chromadb.PersistentClient` instances on the same directory produce
  "Error executing plan: Internal error" under concurrent access. `genai/retriever.py`
  and `embeddings/` share one via `collections.get_client()`.
- `self_check_hallucination()` swallows every exception, so a broken call site
  degrades to "self-check skipped" and the guard is off with no error anywhere.
  Pinned by `TestGuardrailsWiring`.
- `HELIOOPS_CHROMA_PERSIST_PATH` relative values resolve against the REPO ROOT.
  They used to resolve against the `backend/` package, so the `backend/data/chroma_db`
  shipped in .env/.env.example became `backend/backend/data/chroma_db` — a path Chroma
  happily CREATES. Every KB read 0, `retrieve_chunks()` swallowed it, and every
  advisory was ungrounded with nothing logged. It also made 9 of test_retrieval.py
  fail in a way that read as the known chromadb flake. Pinned by test_runtime_paths.py.
- `/health/ready` answers 503 with the same body as 200 when degraded. Frontend
  getHealth() must parse unconditionally — routing it through the throwing json()
  helper made every degraded state render as "unreachable" with no check pills.
- `check_rate_limit()` MUTATES on read (records the call). Preflight and anything
  else read-only must use `peek_rate_limit()` instead.
- The advisory field is `sources_cited`, NOT `citations`. Any RAG-liveness check
  grepping for `citations` reports a false failure.
- `/api/detect` takes 65-80s end to end, not the 8-15s once documented. Groq's
  gpt-oss-120b reasoning pass dominates; host CPU is nearly irrelevant.
- `backend/ml/0*.py` must keep the numeric prefix: `.dockerignore` excludes the
  training scripts by that glob. Renaming them silently ships them in the image.
- joblib shells out to `wmic` to count physical cores; Windows 11 build 26xxx does
  not ship it, so every ML run dumped a subprocess traceback. `backend/__init__.py`
  sets `LOKY_MAX_CPU_COUNT` to skip the probe.
- test_retrieval.py fails ~1 full-suite run in 3 with a chromadb segment-reader
  InternalError. Passes standalone (11/11), KB counts stay correct. Pre-existing
  chromadb-internal bug, mitigated but not fixed by the retry in collections.py.
- The ingest CLIs used to default `--base-dir`/cache paths to the CWD while `detect()`
  resolves everything from `backend.paths`. Running the documented repo-root commands
  therefore wrote FITS/JSON to `<root>/data/cached/` where the detector never looks, and
  detection silently degraded to the stub forever. All five now default to BACKEND_DIR.
- loky skips its `wmic` physical-core probe only when LOKY_MAX_CPU_COUNT is STRICTLY
  BELOW os.cpu_count(); setting it to the logical count left the warning + traceback
  firing. `backend/__init__.py` now sets logical//2.
- `test_api_endpoints.py::test_valid_storm_id_returns_200_or_500_or_429` runs the REAL
  pipeline against the REAL Groq API. With quota free the suite is ~45s; with the pooled
  keys saturated (or CI's placeholder GROQ_API_KEY) that one test drags the suite to
  9-12 min. It is the only live-network test in the suite.
- `_pick_key()` in genai/llm.py waits for TPM budget in an unbounded `while True`; the
  per-call timeout and GROQ_MAX_RETRIES do not bound it. With every key parked, /api/detect
  and /ws/stream stall for minutes with no error and no client-side timeout either.
- HF Spaces builds `Dockerfile` at the REPO ROOT. `deployment/Dockerfile.backend`
  is never picked up — the two must be kept in step by hand.
- The frontend API base is `VITE_API_URL` (NOT the Next-era `NEXT_PUBLIC_API_URL`, which
  nothing reads). Vite inlines it at BUILD time, so a runtime env var does nothing --
  pass it as a Docker build arg / Vercel build env. Empty default = relative paths, which
  is correct for the dev proxy and for single-origin deploys and WRONG on Vercel, where
  the catch-all rewrite answers /api/* with index.html and a 200.
- python:3.12-slim has no `curl` — container healthchecks must use python/node.
- `backend.pipeline` defines `PipelineResult` and imports the adapters; a module-level
  `from backend.pipeline import PipelineResult` in an adapter closes the loop and makes
  `import backend.pipeline` fail on its own — invisible under the full suite, which
  imports something else first. Pinned by `TestNoCircularImports`.
- `genai.stream_pipeline()` ends with its own `pipeline.complete`. `stream_full_pipeline`
  re-emits it as `pipeline.stage/advisory_generation/completed`; forwarded raw it would
  collide with the terminal event and the frontend would stop before verification.
  Pinned by `TestStreamEventContract`.

## Decisions Log
2026-08-22 — Deleted the real-data ML track outright rather than parking it — it was blocked on labels that no public dataset supplies in the required form (IONEX / GOES XRS+SEP), and a scaffolded pipeline that cannot be trained is indistinguishable in the tree from one that can. 296 MB and ~1,500 lines gone; the design notes survive in git history.
2026-08-22 — Training scripts resolve paths from backend.paths, not cwd — they used bare `data/` and `checkpoints/`, so README's documented `PYTHONPATH=. python backend/ml/02_train_and_tune.py` looked for a repo-root `data/` that never existed. Same bug class as the chroma path.
2026-08-22 — 03_anchor_test.py exits non-zero and goes through inference.predict() — it caught its own AssertionError and exited 0, so the physics gate could not gate anything; loading the pkls directly would also have let training/serving skew pass unnoticed. It now tests a quiet baseline too, since a constant model passes any single-storm floor.
2026-08-22 — Synthetic-trained LightGBM stays the ML layer of record — it is the only checkpoint set that exists, it is cheap to regenerate (~2 min), and its intervals are measurably calibrated. The R2 measures rule-recovery, not forecast skill; every doc now says so in those words.
2026-08-22 — Relative CHROMA path resolves against the repo root, rather than fixing the .env value — every environment's .env already holds the root-relative form, so moving the resolver is one line and fixes them all; moving the values is N edits that the next person re-breaks.
2026-08-22 — Production CORS origins are defaults in config.py, not deploy-only secrets — the variable REPLACES the list rather than extending it, so a forgotten or partial secret silently 4003s the WebSocket, which reads as a backend fault.
2026-08-22 — knowledge_base added as its own readiness check — genai_module was an import probe and returned True against a completely empty DB; the runbook's manual curl-grep was compensating for a missing automatic signal (and grepping the wrong field name).
2026-08-21 — Repo collapsed to backend/ deployment/ frontend/ — cv/genai/embeddings/ML_after_CV/data/tests all became backend subpackages; one deployable unit matches the serverless-monolith target.
2026-08-21 — Dropped agentscope and langchain for a 45-line groq wrapper — agentscope supplied a message envelope that a dict covers, langchain supplied two dicts and an attribute read; both are pure cold-start weight.
2026-08-21 — Deleted the EKS/Terraform/ArgoCD/chaos stack — a Kubernetes platform for two containers is the single largest cost item and contradicts scale-to-zero.
2026-08-21 — Deleted the Redis embedding cache — ingest is a one-shot offline op over 7 PDFs; the cache existed to speed up a command nobody runs twice.
2026-08-21 — Pipeline goes through the existing adapters instead of importing cv/ML/genai — the adapters already existed and were dead code; this makes the hexagonal claim in qna.md §313 true without adding a port layer (one interface per implementation is not worth it).
2026-08-21 — genai's pipeline.complete re-emitted as a stage event rather than renamed — the frontend already handles pipeline.stage, and advisory_generation previously never reported completed, so one change fixes both.
2026-08-21 — CV split into data_ingestion / image_threshold_algorithm / storm_event_generator — three named stages beat eight flat modules; import path now states which stage a symbol belongs to.
2026-08-21 — No compatibility re-exports after the move — call sites were updated instead, so there is exactly one import path per symbol.
2026-08-21 — batch_preprocess_directory writes png/ + diff/ subdirs — matches what load_cached_sequence and .gitignore already assumed; the old flat layout would have committed hundreds of PNGs.


2026-08-21 — XGBoost over LightGBM for the real ML layer — LightGBM cannot combine monotone constraints with the quantile objective, and monotonicity is what makes the G5 anchor pass structurally instead of by luck; xgboost was already installed, so this is a swap not a new dep.
2026-08-21 — One shared feature builder for train and serve, pinned by a test — training/serving skew is silent and fatal; two thin adapters into one physics function makes it structurally impossible. The test immediately caught that G->Kp quantisation loses resolution the model trains on.
2026-08-21 — 120h embargo instead of GroupKFold — measured autocorrelation (flow_speed r=0.72 at 24h, r<0.1 only past 120h) means group splitting alone leaks; at 120h the embargo also subsumes storm grouping since the longest event is 102h.
2026-08-21 — Outer holdout is a whole solar cycle (SC25) — SC23 has 2.6x the storm hours of SC24, so a random-year holdout overstates skill; this also makes both demo anchor storms genuinely out-of-sample.

2026-08-22 — Backend on HF Spaces, frontend on Vercel, direct CORS instead of a Vercel rewrite — a rewrite adds a hop, cannot proxy /ws/stream, and would split REST and WS across two paths; one origin + one CORS list covers both.
2026-08-22 — Free Space keeps its *.hf.space hostname — custom domains are Pro-only; the API URL lives in VITE_API_URL, so no user ever types it and a Cloudflare Worker proxy is unnecessary until api.heliops.dpdns.org is actually wanted.

## Changelog
2026-08-22 | Pre-flight conflict check + progressive-disclosure run gate | backend/{preflight,middleware,app}.py, backend/tests/{test_preflight,test_api_endpoints}.py, frontend/src/{api.js,Dashboard.jsx,dashboard.css} | Preflight is stat-first read-only (clients fetch+mkdir on miss); conflicts computed with the same parsers the run uses; UI warns but never hard-blocks
2026-08-22 | Delete the real-data ML track and HPO pods; make the synthetic pipeline actually runnable; scrub the docs | backend/ml/** (7 deletions), backend/paths.py, backend/__init__.py, backend/tests/test_runtime_paths.py, .gitignore, .dockerignore, README.md, docs/CV_ML_QNA.md, docs/HOW_TO_DEPLOY_BACKEND.md | One ML pipeline in the tree, not two — the deleted one could never be trained, and its presence made the repo overstate itself
2026-08-22 | Fix silent RAG death (chroma path), lock synthetic ML as the serving layer, make backend HF-deployable | backend/embeddings/config.py, backend/health.py, backend/ml/inference.py, backend/config.py, backend/tests/test_runtime_paths.py, Dockerfile, README.md, .dockerignore, docs/HOW_TO_DEPLOY_BACKEND.md | Readiness must assert the KB holds chunks, not that genai imports — an import probe cannot see an empty DB, which is the exact failure that shipped
2026-08-22 | Judge-facing CV+ML Q&A doc (58 Q, 13 sections, glossary, hostile questions) | docs/CV_ML_QNA.md, AGENTS.md | State shipped-vs-designed explicitly: shipped = 6 LightGBM models on 4,800 synthetic rows; designed = a real-data track blocked on labels (since deleted, see 2026-08-22). Hiding it loses more credibility than admitting it
2026-08-22 | Backend deploy guide; frontend live on Vercel; correct stale KB counts | docs/HOW_TO_DEPLOY_BACKEND.md, docs/DEPLOYMENT.md, frontend/.gitignore, AGENTS.md | Chroma corpus is fully populated (918 chunks) as of f967611 — the telecom_kb=0 / maritime_kb=2 finding was pre-merge and is void
2026-08-22 | Deployment plan: HF Spaces backend + Vercel frontend on heliops.dpdns.org | docs/DEPLOYMENT.md, AGENTS.md | HF free CPU (16 GB) hosts the unslimmed torch image as-is; slimming is a cold-start optimisation, not a prerequisite
2026-08-21 | Collapse to 3 folders; strip 5 deps; fix paths, chroma client, dead self-check, .env loading, docker healthcheck | backend/** (whole tree), deployment/**, frontend/next.config.mjs, .github/workflows/ci.yml, README.md | Reuse over rewrite: kept every algorithm, deleted the scaffolding around them
2026-08-21 | Wire CV->backend through adapters; fix WS event collision + circular import | backend/{pipeline,app,health,config}.py, backend/adapters/{repository,prediction}_adapter.py, cv/** (lint), tests/test_pipeline.py | Reuse the dead adapters rather than build ports; verified live against uvicorn on all 9 endpoints + WS
2026-08-21 | Restructure CV layer into 3 stage packages, fix batch/loader layout mismatch | cv/** (8 moves), backend/{pipeline,health}.py, backend/adapters/*, ML_after_CV/inference.py, tests/*, qna.md, requirements-cv.txt, .gitignore | Full import paths over re-export shims; write path and read path unified on png/ + diff/

## Archived Summary
2026-08-21 (w/e) — Real-data ML track built and then abandoned: NASA OMNI2 1996-2025 fetched
and documented, 38-feature physics builder with train/serve parity check, distributed Optuna
HPO pods with a two-laptop runbook. Never trainable — OMNI supplies every driver and no label.
Deleted 2026-08-22; recoverable from git history if IONEX/GOES label builders ever land.
2026-08-22 — CI's frontend job ran `npm run lint` and `npx tsc --noEmit`, neither of which exists in this repo (no eslint config, no tsconfig, no typescript dep) — both carried over from the deleted Next.js app, so the job could only ever fail. Replaced with `npm test`; added the root Dockerfile to the image matrix so the image HF Spaces actually builds is no longer the only untested one.

## Changelog
2026-08-22 | full-project verification sweep | backend/__init__.py, backend/cv/data_ingestion/{cache_fits,donki_client,flare_classifier,l1_client}.py, backend/cv/image_threshold_algorithm/preprocessing.py, frontend/src/api.js, .github/workflows/ci.yml | ingest CLIs resolve caches from BACKEND_DIR not cwd; frontend gets a VITE_API_URL base so a split Vercel/Spaces deploy can reach the API; CI frontend job made runnable; deleted the pre-refactor leftovers (root cv/ embeddings/ genai/ ML_after_CV/ tests/ data/, frontend/.next, .env.local, tsbuildinfo)
