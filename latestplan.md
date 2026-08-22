# Pre-flight Conflict Check + Progressive Disclosure

## Context

The dashboard's Run button fires the full pipeline immediately: 65-80s, Groq quota burned, rate-limited to 1 run/30s per storm. Every degradation (stub detection, fallback L1 data, missing DONKI record, saturated keys, empty KB) is a silent `log.warning` the user only discovers after committing. The requested improvement: detect conflicts early and present them **before** the user commits, with detail shown gradually rather than all at once.

Delivery: a fast read-only `GET /api/preflight/{storm_id}` that predicts which fallbacks will fire, computes cross-source physical conflicts from the cached inputs, and reports system/quota state — plus a frontend confirmation panel (summary line, expandable findings, Run anyway / Cancel). Runs are never hard-blocked server-side (demo product). No new deps, no new WS events (`TestStreamEventContract` pins "pipeline.complete is last").

Scope decision (user-confirmed): **preflight only** — no provenance threading through `detect()`/`StormEvent`; that is the natural follow-up, deferred.

## Response schema

```json
{
  "storm_id": "2024-10-G4",
  "ready": true,
  "estimated_duration_s": 72,
  "findings": [
    {"id": "cv_stub_replay", "severity": "warn",
     "title": "Detection will replay the committed stub",
     "detail": "No preprocessed frames under data/cached/... Run cache_fits + preprocessing to detect from real frames."}
  ]
}
```

- `severity`: `info | warn | block`. `block` = the run will *fail* now (only the rate limiter produces it). `ready` = no block findings.
- `estimated_duration_s`: `round(avg(health._requester_metrics["pipeline_duration_seconds"]))`, fallback 70.
- All strings ASCII (Windows cp1252 gotcha).

## Findings catalogue

**Cache existence** (pure `Path.exists()`/glob off `STORM_CONFIGS`, `detect.py:40-69`; predicts the four fallback points at detect.py L132/146/164/211):
| id | fires when | sev |
|---|---|---|
| `cv_stub_replay` | `png_dir/png/*.png` or `png_dir/diff/*.png` empty (mirrors `load_cached_sequence` layout) | warn |
| `donki_cache_missing` / `flare_cache_missing` / `l1_cache_missing` / `alert_cache_missing` | cache file absent → live fetch attempt, else stub/fallback values | info |
| `l1_fallback_data` | l1 cache parses to `source == "DSCOVR (fallback defaults)"` | warn |

When `cv_stub_replay` fires, its detail notes the other caches won't even be read (detect() short-circuits wholesale at L132) — demote wording, keep the findings.

