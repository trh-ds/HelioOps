# REFACTOR_MAP.md — HelioOps → private-helioops

Index of the collapse from the 18-folder `HelioOps` repo into the 3-folder
`private-helioops` monolith (`backend/`, `deployment/`, `frontend/`).

- **Source repo:** `C:\Users\Priyanshu\OneDrive\Desktop\All_projects\hackathon\HelioOps`
- **Target repo:** `C:\Users\Priyanshu\OneDrive\Desktop\All_projects\hackathon\private-helioops`
- **Refactor commits:** `4afbf84` (collapse + strip 5 deps), merged in `8af81c7`
- **Verified:** 2026-08-21

Companion docs: `AGENTS.md` (project memory), `context.md` (full narrative context),
`qna.md` (pitch/Q&A). This file is the *mapping* layer they don't cover.

---

## 1. Verdict

| Check | Result |
|---|---|
| Every `backend.*` import resolves to a real module | ✅ 0 missing targets (AST scan) |
| `ruff check backend/ --ignore=E501,F403,E402` | ✅ clean |
| `pytest backend/tests -q` | 122 passed, 2 failed, 31 blocked |
| Regressions vs. HelioOps baseline | ✅ **none** — baseline is 114 passed / 1 failed with identical causes |
| Public API surface (REST + WS) | ✅ identical, 5 routes + health |
| `frontend/src` and `frontend/__tests__` | ✅ byte-identical to HelioOps |
| Data assets (PDFs, alerts, chroma_db, ML checkpoints, stubs) | ✅ all carried over |
| Runtime path resolution | ✅ **improved** — see §5 |

The 2 failures + 31 blocked tests are a **local environment problem, not a refactor
problem**: `opentelemetry-exporter-otlp-proto-common` is too old for the installed
`chromadb`, and `astropy` is not installed. The same two failures reproduce in the
old HelioOps repo. Fix locally with:

```
pip install -r backend/requirements-dev.txt --upgrade
```

---

## 2. Directory mapping

### Moved

| HelioOps | private-helioops | Note |
|---|---|---|
| `genai/` | `backend/genai/` | + new `llm.py`; `README.md` dropped |
| `embeddings/` | `backend/embeddings/` | `cache.py` → `store.py` (see §4) |
| `ML_after_CV/` | `backend/ml/` | scripts, `inference.py`, `checkpoints/`, `data/` |
| `cv/cache_fits.py`, `donki_client.py`, `flare_classifier.py`, `l1_client.py` | `backend/cv/data_ingestion/` | new subpackage |
| `cv/preprocessing.py`, `threshold_detector.py` | `backend/cv/image_threshold_algorithm/` | new subpackage |
| `cv/detect.py`, `fusion.py` | `backend/cv/storm_event_generator/` | new subpackage |
| `ml/stubs/*.json` | `backend/cv/stubs/` | stubs now live beside the detector that reads them |
| `data/` | `backend/data/` | aviation, grid, maritime, impact_matrix, cached, chroma_db |
| `tests/` | `backend/tests/` | `README.md` dropped |
| `Dockerfile.backend` | `deployment/Dockerfile.backend` | build context is now the repo root |
| `Dockerfile.frontend` | `deployment/Dockerfile.frontend` | " |
| `docker-compose.yml` | `deployment/docker-compose.yml` | `context: ..` |
| `supabase/` | `deployment/supabase/` | 3 SQL files unchanged |
| `requirements-backend.txt` + `-genai.txt` + `-data.txt` | `backend/requirements.txt` + `backend/requirements-dev.txt` | split serving vs. offline |
| `frontend/` | `frontend/` | unchanged except `next.config.mjs` (see §6) |
| `.github/workflows/ci.yml` | same path | paths rewritten |

### Import rewrite rule

```
from cv.detect            → from backend.cv.storm_event_generator.detect
from cv.fusion            → from backend.cv.storm_event_generator.fusion
from cv.preprocessing     → from backend.cv.image_threshold_algorithm.preprocessing
from cv.threshold_detector→ from backend.cv.image_threshold_algorithm.threshold_detector
from cv.donki_client      → from backend.cv.data_ingestion.donki_client   (also l1_client,
                                                    flare_classifier, cache_fits)
from ML_after_CV.inference→ from backend.ml.inference
from genai.X              → from backend.genai.X
from embeddings.X         → from backend.embeddings.X
```

