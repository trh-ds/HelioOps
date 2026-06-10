# HelioOps GenAI Layer (Layer III — Verified Advisory)

AgentScope + Groq (Llama 3.3 70B) advisory generation pipeline. Takes a structured `StormEvent` from the NOAA detection pipeline and produces parallel, RAG-grounded, hallucination-resistant advisories for up to four industries simultaneously.

**Owner:** Priyanshu | **Downstream consumer:** Tirth (Layer IV — Delivery)

---

## Architecture

```
NOAA Alert (StormEvent)
        │
        ▼
┌───────────────────┐
│  route_storm()    │  ← Deterministic G-scale → severity matrix (no LLM)
│  impact_router.py │    Identifies triggered industries + severity tier
└────────┬──────────┘
         │  asyncio.create_task() — parallel fan-out
    ┌────┴─────────────────────────────────┐
    │           │           │              │
    ▼           ▼           ▼              ▼
 Aviation     Grid      Maritime       Telecom
 Agent        Agent     Agent          Agent
    │           │           │              │
    └────┬─────────────────────────────────┘
         │  asyncio.gather — fan-in + event drain
         ▼
┌──────────────────────┐
│  Collect advisories  │  ← Aggregate AdvisoryOutput list
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  verify_advisory()   │  ← Deterministic rule engine (zero LLM calls)
│  verifier.py         │    ICAO HF bands, reroute lat, NERC GIC, GMDSS
└──────────┬───────────┘
           │
           ▼
  (VerifiedAdvisory, ProvenanceTrace)  →  Layer IV (Tirth)
```

### Per-Agent Pipeline (inside each `IndustryAgentBase.run_async()`)

```
1. Build KB query from storm parameters (G-scale, Kp, S-scale, R-scale)
2. Parallel ChromaDB retrieval via asyncio.to_thread:
   ├── Industry KB  (e.g. aviation_kb)   — top 8 chunks
   └── Impact Matrix KB                  — top 4 chunks
3. Format context (labelled blocks with chunk_id + source + similarity)
4. Generate advisory (Groq Llama 3.3 70B, temperature=0.1, JSON mode)
5. Validate schema (Pydantic — fails fast on missing source_ref)
6. Check severity consistency (LLM cannot go below deterministic matrix)
7. LLM self-check (separate Groq call — judges if claims are grounded)
8. Compute confidence score (multi-factor)
9. Apply safety flags (non-blocking audit markers)
10. Retry loop (up to 3 attempts with error feedback injected into prompt)
11. Safe fallback (ESCALATE_TO_SPECIALIST if all retries fail)
```

---

## File Structure

```
genai/
├── __init__.py                Public API: run_pipeline(), stream_pipeline()
├── models.py                  All Pydantic models: StormEvent, AdvisoryOutput, ActionItem, etc.
├── config.py                  All configuration knobs (LLM, RAG, retry thresholds)
├── impact_router.py           Deterministic G-scale → industry severity matrix
├── retriever.py               ChromaDB query wrapper (BGE-small embed_query, cosine filter, context formatter)
├── guardrails.py              Schema validation, severity check, LLM self-check, confidence scoring
├── contracts.py               Layer III→IV data contracts (§7.2–7.4 of imp.md)
├── verifier.py                Deterministic rule engine: ICAO HF, reroute lat, NERC GIC, GMDSS
├── orchestrator.py            AgentScope parallel pipeline — replaces graph.py
├── graph_langgraph_legacy.py  Archived LangGraph version (dead code, kept for reference)
├── agents/
│   ├── __init__.py
│   ├── base.py                IndustryAgentBase — full RAG+LLM+guardrails pipeline
│   ├── aviation.py            AviationAgent — AVIATION_SYSTEM_PROMPT + KB query
│   ├── grid.py                GridAgent — GRID_SYSTEM_PROMPT + KB query
│   ├── maritime.py            MaritimeAgent — MARITIME_SYSTEM_PROMPT + KB query
│   └── telecom.py             TelecomAgent — TELECOM_SYSTEM_PROMPT + KB query
└── prompts/
    ├── __init__.py
    ├── base.py                Shared: JSON output schema, format_advisory_prompt()
    ├── aviation.py            Aviation system prompt + KB query template
    ├── grid.py                Grid system prompt + KB query template
    ├── maritime.py            Maritime system prompt + KB query template
    └── telecom.py             Telecom system prompt + KB query template
```

