# HelioOps GenAI Layer

LangGraph + Groq (Llama 3.3 70B) advisory generation pipeline. Takes a structured `StormEvent` from the NOAA detection pipeline and produces parallel, RAG-grounded, hallucination-resistant advisories for up to four industries simultaneously.

---

## Architecture

```
NOAA Alert (StormEvent)
        │
        ▼
┌───────────────────┐
│  classify_route   │  ← Deterministic G-scale → severity matrix (no LLM)
│  (LangGraph node) │    Identifies which industries are triggered
└────────┬──────────┘
         │  LangGraph Send() — parallel dispatch
    ┌────┴─────────────────────────────────┐
    │           │           │              │
    ▼           ▼           ▼              ▼
 Aviation     Grid      Maritime       Telecom
 Agent        Agent     Agent          Agent
    │           │           │              │
    └────┬─────────────────────────────────┘
         │  operator.add reducer — fan-in
         ▼
┌──────────────────────┐
│  compile_advisories  │  ← Aggregate all results, emit pipeline.complete
└──────────┬───────────┘
           │
           ▼
   List[AdvisoryOutput]  →  Backend DB + WebSocket + Notifications
```

### Per-Agent Pipeline (inside each `run_agent` node)

```
1. Build KB query from storm parameters (G-scale, Kp, S-scale, R-scale)
2. Parallel ChromaDB retrieval:
   ├── Industry KB  (e.g. aviation_kb)   — top 8 chunks
   └── Impact Matrix KB                  — top 4 chunks
3. Format context (labelled blocks with chunk_id + source + similarity)
4. Generate advisory (Groq Llama 3.3 70B, temperature=0, JSON mode)
5. Validate schema (Pydantic — fails fast on missing source_ref)
6. Check severity consistency (LLM cannot go below deterministic matrix)
7. LLM self-check (separate Groq call — judges if claims are grounded)
8. Compute confidence score (multi-factor)
9. Apply safety flags (non-blocking audit markers)
10. Retry loop (up to 3 attempts with error feedback injected)
11. Safe fallback (ESCALATE_TO_SPECIALIST if all retries fail)
```

---

## Anti-Hallucination Techniques

This is the core design constraint. Ten independent techniques work in layers:

| # | Technique | Where | Effect |
|---|-----------|-------|--------|
| 1 | **RAG-Only Grounding** | System prompt | LLM is explicitly forbidden from using training knowledge; must use ONLY provided context |
| 2 | **Citation Enforcement** | System prompt + Pydantic | Every `action_item` must have `source_ref` citing an exact document name or regulation code. Missing `source_ref` = validation failure = retry |
| 3 | **Retrieval Quality Gate** | `retriever.py` | Chunks below 0.35 cosine similarity are silently dropped before the LLM ever sees them |
| 4 | **JSON Schema Enforcement** | `guardrails.py` + Groq JSON mode | Groq forces valid JSON output; Pydantic validates field types, required fields, and value constraints |
| 5 | **Deterministic Severity Override** | `guardrails.py` | If LLM severity < deterministic matrix minimum, `SEVERITY_MISMATCH` flag is added (advisory not blocked — human reviewer is alerted) |
| 6 | **Source Existence Check** | `guardrails.py` | `sources_cited` list is cross-checked against the set of retrieved chunk sources. Unknown sources → `CITATION_GAP` flag |
| 7 | **LLM Self-Check** | `guardrails.py` | A second Groq call audits the generated advisory against the context, looking for specific numeric values / regulation codes not present in the context |
| 8 | **Retry with Error Injection** | `graph.py` | On any validation failure, the specific error messages are injected into the next prompt: "FIX THESE: ..." — the LLM sees its own mistake |
| 9 | **Confidence Score** | `guardrails.py` | Multi-factor score: base=avg retrieval similarity, bonus per cited source, penalty per missing citation, bonus for high-coverage context. Score exposed to reviewers |
| 10 | **Conservative Fallback** | `graph.py` | If all 3 retries fail, a `GENERATION_FAILED` advisory is emitted with a single action: "ESCALATE TO SPECIALIST". Never silently fails. |

### Confidence Score Formula

```
base_score          = average cosine similarity of all retrieved chunks
+ citation_bonus    = +0.02 per action_item with a verified source_ref
- citation_penalty  = -0.08 per action_item missing or with unverifiable source_ref
+ coverage_bonus    = +0.10 if base_score > 0.6 (context is high quality)

confidence_score    = clamp(score, 0.0, 1.0)
```

Advisories with `confidence_score < 0.50` receive the `LOW_CONFIDENCE` safety flag.

---

## File Structure