CLI entry points moved the same way, e.g.
`python cv/detect.py --storm 2024-10-G4` → `python -m backend.cv.storm_event_generator.detect --storm 2024-10-G4`.

---

## 3. Deleted, with impact

### Deleted — infrastructure (real capability loss, was never live)

| Path | Contents | Impact |
|---|---|---|
| `k8s/` | base + production/staging kustomizations, ingress, servicemonitor | No k8s manifests. Deploy story is now Docker/compose only. |
| `infra/` | Terraform: VPC + EKS modules, staging & production envs | No IaC. `.gitignore` still reserves `deployment/infra/**` — the intended home if restored. |
| `argocd/` | backend staging + production Application manifests | No GitOps. |
| `chaos/` | pod-kill, network-delay, cpu-stress experiments | No chaos suite. |
| `runbooks/` | detection-failure, groq-outage, high-error-rate, high-latency | No on-call runbooks. |

These were demo/deliverable artifacts, never applied to a cluster (`context.md` §1).
Restoring is a pure file copy — nothing in `backend/` references them.

### Deleted — architecture

| Path | Impact |
|---|---|
| `backend/ports/` (5 files) | Protocol/ABC layer removed. `backend/adapters/*` are now the contract themselves. Hexagonal *shape* kept (adapters still wrap cv/ml/genai), formal port interfaces gone. |
| `backend/adapter.py` | Superseded by `backend/adapters/` package. |
| `backend/run.py` | Launch is now `uvicorn backend.app:app` directly (README + Dockerfile CMD). |
| `embeddings/cache.py` | Redis/fakeredis embedding cache. Replaced by `backend/embeddings/store.py`. |

### Deleted — docs

`ARCHITECTURE_CHANGES.md`, `CI_CD_REQUIREMENTS.txt`, `pdf.md` (pitch deck),
`docs/notebooklm_script.md`, `docs/archived/{change_in_plan,ml_dl}.md`,
`docs/ml_research/eda_plots/*.png` (4 EDA charts),
`ML_after_CV/{README,FINAL_RESULTS,execution_report}.md`,
per-package `README.md` in `backend/`, `cv/`, `embeddings/`, `genai/`, `tests/`,
`frontend/dashboard_implementation.md`.

Root `README.md` shrank 24 KB → 2.4 KB. The ASCII 4-layer pipeline diagram, per-layer
detail, and endpoint tables are gone from it; `context.md` and `qna.md` cover most of
that content in the new repo. **Not covered anywhere new:** the ML EDA plots, the
LightGBM tuning results (`FINAL_RESULTS.md`), and the CI/CD requirements list.

### Not carried (intentional)

`cme_training_short_data/` — ~250 raw `.fts` training frames, gitignored in both repos.

---

## 4. New in private-helioops

| File | Why it exists |
|---|---|
| `backend/paths.py` | Single source of truth for every runtime path, anchored on `__file__`. Fixes the old split-brain where `embeddings/config.py` used `./data/chroma_db` and `genai/config.py` computed an absolute path. |
| `backend/genai/llm.py` | `complete_json()` over the raw `groq` AsyncGroq SDK. Replaces `langchain-core` + `langchain-groq`. |
| `backend/embeddings/store.py` | `embed_and_upsert()`. Replaces `embeddings/cache.py` — ingest is offline over a handful of PDFs, so the Redis cache bought nothing and cost 2 deps + a live-server probe on import. |
| `backend/__init__.py` | Now calls `load_dotenv(<repo root>/.env)`, so every entry point (tests, CLI scripts, uvicorn) sees the env — previously only `app.py` did. |
| `AGENTS.md` | Auto-maintained project memory. |
| `context.md` | Standalone full-repo context dump. |
| `qna.md` | Pitch / judge Q&A (supersedes `pdf.md`). |
| `.dockerignore` | Keeps tests, training scripts and raw frames out of the image. |
| `REFACTOR_MAP.md` | This file. |

### Dependencies stripped (5)

`agentscope`, `langchain-core`, `langchain-groq`, `openai`, `redis`/`fakeredis`.

Consequence — **the agent call signature changed**:

```python
# HelioOps  (agentscope Msg in, Msg out)
async def run_async(self, x: Msg) -> Msg

# private-helioops
async def run_async(self, storm: StormEvent, severity: str = "HIGH") -> dict
#   returns {"advisory": AdvisoryOutput, "stream_log": list[dict]}
```

`guardrails.self_check()` also lost its `llm: ChatGroq` parameter — it now calls
`complete_json(..., model=GROQ_CHECKER_MODEL)` internally. Any external code written
against the old `Msg` protocol will break; everything inside this repo is updated.