---

## Anti-Hallucination Techniques

Ten independent techniques in layers:

| # | Technique | Where | Effect |
|---|-----------|-------|--------|
| 1 | **RAG-Only Grounding** | System prompt | LLM forbidden from using training knowledge; must cite ONLY provided context |
| 2 | **Citation Enforcement** | System prompt + Pydantic | Every `action_item` must have `source_ref`. Missing = validation fail = retry |
| 3 | **Retrieval Quality Gate** | `retriever.py` | Chunks below 0.35 cosine similarity dropped before LLM sees them |
| 4 | **JSON Schema Enforcement** | `guardrails.py` + Groq JSON mode | Groq forces valid JSON; Pydantic validates field types, required fields, value constraints |
| 5 | **Deterministic Severity Override** | `guardrails.py` | LLM severity < deterministic matrix minimum → `SEVERITY_MISMATCH` flag (advisory not blocked; human alerted) |
| 6 | **Source Existence Check** | `guardrails.py` | `sources_cited` cross-checked against retrieved chunk sources. Unknown source → `CITATION_GAP` flag |
| 7 | **LLM Self-Check** | `guardrails.py` | Second Groq call audits advisory against context for specific numeric values / regulation codes |
| 8 | **Retry with Error Injection** | `agents/base.py` | Validation errors injected into next prompt: "FIX THESE: ..." — LLM sees its own mistake |
| 9 | **Confidence Score** | `guardrails.py` | Multi-factor score exposed to reviewers (see formula below) |
| 10 | **Conservative Fallback** | `agents/base.py` | All 3 retries fail → `GENERATION_FAILED` advisory with single action: "ESCALATE TO SPECIALIST" |

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

## Deterministic Verifier (verifier.py)

Zero LLM calls. Runs after all agents complete. Rule checks per industry:

| Rule | Industry | Valid Set | Detection |
|------|----------|-----------|-----------|
| HF frequency | aviation, maritime | `{3, 5, 8, 11, 17}` MHz (ICAO NAT) | regex `(\d+)\s*MHz` |
| Reroute latitude | aviation | G3→78°N, G4→70°N, G5→60°N | regex `(\d+)\s*°?\s*N` |
| GIC operating step | grid | NERC TPL-007-4 Appendix B steps | keyword match |
| GMDSS channel | maritime | Valid GMDSS distress/working channels | keyword match |

**WOW #2 demo**: LLM writes `"21 MHz"` → regex catches it → `21 ∉ {3,5,8,11,17}` → `status="blocked"`, `corrected_to=5` (ICAO G4+ default backup) → action text corrected in-place → logged + streamed as WebSocket event.

```python
from genai.verifier import verify_advisory

verified, trace = verify_advisory(advisory, storm.model_dump(mode="json"), impact_assessment)
# verified.verifier.status == "passed_with_corrections"
# verified.verifier.checks[0].field == "hf_band"
# verified.verifier.checks[0].proposed == 21
# verified.verifier.checks[0].corrected_to == 5
```

---

## Layer III → IV Contracts (contracts.py)

Matches imp.md §7.2–7.4. Tirth's Layer IV stores and dispatches `VerifiedAdvisory`.

### §7.2 ImpactAssessment (Neal produces, Priyanshu consumes)
```python
class ImpactMetric(BaseModel):
    domain: str          # gps_pnt, hf_radio, grid_gic
    metric: str          # l1_position_error_m, blackout_probability, gic_risk_index
    value: float
    ci_low, ci_high, ci_level: Optional[float]
    qualifier: Optional[str]

class ImpactAssessment(BaseModel):
    storm_id: str
    model_version: str
    low_confidence: bool
    source: str          # "model" or "severity_floor"
    impacts: list[ImpactMetric]
```

