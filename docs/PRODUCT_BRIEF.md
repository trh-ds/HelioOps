# HelioOps — Product Brief

**What it is:** a real-time space weather operations platform that watches the Sun, predicts what a
solar storm will do to critical infrastructure, and hands operators regulator-cited, machine-verified
action lists — with a full audit trail from raw imagery to final instruction.

---

## 1. The problem

When the Sun throws a coronal mass ejection (CME) at Earth, four industries lose capability within
hours:

| Industry | What breaks | Consequence |
|---|---|---|
| **Aviation** | HF radio over polar routes, GPS accuracy, crew radiation dose | Polar tracks close, flights reroute or cancel |
| **Power grid** | Geomagnetically induced currents (GIC) in transformers | Transformer heating, voltage instability, blackout risk |
| **Maritime** | GMDSS distress comms, GNSS positioning | Degraded safety-of-life comms in remote waters |
| **Telecom** | HF/satellite links, timing signals | Link outages, timing drift |

Today the raw signal exists and is free — NOAA/SWPC alerts, NASA DONKI CME kinematics, GOES X-ray
flare data, DSCOVR L1 solar wind. What does **not** exist is the last mile:

1. **Raw alerts are not decisions.** "G4 Watch, Kp 8.3" tells a dispatcher nothing about which of
   their 40 polar flights to move, or which frequency to fall back to.
2. **The rulebooks are PDFs.** The actual procedures live in ICAO NAT Doc 007, NERC TPL-007-4, IMO
   GMDSS 2019 — hundreds of pages, per industry, that nobody reads at 3am during an event.
3. **Generic LLMs are unsafe here.** Ask a chatbot for an HF fallback frequency and it will confidently
   invent one. A wrong frequency in an aviation advisory is not an embarrassing hallucination, it is a
   safety incident.
4. **Nothing is auditable.** Regulated operators cannot act on an output they cannot trace back to a
   cited procedure and a measured input.

## 2. What we built

A five-stage pipeline that turns coronagraph imagery into verified, cited, per-industry advisories —
streamed live to a dashboard and persisted for audit.

```
Solar imagery (CCOR-1 / LASCO)
        │
   ①  CV DETECTION          deterministic CME detector + NASA DONKI physics
        │                   → StormEvent: confidence, G/S/R scales, CME kinematics
        ▼
   ②  ML IMPACT             LightGBM quantile regression (6 models)
        │                   → GPS error ±95% CI, HF blackout probability ±95% CI
        ▼
   ③  AGENTIC ADVISORY      4 industry agents in parallel, RAG-grounded on the real
        │                   rulebooks, 10 layers of anti-hallucination control
        ▼
   ④  DETERMINISTIC VERIFIER  zero-LLM rule engine — ICAO HF bands, reroute latitudes,
        │                     NERC GIC steps, GMDSS channels. Corrects, does not just flag.
        ▼
   ⑤  DELIVERY              FastAPI REST + WebSocket → Next.js operations dashboard
                            → Supabase Postgres for persistence and audit
```

Every advisory that reaches an operator carries a **6-step provenance trace**:
`raw_data → detection → impact → retrieval → verifier → output`.

## 3. Why it is built this way

Four design decisions define the product. Each one trades cleverness for defensibility.

### Deterministic where safety demands it, generative only where language is needed

The G-scale → industry-severity matrix is a **hard-coded lookup table**, not a model output. A G4
storm always produces CRITICAL aviation status — never HIGH because a sampler rolled differently.
Detection is a **threshold algorithm with no RNG**: the same input frame produces byte-identical
output every run. The LLM's only job is the part LLMs are actually good at: turning a severity tier
plus retrieved regulatory text into readable, numbered steps.

### The LLM is never the last word

After generation, a **zero-LLM rule engine** re-checks every advisory against the authoritative
constants. The canonical example: an agent writes "switch to 21 MHz". The verifier's regex catches
the number, tests it against the ICAO NAT set `{3, 5, 8, 11, 17}`, rejects it, rewrites the action
text to 5 MHz, records the correction, and streams it to the dashboard as a visible block event.
The operator sees both what the model proposed and what the rules enforced.

### Physics from authoritative sources, not learned from thin air

CME speed, angular width and direction come from **NASA DONKI**, a human-reviewed database. Flare
class comes from **GOES XRS**. Solar wind Bz and speed come from **DSCOVR at L1**. We did not train a
regressor to guess numbers that a NASA API already publishes and that a regulator would accept.

### Uncertainty is a first-class output

The impact models are quantile regressors, not point estimators. Every prediction ships as
`{median, 2.5th percentile, 97.5th percentile}`. An operator is told "GPS error 12.8 m, 95% CI
6.6–13.3 m", not a bare number with invisible error bars. Measured interval coverage is 96.4% (GPS)
and 94.8% (HF) against a 95% target — the intervals mean what they claim to mean.

## 4. How it helps

