# HelioOps — Architecture Diagram Pack

Everything needed to draw HelioOps on a whiteboard, in draw.io, or on a slide —
and to answer the question a judge actually asks, which is never "what are the
boxes" but **"why is that box there and not a model call?"**

Source of truth: `backend/genai/ARCHITECTURE.md` (layer 3/4 detail) and
`docs/TECHNICAL_DEEP_DIVE.md` (all four layers). This file is the drawable
distillation of both.

---

## 0. The one-sentence version

> **Deterministic where safety demands it, generative only where language is
> needed, and a rule engine downstream of the model that rewrites unsafe values
> rather than flagging them.**

If a diagram communicates only that, it has done its job.

---

## 1. Hero diagram — the whole system

This is the one to put on the slide.

```mermaid
flowchart TD
    subgraph SRC["🛰️ SOURCES · free, public, authoritative"]
        direction LR
        S1["CCOR-1 / LASCO<br/><i>coronagraph FITS</i>"]
        S2["NASA DONKI<br/><i>human-reviewed CME</i>"]
        S3["GOES XRS<br/><i>flare class</i>"]
        S4["DSCOVR L1<br/><i>solar wind, Bz</i>"]
    end

    subgraph L1["① CV DETECTION · deterministic"]
        D1["9-step threshold detector<br/><b>no RNG · no weights</b>"]
        D2["fuse()<br/><i>0.4 CV · 0.2 flare · 0.2 Bz · 0.2 alert</i>"]
        D1 --> D2
    end

    subgraph L2["② ML IMPACT · quantile"]
        M1["6 LightGBM models<br/>q025 · q500 · q975 × 2 targets"]
        M2["GPS error + 95% CI<br/>HF blackout + 95% CI"]
        M1 --> M2
    end

    subgraph L3["③ AGENTIC ADVISORY · the only generative step"]
        R["impact_router<br/><b>hard-coded G-scale matrix</b>"]
        A1["aviation"]
        A2["grid"]
        A3["maritime"]
        A4["telecom"]
        KB[("ChromaDB · 1037 chunks<br/>ICAO · NERC · IMO · ITU · NOAA<br/><i>page-numbered</i>")]
        G["guardrails<br/><i>schema · citations · self-check · flags</i>"]
        R --> A1 & A2 & A3 & A4
        A1 & A2 & A3 & A4 --> KB
        KB --> G
    end

    subgraph L4["④ VERIFIER · zero LLM"]
        V["rule engine<br/><b>rewrites, does not flag</b><br/><i>ICAO {3,5,8,11,17} · GMDSS · GIC</i>"]
    end

    subgraph L5["⑤ DELIVERY"]
        API["FastAPI<br/>REST + WebSocket"]
        UI["React console<br/><i>live stream · clickable citations · per-agent chat</i>"]
        DB[("Supabase<br/><i>audit</i>")]
        API --> UI
        API -.optional.-> DB
    end

    SRC --> L1 --> L2 --> L3 --> L4 --> L5

    PRE["🔍 PRE-FLIGHT<br/><i>read-only dry run</i>"] -.inspects, never mutates.-> L1
    PRE -.-> API

    style L1 fill:#16213e,stroke:#3498db,stroke-width:2px,color:#fff
    style L2 fill:#16213e,stroke:#2ecc71,stroke-width:2px,color:#fff
    style L3 fill:#16213e,stroke:#9b59b6,stroke-width:2px,color:#fff
    style L4 fill:#16213e,stroke:#e74c3c,stroke-width:4px,color:#fff
    style L5 fill:#16213e,stroke:#f39c12,stroke-width:2px,color:#fff
    style SRC fill:#1a1a2e,stroke:#f39c12,color:#fff
    style PRE fill:#1a1a2e,stroke:#95a5a6,stroke-dasharray: 4 3,color:#fff
```

**Read it in one breath:** free public data goes in on the left, a deterministic
detector turns pixels into a typed `StormEvent`, six quantile models attach
uncertainty, four agents write language grounded in the real rulebooks, a rule
engine with no model in it corrects anything unsafe, and the operator gets a
numbered list they can trace back to a page in a PDF.

---

## 2. The diagram that wins the room

If you only draw one *detail*, draw this. It is the part nobody else has.

```mermaid
flowchart LR
    LLM["🤖 aviation agent<br/><i>gpt-oss-120b</i>"] -->|"'Switch HF to 21 MHz'"| RX["regex<br/><i>(\\d+)\\s*MHz</i>"]
    RX -->|21| SET{"21 ∈ ICAO NAT<br/>{3, 5, 8, 11, 17}?"}
    SET -->|"NO"| FIX["rewrite → 5 MHz<br/><i>G4+ default backup band</i>"]
    SET -->|"YES"| PASS["pass through"]
    FIX --> REC["VerifierCheck<br/><i>blocked · reason<br/>proposed · corrected_to</i>"]
    REC --> WS["stream to console<br/><b>operator sees BOTH</b>"]

    style LLM fill:#16213e,stroke:#9b59b6,color:#fff
    style SET fill:#1a1a2e,stroke:#f39c12,stroke-width:2px,color:#fff
    style FIX fill:#16213e,stroke:#e74c3c,stroke-width:3px,color:#fff
    style WS fill:#16213e,stroke:#2ecc71,stroke-width:2px,color:#fff
```

**The line to say out loud:** *"Anyone can put an LLM in front of a vector
store. Almost nobody puts a deterministic rule engine behind it that rewrites
the unsafe value and shows the operator what the model originally said."*

---

## 3. The seam — why the code survives four people