---

## 5. Behaviour changes worth knowing

1. **`base_dir` default flipped from cwd to the package root.**
   `run_full_pipeline(storm_id, base_dir=".")` → `base_dir: str | None = None`,
   and `detect()` resolves `base = Path(base_dir) if base_dir else BACKEND_DIR`.
   Detection now works regardless of the directory you launch from (and inside a
   container whose `WORKDIR` is not the repo root). This is a fix, not a break.

2. **Streaming pipeline accumulates non-fatal errors.**
   `run_full_pipeline_streaming` now appends to an `errors: list[str]` when ML
   prediction fails, instead of silently swallowing it.

3. **`GROQ_API_KEY` is read twice, by two mechanisms.**
   - `backend/genai/config.py` → `os.getenv("GROQ_API_KEY")` ✅ works
   - `backend/config.py` `Settings` has `env_prefix="HELIOOPS_"`, so
     `settings.GROQ_API_KEY` only picks up `HELIOOPS_GROQ_API_KEY` and otherwise
     stays `""` and emits `UserWarning: GROQ_API_KEY not set`.

   **Pre-existing bug, identical in HelioOps.** The warning is noise — the LLM layer
   works. CI's `env: GROQ_API_KEY: test-key` also only reaches the genai path.

4. **`telecom_kb` has no source documents.** `backend/data/` ships aviation, grid,
   maritime and impact_matrix PDFs but no telecom corpus. The chroma DB has 5
   collections and 511 embeddings across 4 populated segments. Pre-existing.

5. **Docstrings still name old paths.** `backend/adapters/__init__.py`,
   `backend/pipeline.py:27`, `backend/ml/inference.py:2`,
   `backend/cv/image_threshold_algorithm/threshold_detector.py:4` still say
   `cv/`, `ML_after_CV/`, `cv/cmecnn.py`. Cosmetic only — no code path affected.

---

## 6. Deployment & config

- `deployment/docker-compose.yml` builds with `context: ..` and `env_file: ../.env`
  — **compose fails without a `.env` at the repo root.** One now exists (§7).
- `deployment/Dockerfile.backend` copies only `backend/`, sets `PYTHONPATH=/app`,
  bakes the `BAAI/bge-small-en-v1.5` embedding model into the image, and health-checks
  with `python`, not `curl` (the slim image has no curl — the old healthcheck always
  failed, so compose never started the frontend behind `service_healthy`).
- `frontend/next.config.mjs` rewrites now read `process.env.BACKEND_URL` at request
  time instead of hardcoding `http://localhost:8000`, so one image works locally, in
  compose (`http://backend:8000`) and deployed. `output: 'standalone'` is set, which
  the frontend Dockerfile requires.
- CI (`.github/workflows/ci.yml`) runs `ruff check backend/`, `pytest backend/tests`,
  the frontend lint/tsc/build, then builds both images from `deployment/Dockerfile.*`.

---

## 7. Environment variables

`.env` has been created at the repo root from `HelioOps/.env`, carrying over all
secrets verbatim: `GROQ_API_KEY`, `HELIOOPS_SUPABASE_URL`, `HELIOOPS_SUPABASE_ANON_KEY`,
plus every server / logging / LLM / budget / storage knob. It is gitignored via `*.env`.

Two variables were **deliberately commented out** rather than remapped:

| Old value | Would become | Why commented |
|---|---|---|
| `HELIOOPS_ML_CHECKPOINT_DIR=ML_after_CV/checkpoints` | `backend/ml/checkpoints` | Relative → resolved against cwd. Leaving it unset lets `backend/paths.py CHECKPOINT_DIR` supply an absolute, cwd-proof path. |
| `HELIOOPS_CHROMA_PERSIST_PATH=data/chroma_db` | `backend/data/chroma_db` | Same — `paths.py CHROMA_DIR`. Setting it relative re-introduces exactly the split-brain bug `paths.py` was written to fix. |

Note `.env.example` still lists both uncommented with the new relative values. That
works when you run from the repo root, which is the documented workflow — but the
commented form in `.env` is strictly safer.

Two variables added for the container story: `BACKEND_URL`, `NEXT_PUBLIC_API_URL`.

---

## 8. Claude / agent context carried over

`HelioOps/.claude/` contained exactly one file — `settings.local.json`, a Bash
permission allowlist. No `CLAUDE.md` existed in HelioOps. The equivalent memory in
this repo is `AGENTS.md`.