### §7.3 VerifiedAdvisory (Priyanshu produces, Tirth consumes)
```python
class VerifiedAdvisory(BaseModel):
    advisory_id: str
    storm_id: str
    industry: str                  # aviation, grid, maritime, telecom
    severity: str                  # critical, high, medium, low
    numbered_actions: list[str]    # plain-text, verifier-corrected action strings
    timing_window: dict            # {"opens": ISO8601, "duration_min": int}
    technical_details: str
    cited_procedure: dict          # {"source": str, "ref": str}
    verifier: VerifierResult
    provenance_ref: str            # trace_id linking to ProvenanceTrace
    requires_human: bool
```

### §7.4 ProvenanceTrace (Priyanshu produces, Tirth renders)
```python
class ProvenanceTrace(BaseModel):
    trace_id: str
    advisory_id: str
    chain: list[ProvenanceStep]    # 6 steps: raw_data → detection → impact → retrieval → verifier → output
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements-genai.txt
pip install -r requirements-data.txt  # ChromaDB, sentence-transformers, pdfplumber
```

### 2. Environment variables

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile       # default
GROQ_CHECKER_MODEL=llama-3.3-70b-versatile
```

### 3. Verify ChromaDB has data

```bash
python -m embeddings.ingest_aviation
python -m embeddings.ingest_grid
python -m embeddings.ingest_maritime
python -m embeddings.ingest_impact_matrix
# telecom_kb intentionally empty — telecom agent produces LOW_COVERAGE advisory
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
    raw_alert_text="NOAA/SWPC Geomagnetic Storm Watch: G4 conditions observed...",
)

async def handle_storm(storm):
    async for event in stream_pipeline(storm):
        await ws_manager.broadcast_all(make_ws_event(event["event"], event))
```

### Batch / Replay

```python
from genai import run_pipeline, StormEvent

advisories = await run_pipeline(storm)

for advisory in advisories:
    print(f"{advisory.industry.value}: {advisory.severity.value} "
          f"(confidence={advisory.confidence_score:.2f}, "
          f"flags={[f.value for f in advisory.safety_flags]})")
```

### Verifier integration

```python
from genai.verifier import verify_advisory, verifier_stream_events

verified, trace = verify_advisory(advisory, storm_dict, impact_assessment_dict)

# Stream verifier events to WebSocket
for event in verifier_stream_events(verified.verifier.checks, advisory.industry.value):
    await ws_manager.broadcast_all(event)