```mermaid
flowchart TB
    subgraph EDGE["Edge"]
        REST["POST /api/detect"]
        WS2["WS /ws/stream"]
        ASK["POST /api/ask"]
        SRC2["GET /api/kb/source"]
    end
    PIPE["backend/pipeline.py<br/><i>owns the adapter singletons</i>"]
    ADP["backend/adapters/<br/>detection · prediction · advisory<br/>verification · schema · repository"]
    subgraph DOM["Domain layers — never imported directly"]
        CV["backend.cv"]
        ML["backend.ml"]
        GEN["backend.genai"]
    end
    MEM[("InMemory")]
    SUP[("Supabase")]

    REST & WS2 --> PIPE --> ADP --> CV & ML & GEN
    ASK --> GEN
    ADP -.HELIOOPS_RESULT_REPOSITORY.-> MEM & SUP

    style PIPE fill:#16213e,stroke:#f39c12,stroke-width:2px,color:#fff
    style ADP fill:#16213e,stroke:#3498db,stroke-width:2px,color:#fff
    style DOM fill:#1a1a2e,stroke:#9b59b6,color:#fff
```

**The point:** the CV layer and the GenAI layer were built by different people
with different `StormEvent` schemas and **neither was rewritten**.
`adapters/schema_adapter.py` translates between them — integration cost paid
once, in one file, instead of smeared across four modules owned by four people.

The abstract `ports/` package was **deleted**: one interface per implementation
is ceremony. What actually enforces the boundary is a test
(`TestNoCircularImports`), not an inheritance tree.

---

## 4. Draw.io build guide

Import-ready settings so the drawn version matches the rendered one.

### Canvas

| Setting | Value |
|---|---|
| Page | A4 landscape / 1600 × 900 |
| Background | `#0A0917` (matches the product) |
| Grid | 10 px, snap on |
| Default font | Helvetica 12, `#E9E9F6` |
| Connector style | orthogonal, rounded 6, arrow `classic`, width 2 |

### Palette — one colour per layer, used consistently

| Layer | Stroke | Fill | Meaning to convey |
|---|---|---|---|
| Sources | `#F39C12` amber | `#1A1A2E` | outside our control, free |
| ① CV | `#3498DB` blue | `#16213E` | deterministic |
| ② ML | `#2ECC71` green | `#16213E` | quantified uncertainty |
| ③ Agents | `#9B59B6` violet | `#16213E` | the only generative step |
| ④ Verifier | `#E74C3C` red, **4 px** | `#16213E` | the safety gate — make it heaviest |
| ⑤ Delivery | `#F39C12` amber | `#16213E` | what the operator touches |
| Pre-flight | `#95A5A6` grey, **dashed** | `#1A1A2E` | read-only, side-car |

> Make the verifier's border visibly thicker than everything else. On a slide
> the eye lands on line weight before it reads a word, and the verifier is the
> thing you want it to land on.

### Shapes

| Element | draw.io shape |
|---|---|
| Layer group | Rounded rectangle, container, 12 px radius |
| Process step | Rectangle |
| Decision (`21 ∈ set?`) | Rhombus |
| Knowledge base / DB | Cylinder |
| External source | Rectangle, dashed top edge |
| Stream / async edge | Dashed connector |
| "never mutates" edge | Dotted connector, grey |

### Layout order (left → right, or top → bottom on a portrait slide)

```
SOURCES → ① CV → ② ML → ③ AGENTS ⇄ CHROMA → ④ VERIFIER → ⑤ DELIVERY
                                                   ↑
                                          PRE-FLIGHT (dashed, below)
```

Keep the four agents as a vertical stack inside the ③ container so the
**parallel fan-out is visible as a shape**, not just a label. That is the
cheapest way to show concurrency on a static diagram.

### Labels worth putting on edges

- Sources → ①: `cache-first, network fallback, stub floor`
- ① → ②: `StormEvent (the contract every layer reads)`
- ② → ③: `median + 95% CI`
- ③ → ④: `4 advisories, each with sources_cited`
- ④ → ⑤: `passed | passed_with_corrections | blocked`
- Pre-flight → ①: `stat() only — never fetch, never mkdir`

---

## 5. Numbers to put on the diagram

Judges remember figures attached to a picture. These are all measured, not
estimated.

| Figure | Value | Where it comes from |
|---|---|---|
| Knowledge base | **1037 chunks**, 5 collections, page-numbered | `rebuild_kb` |
| Interval calibration | **PICP 95.90 % / 94.21 %** vs nominal 95 % | `02_train_and_tune.py` |
| Interval width | PINAW 0.0369 / 0.1941 | same |
| Detection determinism | byte-identical output, **0 RNG** | threshold algorithm |
| Tests | **307 passing** | `pytest backend/tests` |
| ML checkpoints | 527 KB, **CPU only** | `backend/ml/checkpoints/` |
| End-to-end run | **65–80 s**, ~99 % of it Groq | measured, both storms |
| GPU hours | **0** | — |

---

## 6. Three questions the diagram should pre-empt

**"Where is the AI?"**
Exactly one box — ③. Detection is a threshold algorithm, routing is a lookup
table, impact is gradient boosting, verification is regex against a constant
set. The LLM does the one job LLMs are good at: turning a severity tier plus
retrieved regulation into readable numbered steps.

**"What stops it hallucinating a frequency?"**
Four things in series, and only the first is the model: RAG grounding →
guardrails (schema, citation resolution, self-check on a second model) → the
zero-LLM verifier that rewrites the value → an operator who can click the
citation and read the page it came from.

**"What happens when something is down?"**
Every arrow has a fallback and none of them raise. No frames → stub StormEvent.
No DONKI → cached physics. No checkpoints → conservative defaults (20 m GPS,
85 % HF). Groq exhausted → `ESCALATE TO SPECIALIST`, never a guess. Draw those
as small grey stubs hanging off each layer if you have room — "designed to
degrade" is a claim, and the stubs are the evidence.