The allowlist has **not** been written to `.claude/settings.local.json` here — writing
permission-config files is blocked. Paths in it need remapping when you add it:
`ls data/cached/...` → `ls backend/data/cached/...`, and
`pytest tests/...` → `pytest backend/tests/...`.

---

## 9. Known-broken, ranked

Resolved 2026-08-21 — see §11 for the GenAI work:

| # | Item | Resolution |
|---|---|---|
| ~~1~~ | `test_cv_preprocessing.py` wouldn't collect | `pip install astropy` — done |
| ~~2~~ | `test_retrieval.py` + 2 `test_pipeline.py` failures | otlp-proto-common upgraded — done |
| ~~3~~ | `UserWarning: GROQ_API_KEY not set` | `validation_alias` added in `backend/config.py` — done |

Still open:

| # | Item | Cause | Fix |
|---|---|---|---|
| 4 | **`imo_gmdss_2019.pdf` is not the GMDSS manual** — it is the 2-page publisher catalogue page for it (411KB, 3,804 chars, vs 160pp/417k chars for the aviation source). `maritime_kb` holds 2 chunks. Maritime advisories are grounded on a book advertisement. | Wrong file committed | Replace with the actual IMO GMDSS manual and `python -m backend.embeddings.rebuild_kb` |
| 5 | `telecom_kb` is empty — telecom advisories are grounded only by `noaa_space_weather_scales.txt` | No telecom source corpus in `backend/data/`, and no `ingest_telecom.py` | Add ITU-R / telecom continuity PDFs under `backend/data/telecom/` and write the ingest script alongside the other four |
| 6 | k8s / Terraform / ArgoCD / chaos / runbooks absent | Deleted in refactor | Copy back from `HelioOps/` into `deployment/infra/`, `deployment/k8s/`, etc. |
| 7 | ML EDA plots + `FINAL_RESULTS.md` have no home in the new repo | Deleted with `docs/` and `ML_after_CV/*.md` | Copy to `backend/ml/docs/` if the tuning story matters for the demo |

---

## 11. GenAI / agentic layer — 2026-08-21

Full write-up of what was broken and what changed lives in the commit and in
`backend/genai/config.py`, which carries the reasoning inline. Summary:

| Finding | Impact | Fix |
|---|---|---|
| `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` **decommissioned by Groq** — both 404 | Every advisory hit the ESCALATE_TO_SPECIALIST fallback. Layer was 100% dead against live Groq. | `openai/gpt-oss-120b` (advisory) + `openai/gpt-oss-20b` (self-check) |
| gpt-oss are reasoning models; CoT is billed against `max_tokens` | `finish_reason=length`, truncated JSON, confusing "sources_cited is empty" error | `GROQ_REASONING_EFFORT=low` + explicit truncation warning in `llm.py` |
| 4 agents fired ~26k tokens into an 8k/min TPM window, no 429 handling anywhere | 429 burned a retry attempt instantly; run degraded to fallback advisories | Per-model sliding-window token bucket + Retry-After-aware retry in `genai/llm.py`; `GENAI_MAX_CONCURRENCY=2` |
| Self-check failure forced a full regeneration | 3 of 4 industries flagged on the G5 storm → 3x token spend, 344s runs, same flagged output | `SELF_CHECK_BLOCKING=false` — flag, apply a confidence penalty, ship for review |
| `retrieve_chunks` swallowed every exception as "no context" | A transient GPU OOM produced *ungrounded* advisories citing the literal string `SOURCE UNAVAILABLE`, flagged only LOW_COVERAGE | Only the expected case (collection absent) is quiet; real failures log |
| Embedder pinned to CUDA with no fallback | GPU OOM took the whole GenAI layer down — every advisory starts with a RAG query | CPU fallback at load *and* encode; `HELIOOPS_EMBED_DEVICE` to force |
| Advisories indexed only under the verifier's rewritten id | `GET /api/advisory/{uuid}` always 404'd — and the UUID is what the dashboard renders and what `api.ts` documents | `_persist_result` indexes under both ids |

Measured on the G5 anchor storm: **344s → 86s**, 4/4 advisories schema-valid and
RAG-grounded. Both anchor storms verified end-to-end through a live uvicorn.
Suite is **176 passed, 1 xfailed**; 22 of those are new regression tests in
`backend/tests/test_llm_ratelimit.py`.