**For the operator.** One screen, four industries, live. Open the dashboard, trigger a storm, and
watch detection → prediction → four agents reasoning in parallel → verifier checks land in real time
over WebSocket. Each advisory is a numbered action list with a time window and a cited source
document, not a paragraph of prose to interpret under pressure.

**For the safety officer.** Every advisory is traceable end to end. Which chunk of which PDF grounded
step 3? What did the model originally propose before correction? What was the retrieval similarity?
What confidence score, and which safety flags fired? All of it is stored, all of it is renderable.

**For the engineering team.** The system is built to be operated, not just demoed: structured JSON
logs, Prometheus metrics, three-tier health checks, Kubernetes manifests with real probes, Terraform
for the cluster, GitOps for deploys, chaos experiments in staging, and four incident runbooks. ~137
Python tests and ~255 frontend tests run in CI.

**Failure is designed in, not discovered.** Every layer degrades instead of collapsing. No cached
imagery → fall back to stub storm events. DONKI unreachable → cached physics. ML checkpoints missing
→ conservative defaults (20 m GPS, 85% HF blackout) rather than silence. All three LLM retries
exhausted → an advisory that says `ESCALATE TO SPECIALIST` instead of a guess. Groq entirely down →
detection and impact prediction still serve.

## 5. Why choose it

| | Raw NOAA alerts | Generic LLM assistant | Consultancy / manual desk | **HelioOps** |
|---|---|---|---|---|
| Per-industry actions | ✗ | ~ | ✓ | ✓ |
| Grounded in real rulebooks | ✗ | ✗ | ✓ | ✓ (RAG over ICAO / NERC / IMO / NOAA) |
| Safety-critical values verified | n/a | ✗ | ~ | ✓ (deterministic rule engine) |
| Quantified uncertainty | ✗ | ✗ | ~ | ✓ (95% CIs, measured coverage) |
| Full audit trail | ✗ | ✗ | ~ | ✓ (6-step provenance per advisory) |
| Reproducible | ✓ | ✗ | ✗ | ✓ (no RNG in detection or routing) |
| Real time | ✓ | n/a | ✗ | ✓ (WebSocket streaming) |
| Cost to run | free | low | very high | low (CPU-only, free-tier LLM) |

Three things are genuinely hard to copy:

1. **The verifier.** Anyone can wire an LLM to a vector store. Almost nobody puts a deterministic rule
   engine downstream of it that *rewrites* unsafe values and logs the correction.
2. **The provenance chain.** Auditability was designed in from the schema up — it is not a logging
   afterthought bolted on later.
3. **The honesty of the failure modes.** Conservative fallbacks and explicit safety flags
   (`LOW_COVERAGE`, `CITATION_GAP`, `SEVERITY_MISMATCH`, `LOW_CONFIDENCE`) mean the system tells you
   when to distrust it.

**Cost profile:** runs entirely on CPU. No GPU for detection (threshold algorithm), none for impact
(LightGBM, checkpoints < 500 KB), none for embeddings (BGE-small, 384-dim). The only external paid
dependency is the LLM, and the self-check step deliberately uses a lighter 8B model to stay inside
free-tier rate limits.

## 6. Current maturity — stated plainly

Production-shaped, not yet production-proven. What is real and what is not:

**Real:** the detection algorithm, the DONKI/GOES/DSCOVR integrations, the trained models and their
metrics, the agent pipeline, the verifier, the API, the dashboard, the database schema, and the full
DevOps chain (Docker → CI → Kubernetes → Terraform → ArgoCD → chaos → runbooks).

**Caveats worth knowing before deploying:**

- **Impact models are trained on synthetic storm data.** The reported R² of 0.986 measures how well
  the model learned the physical proxy rules it was generated from — not real-world accuracy. Moving
  to NASA OMNIWeb historical data is the known next step.
- **Two demo storms** (`2024-10-G4`, `2024-05-G5`) are wired for replay; live mode exists but the
  cached path is what the demo runs.
- **`telecom_kb` is intentionally empty**, so the telecom agent honestly emits a `LOW_COVERAGE`
  advisory — a deliberate demonstration that the system reports thin evidence instead of inventing it.
- **CI gates are advisory, not blocking** (steps end in `|| true`), and the Docker build stage builds
  without pushing. Full CD is scaffolded, not switched on.
- **Rate limiting and metrics are per-process**, so they are correct on a single replica and need a
  shared store (Redis) before horizontal scaling means anything.

## 7. Team

| Owner | Layer |
|---|---|
| **Neal** | Layer 1 — CV detection, ML pipeline |
| **Parshva** | Layer 2 — data engineering, impact models |
| **Priyanshu** | Layer 3 — GenAI advisory, backend pipeline, database |
| **Tirth** | Layer 4 — frontend dashboard, DevOps, deployment |

---

*Technical detail per domain: see [`TECHNICAL_DEEP_DIVE.md`](./TECHNICAL_DEEP_DIVE.md).*