```
genai/
├── __init__.py            Public API: run_pipeline(), stream_pipeline()
├── models.py              All Pydantic models: StormEvent, AdvisoryOutput, ActionItem, etc.
├── config.py              All configuration knobs (LLM, RAG, retry thresholds)
├── impact_router.py       Deterministic G-scale → industry severity matrix
├── retriever.py           ChromaDB query wrapper with similarity filtering + context formatter
├── guardrails.py          Schema validation, severity check, LLM self-check, confidence scoring
├── graph.py               LangGraph StateGraph — nodes, edges, parallel dispatch, public API
└── prompts/
    ├── __init__.py
    ├── base.py            Shared: JSON output schema, format_advisory_prompt()
    ├── aviation.py        Aviation system prompt + KB query template
    ├── grid.py            Grid system prompt + KB query template
    ├── maritime.py        Maritime system prompt + KB query template
    └── telecom.py         Telecom system prompt + KB query template
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements-genai.txt
pip install -r requirements-data.txt  # ChromaDB, sentence-transformers
```

### 2. Environment variables

Add to `backend/.env` (or export directly):

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile       # default
GROQ_CHECKER_MODEL=llama-3.3-70b-versatile  # model used for self-check
```

### 3. Verify ChromaDB has data

The RAG layer requires populated ChromaDB collections. If not already done:

```bash
# From project root
python -m embeddings.ingest_aviation
python -m embeddings.ingest_grid
python -m embeddings.ingest_maritime
python -m embeddings.ingest_impact_matrix
```

---

## Usage

### Streaming (backend WebSocket integration)

```python
from genai import stream_pipeline, StormEvent
from datetime import datetime, timezone

storm = StormEvent(
    alert_id="NOAA-2024-05-10-G4",
    g_scale="G4",
    kp_index=8.3,
    s_scale="S2",
    r_scale="R3",
    estimated_arrival_utc=datetime(2024, 5, 10, 18, 0, 0, tzinfo=timezone.utc),
    peak_impact_window_start=datetime(2024, 5, 10, 20, 0, 0, tzinfo=timezone.utc),
    peak_impact_window_end=datetime(2024, 5, 11, 4, 0, 0, tzinfo=timezone.utc),
    raw_alert_text="NOAA/SWPC Geomagnetic Storm Watch: G4 conditions observed...",
)

async def handle_storm(storm):
    async for event in stream_pipeline(storm):
        # Forward to WebSocket clients
        event_type = event.get("event", "agent.thinking")
        await ws_manager.broadcast_all(make_ws_event(event_type, event))
```

### Batch / Replay

```python
from genai import run_pipeline, StormEvent

advisories = await run_pipeline(storm)

for advisory in advisories:
    print(f"{advisory.industry.value}: {advisory.severity.value} "
          f"(confidence={advisory.confidence_score:.2f}, "
          f"flags={[f.value for f in advisory.safety_flags]})")
    for item in advisory.action_items:
        print(f"  {item.step}. [{item.source_ref}] {item.action}")
```

---

## Backend Integration Points

### Wiring into `backend/app.py`

The backend's replay endpoint already emits `storm.detected` WebSocket events.
To wire the genai pipeline:

```python
# In the replay endpoint (or storm detection scheduler):
import asyncio
from genai import stream_pipeline, StormEvent

async def process_and_stream(storm: StormEvent, storm_db_id: str):
    async for event in stream_pipeline(storm):
        event_type = event.get("event", "agent.thinking")

        if event_type == "advisory.generated":
            # Persist to DB
            advisory_data = event["data"]
            async with state.db.acquire() as conn:
                await conn.execute(
                    """INSERT INTO advisories
                       (id, storm_event_id, industry, severity, status, confidence, advisory_json)
                       VALUES ($1,$2,$3,$4,'pending_review',$5,$6)""",
                    advisory_data["advisory_id"],
                    storm_db_id,
                    advisory_data["industry"],
                    advisory_data["severity"],
                    advisory_data["confidence_score"],
                    json.dumps(advisory_data),
                )
            # Create CRM ticket
            await create_crm_ticket(
                state.db,
                advisory_data["advisory_id"],
                advisory_data["industry"],
                advisory_data["severity"],
                storm.g_scale.value[1],  # numeric part of "G4"
                [a["action"] for a in advisory_data["action_items"]],
            )

        # Always broadcast to WebSocket clients
        await ws_manager.broadcast_all(make_ws_event(event_type, event))