TPM pacing is a free-tier constraint, not a bug: ~12.7k tokens through an
8k/min ceiling has a hard floor near 90s. Raise `GROQ_TPM_LIMIT` on a paid key
and the pacing disappears.

---

## 10. Quick verification commands

```bash
pip install -r backend/requirements-dev.txt
PYTHONPATH=. python -m pytest backend/tests -q          # expect 154 passing once deps are fixed
PYTHONPATH=. python -m ruff check backend/ --ignore=E501,F403,E402
PYTHONPATH=. uvicorn backend.app:app --reload
curl -s -X POST http://localhost:8000/api/detect/2024-10-G4
docker compose -f deployment/docker-compose.yml up --build
```

---

## 12. Throughput vs accuracy — 2026-08-21

Question asked: would per-model API keys (a bigger budget) make a day-and-night
difference to accuracy or efficiency? Measured answer: **efficiency yes,
accuracy no.**

**Context window was never the constraint.** gpt-oss-120b offers 131,072
tokens; the largest prompt HelioOps builds is ~3,928 — **3% utilisation**.
Extra keys raise the tokens-per-minute ceiling, which is a *rate* limit, not a
*size* limit. No amount of budget "unlocks more context".

**Efficiency — real, roughly linear.** Groq meters TPM per `(key, model)`.
`GROQ_API_KEYS` now takes a comma-separated pool; `genai/llm.py` keeps one
bucket per `(model, key)` and routes each call to whichever has the most
headroom. One key ≈86s/storm, two ≈50s, three ≈35s, with no change to prompts
or models.

**Accuracy — no measurable gain.** Citation validity (fraction of action items
whose `source_ref` resolves to a genuinely retrieved chunk), G5 anchor storm:

| RAG_TOP_K | context budget | citation validity | mean input tokens | wall time |
|---|---|---|---|---|
| 3 | 1,900 | 95% | 2,288 | ~86s |
| 5 | 3,200 | 100% | 2,829 | ~129s |
| 8 | 6,000 | 100% | 3,624 | — |

One sample per cell, and a later K=5 run produced a `CITATION_GAP` the sampled
K=5 run did not — so treat 95→100 as noise. Defaults stay at K=3; raise to
K=5 / `MAX_PROMPT_TOKENS=4300` together once a key pool absorbs the latency.

**The actual accuracy ceiling is corpus coverage, and it is severe.** Of 511
embedded chunks, 96% are aviation + grid + impact-matrix:

```
aviation_kb        242    nat_doc_007_2025.pdf        160 pages
grid_kb            101    3 NERC PDFs                  18-38 pages
impact_matrix_kb   166    NOAA memo + NESDIS         4-193 pages
maritime_kb          2    imo_gmdss_2019.pdf        >>> 2 pages <<<
telecom_kb           0    (no source documents)
```

Two of four industries cannot use a larger budget because there is nothing more
to retrieve. Fixing the maritime source and adding a telecom corpus is worth
more than any rate-limit change.

**Guardrail bug found while measuring this.** `LOW_COVERAGE` compared the
*combined* industry + impact-matrix chunk count against a threshold of 3. Every
industry always receives 2 impact-matrix chunks (generic NOAA scale text), so
the effective floor was 2 and the flag could fire only for a completely empty
KB. Maritime's 2 real chunks + 2 generic reached 4, cleared the threshold, and
maritime shipped as the **highest-confidence, zero-flag industry in every run**
while being the least grounded. `apply_safety_flags` now takes
`industry_chunk_count` and measures industry coverage alone:

```
industry   industry  impact  combined   OLD rule      NEW rule
aviation          3       2         5   clean         clean
grid              3       2         5   clean         clean
maritime          2       2         4   clean         LOW_COVERAGE   <-- changed
telecom           0       2         2   LOW_COVERAGE  LOW_COVERAGE
```

**KB hygiene.** `backend/data/chroma_db/` is committed so a clone and the
Docker image have working RAG with no setup, but ChromaDB rewrites the segment
files on open, so they show modified after any test run. `.gitattributes` marks
them `binary -diff -merge` to keep that out of diffs, and
`python -m backend.embeddings.rebuild_kb` regenerates the whole DB from the
committed sources. `--verify` prints per-collection counts and flags empty or
thin collections, which is what surfaced the maritime problem.

---

## 13. Corpus rebuild — 2026-08-21

The two coverage gaps from §12 are closed. `maritime_kb` **2 → 174** chunks,
`telecom_kb` **0 → 164**. Total corpus 511 → 847 chunks.