```

---

## WebSocket Event Reference

Events emitted by `stream_pipeline` in chronological order:

| Event | When | Key Fields |
|-------|------|------------|
| `agent.thinking` (`routing_complete`) | After route_storm() | `message`, triggered industries |
| `agent.thinking` (`rag_start`) | Before ChromaDB query | `industry` |
| `agent.thinking` (`rag_done`) | After ChromaDB query | `industry`, chunk counts, avg similarity |
| `agent.thinking` (`gen_attempt_N`) | Before each LLM call | `industry` |
| `agent.thinking` (`self_check`) | Before hallucination check | `industry` |
| `agent.thinking` (`advisory_ready`) | After successful generation | `industry`, `severity`, `confidence`, `flags` |
| `advisory.generated` | Per advisory | `data` = full AdvisoryOutput dict |
| `pipeline.complete` | All agents done | `total_advisories`, `industries` |
| `verifier.check` (blocked) | Per blocked rule | `field`, `proposed`, `corrected_to` — red-glow in UI |
| `verifier.check` (pass) | Per passing rule | `field`, `proposed` |

---

## AdvisoryOutput Schema

```json
{
  "advisory_id":             "uuid",
  "storm_event_id":          "NOAA-2024-05-10-G4",
  "industry":                "aviation",
  "severity":                "CRITICAL",
  "confidence_score":        0.72,
  "summary":                 "G4 storm (Kp=8.3) requires immediate HF frequency switch...",
  "action_items": [
    {
      "step":        1,
      "action":      "Switch all NAT tracks above 70°N to SATCOM backup immediately.",
      "rationale":   "HF blackout expected on polar routes during G4 conditions.",
      "source_ref":  "nat_doc_007_2025.pdf",
      "time_window": "IMMEDIATE"
    }
  ],
  "estimated_impact_window": "12-24 hours",
  "sources_cited":           ["nat_doc_007_2025.pdf", "noaa_space_weather_scales.txt"],
  "validation_passed":       true,
  "generated_at":            "2024-05-10T17:58:22Z",
  "model_used":              "llama-3.3-70b-versatile",
  "safety_flags":            [],
  "generation_errors":       []
}
```

### Safety Flags

| Flag | Meaning | Required Action |
|------|---------|-----------------|
| `SEVERITY_MISMATCH` | LLM under-reported severity vs deterministic matrix | Human reviewer must verify severity |
| `HALLUCINATION_DETECTED` | Self-check found unsupported claims | Review action items carefully |
| `LOW_COVERAGE` | Fewer than 3 chunks above similarity threshold | KB may lack relevant content |
| `LOW_CONFIDENCE` | `confidence_score < 0.50` | Treat advisory as preliminary |
| `CITATION_GAP` | `source_ref` values not in retrieved chunks | Citations may be fabricated |
| `GENERATION_FAILED` | All 3 retries exhausted | Manual specialist consultation required |

---

## Configuration Reference

All tunable values in `genai/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Primary LLM |
| `GROQ_TEMPERATURE` | `0.1` | Low temp for reproducibility; >0 required for Groq JSON mode |
| `GROQ_MAX_TOKENS` | `2048` | Max tokens per generation call |
| `RAG_TOP_K` | `8` | Chunks from industry KB |
| `RAG_IMPACT_MATRIX_TOP_K` | `4` | Chunks from impact_matrix_kb |
| `RAG_MIN_SIMILARITY` | `0.35` | Cosine similarity threshold — chunks below discarded |
| `RAG_LOW_COVERAGE_THRESHOLD` | `3` | Fewer valid chunks → `LOW_COVERAGE` flag |
| `MAX_RETRY_ATTEMPTS` | `3` | LLM retries before safe fallback |
| `SELF_CHECK_ENABLED` | `True` | Toggle LLM hallucination self-check |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | Below this → `LOW_CONFIDENCE` flag |

---

## Design Decisions

### Why AgentScope instead of LangGraph?

AgentScope's `Msg` + `TextBlock` message protocol provides structured inter-agent communication without LangGraph's graph compilation overhead. Parallel fan-out via `asyncio.gather` + `asyncio.Queue` is more transparent and debuggable than LangGraph's `Send` API for dynamic dispatch. The agent registry (`_AGENT_REGISTRY`) makes adding/removing industries a one-liner.

### Why a deterministic verifier after the LLM?

LLMs hallucinate specific technical values even with RAG. The verifier is a zero-LLM rule engine that catches and corrects safety-critical mistakes (wrong HF frequencies, wrong reroute latitudes) before advisories reach operators. It's fast, fully auditable, and produces `ProvenanceTrace` records that Tirth's Layer IV can render.

### Why BGE-small-en-v1.5 + ChromaDB?

BGE-small is 384-dim, fast on CPU, and asymmetric (QUERY_PREFIX at query time, no prefix at index time) — outperforms MiniLM on retrieval benchmarks. ChromaDB PersistentClient is embedded with no server required. L2-normalized vectors stored = cosine similarity via `1 - dist/2` with zero extra computation.

### Why separate self-check LLM call?

Generation LLM is in "write" mindset. A separate call in "critic" mindset catches consistency errors the generator cannot self-detect in one pass. Cost: 1 extra Groq call per industry. Benefit: prevents factually unsupported advisories reaching operators making safety-critical decisions.

### Why deterministic routing + LLM advisory (not end-to-end LLM)?

The G-scale → severity matrix must be auditable and reproducible. Operators need certainty that G4 always triggers CRITICAL aviation status — not sometimes HIGH depending on LLM sampling. The LLM's only job: translate severity + KB context into actionable steps.