```

---

## WebSocket Event Reference

Events emitted by `stream_pipeline` in chronological order:

| Event | When | Key Fields |
|-------|------|------------|
| `agent.thinking` (step: `routing_complete`) | After classify_route | `message`, `timestamp` |
| `agent.thinking` (step: `rag_start`) | Before ChromaDB query | `industry` |
| `agent.thinking` (step: `rag_done`) | After ChromaDB query | `industry`, chunk counts, avg similarity |
| `agent.thinking` (step: `gen_attempt_N`) | Before each LLM call | `industry` |
| `agent.thinking` (step: `self_check`) | Before hallucination check | `industry` |
| `agent.thinking` (step: `advisory_ready`) | After successful generation | `industry`, `severity`, `confidence`, `flags` |
| `advisory.ready` | Embedded in above | `advisory_id`, `industry`, `severity`, `confidence`, `flags` |
| `advisory.generated` | After any advisory (pass or fallback) | `data` = full AdvisoryOutput dict |
| `pipeline.complete` | After all agents complete | `total_advisories`, `industries` |

---

## AdvisoryOutput Schema

```json
{
  "advisory_id":             "uuid",
  "storm_event_id":          "NOAA-2024-05-10-G4",
  "industry":                "aviation",
  "severity":                "CRITICAL",
  "confidence_score":        0.72,
  "summary":                 "G4 storm (Kp=8.3) requires immediate HF frequency ...",
  "action_items": [
    {
      "step":        1,
      "action":      "Switch all NAT tracks above 70°N to SATCOM backup immediately.",
      "rationale":   "HF blackout expected on polar routes during G4 conditions.",
      "source_ref":  "nat_doc_007_2025.pdf",
      "time_window": "T+0 immediately"
    }
  ],
  "estimated_impact_window": "2024-05-10T20:00Z to 2024-05-11T04:00Z",
  "sources_cited":           ["nat_doc_007_2025.pdf", "noaa_space_weather_scales.txt"],
  "validation_passed":       true,
  "generated_at":            "2024-05-10T17:58:22Z",
  "model_used":              "llama-3.3-70b-versatile",
  "safety_flags":            [],
  "generation_errors":       []
}
```

### Safety Flags Reference

| Flag | Meaning | Action |
|------|---------|--------|
| `SEVERITY_MISMATCH` | LLM under-reported severity vs deterministic matrix | Human reviewer must verify severity |
| `HALLUCINATION_DETECTED` | Self-check found unsupported claims | Review action items carefully |
| `LOW_COVERAGE` | Fewer than 3 chunks above similarity threshold | KB may lack relevant content |
| `LOW_CONFIDENCE` | `confidence_score < 0.50` | Treat advisory as preliminary |
| `CITATION_GAP` | Some `source_ref` values not in retrieved chunks | Citations may be fabricated |
| `GENERATION_FAILED` | All 3 retries exhausted | Manual specialist consultation required |

---

## Configuration Reference

All tunable values in `genai/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Primary LLM for advisory generation |
| `GROQ_CHECKER_MODEL` | same as GROQ_MODEL | LLM for self-check (can use a lighter model) |
| `GROQ_TEMPERATURE` | `0.0` | Deterministic output for reproducibility |
| `GROQ_MAX_TOKENS` | `2048` | Max tokens per advisory generation call |
| `RAG_TOP_K` | `8` | Chunks retrieved from industry KB per query |
| `RAG_IMPACT_MATRIX_TOP_K` | `4` | Chunks retrieved from impact_matrix_kb |
| `RAG_MIN_SIMILARITY` | `0.35` | Cosine similarity threshold — chunks below are discarded |
| `RAG_LOW_COVERAGE_THRESHOLD` | `3` | Fewer valid chunks → LOW_COVERAGE flag |
| `MAX_RETRY_ATTEMPTS` | `3` | LLM generation retries before safe fallback |
| `SELF_CHECK_ENABLED` | `True` | Toggle LLM hallucination self-check |
| `SELF_CHECK_MAX_CHUNKS` | `5` | Max context chunks passed to self-check LLM |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | Below this → LOW_CONFIDENCE flag |
| `CITATION_BONUS` | `0.02` | Per-item confidence bonus for valid citations |
| `CITATION_PENALTY` | `0.08` | Per-item confidence penalty for missing citations |
| `COVERAGE_BONUS` | `0.10` | Bonus when context quality score > 0.6 |

---

## Design Decisions

### Why Groq + Llama 3.3 70B?
Fast inference (tokens/sec far above OpenAI), no per-token cost concern for 3-minute SLA, and Llama 3.3 instruction-following quality is comparable to GPT-4o-mini for structured JSON tasks. `temperature=0` ensures deterministic outputs.

### Why LangGraph?
Provides first-class support for parallel node execution via the `Send` API, built-in streaming via `astream`, and the state reducer pattern handles the fan-in from N parallel agents cleanly. Alternatives (Celery, asyncio.gather) lack the graph-level observability.

### Why separate self-check LLM call?
The generation LLM is in a "write" mindset; a separate call in a "critic" mindset catches consistency errors that the generator can't self-detect in a single pass. Cost tradeoff: 1 extra LLM call per industry, but prevents delivering factually unsupported advisories to operators making safety-critical decisions.

### Why deterministic routing + LLM advisory (not end-to-end LLM)?
The G-scale → severity matrix must be auditable and reproducible. Operators need to trust that a G4 storm always triggers CRITICAL aviation status — not sometimes HIGH depending on LLM mood. The LLM's job is only to translate severity + context into actionable steps.