**Cross-source conflict rules** — computed only between sources whose caches exist, reusing the exact ingestion parsers the run uses (`cme_to_fields`, `fetch_and_classify_flare`, `fetch_l1_wind`) plus the always-present committed stub (its `scales.G` is what real runs use too, detect.py:199). **Load-bearing rule: stat the cache file first, only parse when it exists** — the clients are cache-first-then-NETWORK and `fetch_l1_wind` mkdirs on entry.
| id | rule | sev |
|---|---|---|
| `speed_disagreement` | `l1.speed > cme.speed * 1.10` (arriving faster than launch is unphysical) or `< cme.speed * 0.30` (exceeds drag-model deceleration) | warn |
| `arrival_eta_mismatch` | `abs(donki.arrival_estimate − (l1.measured_at + eta_minutes)) > 12h` (ballistic estimates carry ~10h MAE); skip if either timestamp unparseable | warn |
| `bz_northward_strong_g` | `stub.scales.G >= 3` and `l1.bz_nt >= 0` (northward Bz doesn't support the severity; fuse() drops its 0.2 term) | warn |
| `flare_r_mismatch` | `stub.scales.R >= 2` and `flare.r_scale == 0` → warn; else `abs(diff) >= 2` → info | warn/info |

Each rule must be silent on the committed stubs' own values (internal-consistency guard, pinned by test).

**System/quota:**
| id | source | sev |
|---|---|---|
| `rate_limited` | new `peek_rate_limit(storm_id)` > 0; detail carries wait seconds | block |
| `no_groq_key` | `GROQ_API_KEYS == [""]` | warn |
| `groq_tpm_low` | `sum(headroom)` across keys for `GROQ_MODEL` < 4000 via `await _bucket_for(model, key).headroom()` (llm.py:145) — detail must say the run *stalls* rather than fails, and headroom is process-local accounting | warn |
| `check_<name>_degraded` | each `False` from `health_collector.run()` (ml_models → "fallback prediction", knowledge_base → "ungrounded advisories", ...) | warn |

Never probe the Groq API itself — that burns the quota preflight protects.

## Steps

### 1. `backend/middleware.py` — non-mutating peek (~0.5h)
```python
def peek_rate_limit(storm_id: str) -> float:
    """Seconds until the next run is allowed. 0 = allowed now. Does not record."""
    return max(0.0, RATE_LIMIT_SECONDS - (time.time() - _pipeline_calls.get(storm_id, 0)))
```
(`check_rate_limit` at middleware.py:67 mutates on read — preflight must never call it.)

### 2. `backend/preflight.py` — new, ~150 lines (~4h)
`async def run_preflight(storm_id: str, base_dir: Path | None = None) -> dict` (base_dir mirrors `detect()` so tests use tmp_path unpatched). Small pure helpers:
- `_cache_findings(cfg, base)` — existence checks; parse each source only if its file exists; returns findings + parsed cme/flare/l1 (or None) + stub JSON.
- `_conflict_findings(stub, cme, flare, l1)` — the four rules, each skipping None inputs.
- `_system_findings()` — `health_collector.run()` loop + key presence (collector already swallows per-check exceptions, health.py:40-44, so the chromadb flake degrades to a warn, not a 500).
- `_quota_findings(storm_id)` — `peek_rate_limit` + per-key headroom.
- `_estimate_duration()` — from `backend.health._requester_metrics` (import precedent app.py:50).

First call pays `_load_models()` + Chroma counts (~1-2s); acceptable.

### 3. `backend/app.py` — endpoint (~1h)
`GET /api/preflight/{storm_id}`: `validate_storm_id` → 400; `storm_id in _available_storms()` → 404; **no** `check_rate_limit`, no `record_*` counters; return `await run_preflight(storm_id)`. Same gate order as `detect_storm` (app.py:137-182) minus the mutating pieces. Update module docstring endpoint list.

### 4. Backend tests (~4h)
`backend/tests/test_preflight.py` (plain pytest classes, tmp_path + mock.patch only):
- `TestPeekRateLimit` — 0 fresh; >0 after seeding `middleware._pipeline_calls`; peek leaves the dict unchanged (restore in teardown).
- `TestCacheFindings` — empty tmp_path → `cv_stub_replay`; fabricated `png/`+`diff/` PNGs → absent; **pin the no-network/no-mkdir guarantee** (empty tmp_path, assert nothing created).
- `TestConflictRules` — per rule: fires above threshold, silent below, silent on missing input; stub self-consistency (stub values fire nothing).
- `TestRunPreflight` — real repo state: schema keys, `ready is True`, `cv_stub_replay` present (today's normal); seed rate limit → `ready is False` + one block.

`backend/tests/test_api_endpoints.py` — new `TestPreflight` beside `TestDetectEndpoint` (L76): 200+schema, 400 invalid, 404 unknown, and non-mutation: after GET preflight, `middleware._pipeline_calls` lacks the storm (inspect the dict; do NOT POST detect to verify — that runs live Groq).

### 5. `frontend/src/api.js` (~0.5h)
```js
export const getPreflight = stormId => json(`/api/preflight/${encodeURIComponent(stormId)}`)
export const getHealth = async () => (await fetch(BASE + '/health/ready')).json()
```
The `getHealth` rewrite fixes the existing bug: `/health/ready` 503s when degraded, `json()` throws, Dashboard shows "unreachable" and the per-check pills never render. Body shape is identical at 200 and 503 — parse unconditionally; existing `.catch` still covers network failure.

### 6. `frontend/src/Dashboard.jsx` — gate + panel (~4h)
One state var `gate`:
```
idle(null) --click Run--> {phase:'loading', runner}
  --preflight ok--> {phase:'confirm', runner, data}
  --preflight FAILS--> start runner directly (gate never breaks the demo)
confirm --Run/Run anyway--> gate=null + startLive|startBatch
        --Cancel--> gate=null
```
- Rename `runLive`/`runBatch` (L245-282) bodies to `startLive`/`startBatch`; shared `requestRun(runner)` drives the gate.
- `PreflightPanel` between `.dash-controls` and the error banner. Progressive disclosure with existing primitives only:
  - Always-visible summary: `PRE-FLIGHT · 2 warnings · est ~72s` with severity-count `Pill`s (block→`bad`, warn→`warn`, info→`info`; same tones as `FLAG_TONE`, L16-40).
  - `<details>` "show N findings" (AdvisoryCard idiom L188-201): each finding = Pill + title, detail as `muted small`.
  - Primary button `Run` when zero warn/block, else `Run anyway`; plus `Cancel`. Block findings keep the button enabled (never hard-block); the rate-limit detail explains the coming 429.
- Panel shows on every run, detail collapsed by default. Run buttons disabled while `gate` non-null (in addition to `busy`). No StreamLog/describe/toneOf changes — no new WS events.

### 7. `frontend/src/dashboard.css` (~1h)
`.preflight` block reusing existing pill/banner/muted/small classes; only layout rules new.

## Verification (~3h; ~6h buffer)

```bash
pytest backend/tests/test_preflight.py -q
pytest backend/tests/test_api_endpoints.py -q -k "Preflight or Detect"
pytest backend/tests -q            # full suite; test_retrieval flake is known
ruff check backend/ --ignore=E501,F403,E402

uvicorn backend.app:app --reload
curl -s localhost:8000/api/preflight/2024-10-G4      # 200, cv_stub_replay warn, ready:true
curl -s localhost:8000/api/preflight/2024-05-G5
curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/preflight/bad-id      # 400
curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/preflight/2099-01-G5  # 404
curl -s -X POST -o /dev/null -w "%{http_code}" localhost:8000/api/detect/2024-10-G4  # not 429 (preflight didn't consume the slot)
curl -s localhost:8000/api/preflight/2024-10-G4 | python -c "import json,sys; d=json.load(sys.stdin); assert any(f['id']=='rate_limited' for f in d['findings']) and not d['ready']"  # within 30s of the detect

cd frontend && npm ci && npm run dev
# manual: Run live -> panel (summary + est) -> expand findings -> Cancel (nothing runs)
# -> Run live -> Run anyway -> stream starts. Stop uvicorn -> "unreachable" pill.
# Rename a checkpoint -> per-check pills now render in degraded state (503 fix).
```

## Files
- `backend/preflight.py` (new), `backend/tests/test_preflight.py` (new)
- `backend/middleware.py`, `backend/app.py`, `backend/tests/test_api_endpoints.py`
- `frontend/src/api.js`, `frontend/src/Dashboard.jsx`, `frontend/src/dashboard.css`

## Risks (accepted)
- Peek/commit race: preflight OK at t=29s can still 429 at commit — rare, existing 429 banner handles it.
- Groq headroom is process-local, soft signal — wording carries the caveat.
- Hidden network/mkdir in "read-only" preflight is the one real trap — exists()-first guard pinned by test.

## Deferred
Provenance threading (`degradations` list through detect()/StormEvent/PipelineResult) — natural follow-up if post-run verification of predictions becomes a demo talking point.

## After implementation
Update AGENTS.md: File Map (+preflight.py, +test_preflight.py), Current State, Changelog line; note the getHealth 503 fix in Gotchas.
