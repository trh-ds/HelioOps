# HelioOps Backend

FastAPI server that bridges all four HelioOps layers into a single pipeline:

```
FITS imagery → CV Detection → ML Impact Prediction → GenAI Advisory → Deterministic Verification
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                           │
│                     backend/app.py :8000                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  POST /api/detect/{storm_id}  ──► run_full_pipeline()           │
│  GET  /api/storms             ──► list available + completed    │
│  GET  /api/advisory/{id}      ──► verified advisory + provenance│
│  GET  /api/result/{storm_id}  ──► full pipeline result          │
│  WS   /ws/stream              ──► real-time event streaming     │
│  GET  /health                 ──► health check                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    Pipeline (backend/pipeline.py)                │
│                                                                 │
│  Step 1: cv.detect.detect(storm_id)                             │
│          └─ Threshold CME detector + DONKI physics fusion       │
│          └─ Output: cv.fusion.StormEvent                        │
│                                                                 │
│  Step 2: ML_after_CV.inference.predict(storm_dict)              │
│          └─ LightGBM quantile regression (6 models)             │
│          └─ Output: GPS error + HF blackout with 95% CIs       │
│                                                                 │
│  Step 3: backend.adapter.adapt_storm_event(cv_event)            │
│          └─ Bridges cv.fusion.StormEvent → genai.models schema  │
│          └─ Maps G-scale→Kp, parses arrival times               │
│                                                                 │
│  Step 4: genai.run_pipeline(genai_event)                        │
│          └─ 4 parallel industry agents (AgentScope + Groq LLM)  │
│          └─ RAG from ChromaDB (aviation, grid, maritime, telecom│
│          └─ 10-layer anti-hallucination guardrails               │
│          └─ Output: AdvisoryOutput per triggered industry        │
│                                                                 │
│  Step 5: genai.verifier.verify_advisory(advisory, storm_event)  │
│          └─ Zero-LLM deterministic rule engine                  │
│          └─ Checks: HF frequencies, reroute latitudes, GIC ops  │
│          └─ Output: VerifiedAdvisory + ProvenanceTrace           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI application — REST + WebSocket endpoints, CORS |
| `pipeline.py` | `run_full_pipeline()` and `stream_full_pipeline()` — chains all 5 steps |
| `adapter.py` | Schema bridge: `cv.fusion.StormEvent` → `genai.models.StormEvent` |
| `run.py` | Entry point: `python -m backend.run` starts uvicorn on port 8000 |

## Setup

```bash
# Install dependencies
pip install -r requirements-backend.txt
pip install -r requirements-genai.txt
pip install -r requirements-data.txt

# Set Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# Start server
python -m backend.run
```

Server starts at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## API Reference

### `POST /api/detect/{storm_id}`

Run the full 5-step pipeline for a storm.

**Available storm IDs:** `2024-10-G4`, `2024-05-G5`

**Response:**
```json
{
  "storm_id": "2024-10-G4",
  "cv_event": { "storm_id": "...", "confidence": 0.91, "scales": {"G": 4, "S": 0, "R": 3} },
  "impact_prediction": {
    "gps_error_m": 12.81,
    "gps_error_ci_low": 6.59,
    "gps_error_ci_high": 13.28,
    "hf_blackout_prob": 0.898,
    "hf_blackout_ci_low": 0.657,
    "hf_blackout_ci_high": 0.927
  },
  "genai_event": { "alert_id": "2024-10-G4", "g_scale": "G4", "kp_index": 8.3 },
  "advisories": [ ... ],
  "verified_advisories": [ ... ],
  "provenance_traces": [ ... ],
  "errors": [],
  "completed_at": "2026-06-13T19:58:59Z"
}
```

### `GET /api/storms`

List available storm IDs and completed pipeline results.

### `GET /api/advisory/{advisory_id}`

Get a single verified advisory with its full provenance trace (6-step chain from raw data to output).

### `GET /api/result/{storm_id}`

Get the full pipeline result for a previously processed storm.

### `WebSocket /ws/stream`

Real-time pipeline streaming. Send:
```json
{"action": "run_pipeline", "storm_id": "2024-10-G4"}
```

Receive stream of events:
```json
{"event": "pipeline.stage", "stage": "detection", "status": "started"}
{"event": "pipeline.stage", "stage": "detection", "status": "completed", "data": {...}}
{"event": "pipeline.stage", "stage": "impact_prediction", "status": "completed", "data": {...}}
{"event": "agent.thinking", "industry": "aviation", "step": "rag_start", ...}
{"event": "advisory.verified", "advisory_id": "...", "industry": "aviation", ...}
{"event": "pipeline.complete", "total_advisories": 4, "total_verified": 4}
```

## Schema Bridge

The CV layer and GenAI layer use different `StormEvent` schemas. The adapter (`backend/adapter.py`) translates:

| CV Field | GenAI Field | Transform |
|----------|-------------|-----------|
| `storm_id` | `alert_id` | direct |
| `scales["G"]` (int) | `g_scale` (GScale enum) | `GScale(f"G{v}")` clamped [1,5] |
| `scales["S"]` (int) | `s_scale` (str or None) | `"S{v}"` if > 0 |
| `scales["R"]` (int) | `r_scale` (str or None) | `"R{v}"` if > 0 |
| derived from G | `kp_index` (float) | Parse from alert text or G→Kp map |
| `cme["arrival_estimate"]` | `estimated_arrival_utc` | ISO parse |
| `noaa_alert_raw` | `raw_alert_text` | direct |

## ML Inference

`ML_after_CV/inference.py` loads 6 LightGBM checkpoints and predicts:

- **GPS L1 Position Error** (meters) — median + 95% confidence interval
- **HF Radio Blackout Probability** (0–1) — median + 95% confidence interval

Features extracted from CV StormEvent: G-scale, Kp, Bz, solar wind speed, CME speed, CME width, R-scale.

Falls back to conservative defaults (GPS=20m, HF=85%) if checkpoints missing.

## Verification

The deterministic verifier (`genai/verifier.py`) checks every advisory against authoritative rulebooks:

- **ICAO HF frequencies**: Only {3, 5, 8, 11, 17} MHz allowed. LLM wrote 450 MHz → corrected to 5 MHz.
- **Reroute latitudes**: G3→78°N, G4→70°N, G5→60°N thresholds enforced.
- **NERC GIC steps**: Grid actions must reference valid operating procedures.
- **GMDSS channels**: Maritime actions checked against valid distress frequencies.

Output: `VerifiedAdvisory` + `ProvenanceTrace` (6-step audit chain).