### Maritime

`imo_gmdss_2019.pdf` was the 2-page publisher catalogue page for the GMDSS
Manual, not the manual (3,804 chars). It is deleted and purged from the
collection on re-ingest. The **IMO GMDSS Manual is a paid IMO publication** with
no legitimate free download; if you buy it, drop the PDF in
`backend/data/maritime/` and add it to `_DOCS` in `ingest_maritime.py`.

Replaced with the free ITU-R M-series — the international standards the GMDSS is
built on:

| Rec | Pages | Covers |
|---|---|---|
| M.541-11 | 49 | DSC operational procedures (distress alerting) |
| M.493-16 | 68 | DSC system technical characteristics |
| M.1467-1 | 18 | NAVTEX/MSI coverage prediction **including skywave propagation** |
| M.1173-1 | 4 | HF radiotelephony band plan |

### Telecom

New directory, new `ingest_telecom.py`, free ITU-R P-series:

| Rec | Pages | Covers |
|---|---|---|
| P.531-16 | 25 | Ionospheric propagation — TEC, scintillation, group delay |
| P.533-14 | 28 | HF circuit prediction — MUF collapse, absorption |
| P.372-17 | 36 | Radio noise floor |
| P.618-14 | 51 | Earth-space propagation — satellite scintillation |

Provenance and re-download steps: `backend/data/{maritime,telecom}/SOURCES.md`.
`NGA Pub. 117` was the preferred free maritime addition but `msi.nga.mil`
returned HTTP 503 throughout; worth retrying.

### Effect on advisories (G5 anchor storm)

| | before | after |
|---|---|---|
| maritime | conf 0.94, **zero flags**, grounded on a book advert | conf 0.59, `CITATION_GAP` raised honestly, cites M.541 with the real HF DSC distress frequency 8414.5 kHz and MF 2182 kHz |
| telecom | conf 0.92, always `LOW_COVERAGE`, only source `noaa_space_weather_scales.txt` | conf 0.90, **no flags**, cites P.618 |

Maritime's confidence *dropped* and that is the improvement: it was previously
high because nothing could detect that the source was worthless.

### Throughput

Three pooled keys → 24,000 TPM. Full G5 pipeline **86s → 19.5s**.

### Two concurrency bugs the speedup exposed

1. **`collections.py` had an unlocked singleton.** Every advisory issues two
   `retrieve_chunks` calls through `asyncio.to_thread`, so several threads
   entered `chromadb.PersistentClient()` at once and the losers saw
   `Could not connect to tenant default_tenant`. Retrieval returned nothing and
   the agent emitted an ungrounded advisory — grid came back at confidence 0.0
   citing `SOURCE UNAVAILABLE`. Latent while TPM limits serialised the agents;
   reproducible the moment the key pool let them truly run in parallel.
   Fixed with double-checked locking, matching `embedder.py`, plus a prewarm.
2. **429 handling defeated the pool.** On a rate limit the reservation was
   released, which made that bucket look *emptier*, so the router handed the
   same exhausted key straight back and the retry loop slept 60s per attempt on
   one key while the others idled. `_TokenBucket.penalise()` now parks the key
   for the server's reset window so the next acquire reroutes.

### Image size

The KB source PDFs are ~40MB and are inputs to the offline ingest only — at
runtime the API reads embedded vectors from `backend/data/chroma_db`. They are
excluded in `.dockerignore` and kept in git so `rebuild_kb` stays reproducible.

### Environment: the repo lives inside OneDrive

`C:\Users\Priyanshu\OneDrive\Desktop\...` is a synced directory. While OneDrive
uploads the ~16MB chroma DB after an ingest, chroma intermittently cannot open
an HNSW segment:

```
chromadb.errors.InternalError: Error executing plan: Internal error:
Error creating hnsw segment reader: Nothing found on disk
```

Roughly 1 run in 3 immediately after a rebuild, settling once sync completes.
The same interference made `git checkout -- backend/data/chroma_db` fail with
`unable to unlink ...: Invalid argument`.

`collections.query_collection()` now retries transient storage faults (3
attempts, backoff) and both retrieval paths go through it, so a lost race costs
250ms instead of producing an ungrounded advisory. The suite went from
intermittently 5-failed to 187-passed on three consecutive runs.

**This is a workaround, not a cure.** Recommended: move the repo outside
OneDrive, or mark the folder "Always keep on this device" and exclude
`backend/data/chroma_db` from sync.
