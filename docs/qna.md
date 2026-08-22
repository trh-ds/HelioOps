1. What is the problem?

The Sun regularly throws out a huge blob of charged gas — a coronal mass ejection (CME). When it hits Earth, four industries lose capability within hours:

┌────────────┬─────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┐
│  Industry  │                         What breaks                         │                   What it costs them                    │
├────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Aviation   │ HF radio on polar routes, GPS accuracy, crew radiation dose │ Polar tracks close, flights reroute or cancel           │
├────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Power grid │ Induced currents (GIC) cooking transformers                 │ Transformer heating, voltage instability, blackout risk │
├────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Maritime   │ GMDSS distress comms, GNSS position                         │ Degraded safety-of-life comms far from shore            │
├────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Telecom    │ HF/satellite links, timing signals                          │ Outages, timing drift                                   │
└────────────┴─────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────┘

Here's the twist: the data is already free and public. NOAA/SWPC alerts, NASA DONKI CME data, GOES X-ray flare data, DSCOVR solar wind. Nobody is missing the signal.

What's missing is the last mile — turning the signal into a decision. Four specific gaps (§1 of the brief):

1. An alert is not a decision. "G4 Watch, Kp 8.3" tells a dispatcher nothing about which of my 40 polar flights do I move or which frequency do I fall back to.
2. The rulebooks are PDFs. The real procedures live in ICAO NAT Doc 007, NERC TPL-007-4, IMO GMDSS 2019 — hundreds of pages each. Nobody reads them at 3am mid-event.
3. A normal chatbot is dangerous here. Ask ChatGPT for a fallback HF frequency and it will confidently make one up. A wrong frequency in an aviation advisory isn't an embarrassing error — it's a safety incident.
4. Nothing is auditable. A regulated operator legally cannot act on an output they can't trace back to a cited procedure and a measured input.

So the problem is not "we can't see solar storms." It's "the alert and the action are separated by a wall of PDFs, and the obvious AI shortcut across that wall is unsafe."

---

2. How are we solving it?

A five-stage pipeline. Imagery goes in one end, a numbered, cited, machine-checked action list comes out the other, live on a dashboard and saved for audit.

Solar imagery (CCOR-1 / LASCO)
  ① CV DETECTION      threshold detector + NASA DONKI physics → StormEvent
  ② ML IMPACT         6 LightGBM quantile models → GPS error + HF blackout, each with 95% CI
  ③ AGENTIC ADVISORY  4 industry agents in parallel, RAG over the real rulebooks
  ④ VERIFIER          zero-LLM rule engine — corrects unsafe numbers, doesn't just flag them
  ⑤ DELIVERY          FastAPI REST + WebSocket → Next.js dashboard → Supabase Postgres

Every advisory carries a 6-step provenance trace: raw_data → detection → impact → retrieval → verifier → output.

The one-line summary of the whole design: deterministic where safety demands it, generative only where language is needed. The LLM's only job is turning a severity tier plus retrieved regulatory text into readable numbered steps. It never decides severity, never decides a frequency, never gets the last word.

---

3. Why is this optimal — and is it?

Where it's genuinely optimal, and why:

a) The LLM is boxed in on both sides. Upstream, a hard-coded matrix decides severity (G4 aviation is always CRITICAL — never HIGH because a sampler drifted). Downstream, a zero-LLM rule engine re-checks the output. The model can only write prose inside boundaries it cannot move. This is the correct architecture for a safety domain, and it's the opposite of what a naive "wrap GPT around a vector DB" build does.

b) The verifier corrects rather than rejects. The canonical example from the brief: the agent writes "switch to 21 MHz." Regex pulls out 21, tests against the ICAO NAT set {3, 5, 8, 11, 17}, fails, rewrites the text to 5 MHz, records the correction, and streams it to the dashboard as a visible block. The operator sees both what the model proposed and what the rules enforced. Rejecting the whole advisory would throw away three otherwise-correct actions; correcting keeps them.

c) They deleted their own ML where it wasn't defensible. The CV layer originally had a CNN (cv/cmecnn.py). It was removed because (1) no labeled training data exists for coronagraph CME segmentation, (2) NASA DONKI already publishes human-reviewed kinematics, (3) a deterministic detector is reproducible and needs no GPU. The deep dive calls this the most important engineering judgement in the repo, and it's right — they shipped less AI because a threshold plus an authoritative API is more defensible than a model trained on labels that don't exist.

d) Uncertainty is an output, not a footnote. Operators get "GPS error 12.8 m, 95% CI 6.6–13.3 m", not a bare number. Measured interval coverage is 96.4% / 94.8% against a 95% target — the intervals mean what they claim.

Where "optimal" is doing some work (the honest caveats, §6 of the brief):

- The impact models are trained on synthetic data. The R² of 0.986 measures how well the model learned the physics proxy rules it was generated from — not real-world accuracy. Retraining on NASA OMNIWeb historical data is the stated next step. Until that happens, ② is architecturally right but empirically unproven.
- Only two demo storms are wired for replay; live mode exists but isn't the demo path.
- CI gates are advisory (|| true), rate limiting and metrics are per-process (correct at one replica, wrong at three).

Verdict: the architecture is optimal for the problem — the determinism/generative split, the verifier, the provenance chain are the right answers and would survive contact with a regulator. The data is not yet there. It's production-shaped, not production-proven, and the docs say exactly that rather than hiding it.

---

4. The CV Detection Layer — what, how, why

What it does: looks at coronagraph images of the Sun, finds the CME, and combines that with three other physics feeds into a single StormEvent — confidence, G/S/R scales, CME kinematics, timeline.

How it works — the 9-step algorithm (cv/threshold_detector.py):

1. Annular mask              cut out the occulter disc and the far field
2. Per-frame μ/σ             brightness stats computed inside the mask only
3. Bright threshold          bright_mask = diff > μ + 2.5σ
4. Morphological open+close  kill speckle, close gaps
5. Connected components      take the largest blob
6. Bounding box              normalized, padded
7. CPA + angular width       polar geometry about the occulter centre
8. Confidence                f(area, SNR)
9. Annotate + save PNG

The trick that makes a plain threshold work at all: it runs on running-difference frames — each frame minus the previous one. That subtracts away the static corona, so the only thing left is what moved. The CME becomes the dominant bright object instead of one feature among many.

Two details that carry real weight:

- _circular_mean_deg() — position angles wrap at 0/360°. Averaging 350° and 10° arithmetically gives 180°, pointing the CME in exactly the wrong direction. They use atan2(mean(sin), mean(cos)) instead. That's the correct-on-edge-cases version, not the shorter one.
- find_occulter_center() — measures where the occulter actually is at runtime rather than trusting DEFAULT_CENTER_XY = (256, 256). LASCO and CCOR-1 differ, and no real instrument is perfectly centred. The constants are calibration defaults, not assumptions.

Then: fusion. Detection alone isn't a storm assessment. cv/fusion.py blends four independent sources:

confidence = 0.4·detection + 0.2·flare + 0.2·solar_wind + 0.2·cme

┌─────────────────────┬───────────────────────────────────────────┐
│       Source        │                Contributes                │
├─────────────────────┼───────────────────────────────────────────┤
│ Coronagraph imagery │ detection confidence, bbox, angular width │
├─────────────────────┼───────────────────────────────────────────┤
│ NASA DONKI          │ CME speed, width, direction               │
├─────────────────────┼───────────────────────────────────────────┤
│ GOES XRS            │ flare class (X/M/C) → R-scale             │
├─────────────────────┼───────────────────────────────────────────┤
│ DSCOVR at L1        │ Bz, Bt, density, wind speed, ETA          │
└─────────────────────┴───────────────────────────────────────────┘

Imagery gets the biggest single weight but is capped at 40% — no single sensor can drive the assessment alone.

Why this way, not a CNN: covered above. No labels exist; NASA already publishes reviewed kinematics; deterministic means reproducible, testable, GPU-free. There is no RNG anywhere in the path — the same input frame produces a byte-identical PNG every run, which is what makes the 43 tests in tests/test_option_c.py meaningful instead of flaky. Every tunable is a named constant (SIGMA_THRESHOLD = 2.5, ANNULAR_OUTER_PX = 220) so it can be retuned per instrument without touching the algorithm.

Graceful degradation — every stage has a defined fallback:
PNGs present   → use them      else → cache_fits.py must run
Detector fires → real bbox     else → stub bbox_norm
DONKI cached   → real physics  else → fetch live → on failure → stub speed
StormEvent OK  → return it     else → load ml/stubs/storm_event_{id}.json
It always returns a usable StormEvent. It never half-populates and never raises into the API.

---

5. The ML Impact Layer — what, how, why

What: takes the StormEvent and predicts two things an operator can actually act on:
- GPS L1 position error, in metres
- HF radio blackout probability, 0–1

How — six models, not two:

StormEvent → 9 features → 6 LightGBM models → ImpactPrediction
                          ├── gps_q025 / gps_q500 / gps_q975
                          └── hf_q025  / hf_q500  / hf_q975

Each target gets three independently trained quantile regressors at the 2.5th, 50th and 97.5th percentile. The q025–q975 pair is the 95% confidence interval — produced directly by the models, not estimated afterwards from residuals.

The nine features: g_scale, kp_index (via the {0:0, 1:5, 2:6, 3:7, 4:8.3, 5:9} map), bz_nt, wind_speed_km_s, cme_speed_km_s, cme_width_deg, r_scale, plus geomag_lat_bin and local_time_bin.

Training methodology:

┌──────────────────────┬────────────────────────────────────────────────────────────────────────┐
│      Technique       │                                Purpose                                 │
├──────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ GroupKFold splitting │ Stops temporal leakage — frames of one storm can't straddle train/test │
├──────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Optuna               │ Hyperparameter search                                                  │
├──────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Pinball loss         │ The correct objective for quantile targets                             │
├──────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ PICP / PINAW         │ Measures whether the intervals are calibrated, not just point accuracy │
├──────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Physical anchor test │ G5 black-swan validation                                               │
└──────────────────────┴────────────────────────────────────────────────────────────────────────┘

Results:

┌───────────────────┬──────────────┬─────────────┐
│      Metric       │ GPS L1 error │ HF blackout │
├───────────────────┼──────────────┼─────────────┤
│ R²                │ 0.9858       │ 0.9577      │
├───────────────────┼──────────────┼─────────────┤
│ MAE               │ 0.1463 m     │ 0.0320      │
├───────────────────┼──────────────┼─────────────┤
│ PICP (target 95%) │ 96.40%       │ 94.77%      │
├───────────────────┼──────────────┼─────────────┤
│ PINAW             │ 0.0466       │ 0.1942      │
└───────────────────┴──────────────┴─────────────┘

PICP is the number that matters: when the model claims 95% confidence, the truth lands inside the stated interval 96.4% / 94.8% of the time. And the low PINAW says the intervals are tight — not trivially wide to game the coverage number.

Why quantile regression: a single number is operationally useless for a safety decision. A dispatcher deciding whether to close a polar route needs the plausible worst case, not the average case.

The anchor test is the smartest piece here. Fed the May 2024 G5 storm (CME 1800 km/s, Kp 9.0), the model predicted 17.50 m GPS error (requirement > 15 m) and 84.27% HF blackout (requirement > 80%). This checks the model extrapolates into the rare-event regime instead of regressing toward the training mean — which is the exact failure mode that makes an R² of 0.98 worthless during an actual emergency.

Two production-hardening details:
- Quantile monotonicity. Independently trained quantile models can cross — q97.5 landing below q50 gives an inverted, nonsense interval. Fixed with one line: ci_low, median, ci_high = sorted([q025, q500, q975]). One sorted() call kills a whole class of invalid output.
- Conservative fallback. If checkpoints are missing, inference returns GPS = 20 m, HF = 85% — deliberately pessimistic. In a safety system the fallback must fail toward caution, never toward "all clear." And /health/ready reports the degraded state separately, so a fallback is visible, not silent.

Checkpoints total under 500 KB and run on CPU.

The honest caveat: training data is synthetic (data/synthetic_storms.csv). The R² measures how well the model learned the physics proxy rules it was generated from.

---

6. The Agentic AI Layer — what, how, why

The densest layer: four LLM agents running in parallel over a RAG knowledge base, ten anti-hallucination controls, and a deterministic rule engine downstream.

6a. Deterministic routing first — the LLM is not in charge

Before any agent runs, route_storm() reads a hard-coded matrix. No model chooses severity:

┌─────┬──────────┬──────────┬──────────┬──────────┐
│     │ Aviation │   Grid   │ Maritime │ Telecom  │
├─────┼──────────┼──────────┼──────────┼──────────┤
│ G1  │ LOW      │ LOW      │ NONE     │ NONE     │
├─────┼──────────┼──────────┼──────────┼──────────┤
│ G2  │ MEDIUM   │ MEDIUM   │ LOW      │ LOW      │
├─────┼──────────┼──────────┼──────────┼──────────┤
│ G3  │ HIGH     │ HIGH     │ MEDIUM   │ MEDIUM   │
├─────┼──────────┼──────────┼──────────┼──────────┤
│ G4  │ CRITICAL │ CRITICAL │ HIGH     │ HIGH     │
├─────┼──────────┼──────────┼──────────┼──────────┤
│ G5  │ CRITICAL │ CRITICAL │ CRITICAL │ CRITICAL │
└─────┴──────────┴──────────┴──────────┴──────────┘

Sourced from NOAA Space Weather Scales and NESDIS briefings. Industries below their trigger tier return triggered=False and no agent is spawned for them — saving cost too.

Why: operators need certainty that G4 always means CRITICAL for aviation. Determinism also makes routing unit-testable and auditable, and it becomes the floor that guardrail #5 enforces the LLM against.

6b. Orchestration

AgentScope over LangGraph — a transparent message protocol with no graph-compilation step, plain asyncio.gather fan-out, and a debuggable call stack. Adding an industry is a one-line registry entry.

Streaming while running: agents push events into an asyncio.Queue; the orchestrator drains it on a 50 ms tick while tasks are still in flight, so the dashboard shows agents thinking live. The post-loop final drain is the correctness detail — without it, events queued between the last poll and task completion would be silently dropped.

The embedder prewarm is a real bug fixed at the source: four agents hitting a lazy-loaded BGE singleton from four to_thread workers raced on PyTorch meta-tensor materialization ("Cannot copy out of meta tensor"). One eager load in the main thread before any fan-out removes the race for every caller — instead of bolting a lock onto each agent.

Fault isolation: return_exceptions=True in the batch path, per-task try/except in the streaming path. One failed agent emits agent.error while the other three still deliver.

6c. RAG infrastructure

data/{aviation,grid,maritime,impact_matrix}/*.pdf
  └── loaders → chunker → BGE-small embedder → ChromaDB
                            ├── aviation_kb        242 chunks
                            ├── grid_kb            101 chunks
                            ├── impact_matrix_kb   166 chunks
                            ├── maritime_kb          2 chunks
                            └── telecom_kb           0 chunks

Real regulatory sources: ICAO NAT Doc 007 (2025), NERC TPL-007-4 plus benchmark GMD and transformer-thermal docs, IMO GMDSS (2019), NOAA/NESDIS scales and impact memos.

- BGE-small-en-v1.5: 384-dim, fast on CPU, and asymmetric — a query prefix at query time but not at index time, which is what it was trained for and why it beats MiniLM on retrieval. Vectors stored L2-normalized so cosine similarity falls out as 1 - dist/2 for free.
- ChromaDB PersistentClient is embedded — no server, no network hop, no extra container.
- Chunking: 512 tokens with 64-token overlap, token-aware via tiktoken. The overlap stops a procedure step being severed at a boundary and losing its context.
- Retrieval: top-8 from the industry KB + top-4 from the impact matrix, filtered at 0.35 cosine, both queried in parallel. Context is formatted as labelled blocks carrying chunk_id, source, similarity — which is precisely what makes citation verification possible downstream.

6d. The 11-step per-agent pipeline

Every agent runs the same loop; subclasses supply only a system prompt and a KB query template:

 1. Build KB query from storm parameters (G/Kp/S/R)
 2. Parallel ChromaDB retrieval (industry top-8 + matrix top-4)
 3. Format context with chunk_id, source, similarity
 4. Generate — Groq Llama 3.3 70B, temp 0.1, JSON mode
 5. Validate schema — Pydantic, fails fast on missing source_ref
 6. Severity consistency — cannot go below the deterministic matrix
 7. LLM self-check — separate Groq call in critic mode
 8. Confidence score
 9. Safety flags
10. Retry loop — up to 3, errors injected into the next prompt
11. Safe fallback — ESCALATE_TO_SPECIALIST

6e. Ten anti-hallucination layers

┌─────┬─────────────────────────────────┬──────────────────────────────────────────────────────────────────┐
│  #  │            Technique            │                              Effect                              │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 1   │ RAG-only grounding              │ Training knowledge forbidden; cite provided context only         │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 2   │ Citation enforcement            │ Every action needs source_ref; missing ⇒ validation fail ⇒ retry │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 3   │ Retrieval quality gate          │ Chunks below 0.35 cosine dropped before the LLM sees them        │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 4   │ JSON schema enforcement         │ Groq JSON mode + Pydantic                                        │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 5   │ Deterministic severity override │ Below matrix minimum ⇒ SEVERITY_MISMATCH                         │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 6   │ Source existence check          │ Citations cross-checked against retrieved chunks ⇒ CITATION_GAP  │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 7   │ LLM self-check                  │ Second call audits numbers and regulation codes                  │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 8   │ Retry with error injection      │ "FIX THESE: …" fed back to the model                             │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 9   │ Confidence score                │ Multi-factor, exposed to reviewers                               │
├─────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 10  │ Conservative fallback           │ All retries exhausted ⇒ ESCALATE TO SPECIALIST                   │
└─────┴─────────────────────────────────┴──────────────────────────────────────────────────────────────────┘

Confidence formula:
base_score       = mean cosine similarity across retrieved chunks
+ 0.02 per action_item with a verified source_ref
- 0.08 per action_item missing/unverifiable source_ref
+ 0.10 if base_score > 0.6
The penalty is 4× the bonus — deliberately asymmetric, because a fabricated citation is far more dangerous than a missing bonus is valuable. Below 0.50 ⇒ LOW_CONFIDENCE.

Safety flags are audit markers, not blocks. The advisory still reaches the operator with its caveats attached rather than vanishing — an operator with a flagged advisory is better off than an operator with nothing.

Why a separate self-check call: the generating model is in "write" mode; a fresh call in "critic" mode catches inconsistencies the generator can't see in one pass. Cost is one extra call per industry, routed to the lighter llama-3.1-8b-instant to stay inside Groq rate limits while the 70B does generation.

6f. The deterministic verifier — the crown jewel

genai/verifier.py, zero LLM calls, runs after every agent:

┌────────────────────┬────────────────────┬──────────────────────────────────┐
│        Rule        │      Industry      │            Valid set             │
├────────────────────┼────────────────────┼──────────────────────────────────┤
│ HF frequency       │ aviation, maritime │ {3, 5, 8, 11, 17} MHz (ICAO NAT) │
├────────────────────┼────────────────────┼──────────────────────────────────┤
│ Reroute latitude   │ aviation           │ G3→78°N, G4→70°N, G5→60°N        │
├────────────────────┼────────────────────┼──────────────────────────────────┤
│ GIC operating step │ grid               │ NERC TPL-007-4 Appendix B        │
├────────────────────┼────────────────────┼──────────────────────────────────┤
│ GMDSS channel      │ maritime           │ valid distress/working channels  │
└────────────────────┴────────────────────┴──────────────────────────────────┘

Model writes "21 MHz" → regex extracts 21 → 21 ∉ {3,5,8,11,17} → status="blocked", corrected_to=5 → the action text is corrected in place → streamed as a verifier.check event the dashboard renders as a visible block.

Why it exists: RAG reduces hallucination, it does not eliminate it. Models still fabricate specific numeric values even with correct context in the window. The verifier is fast, fully auditable, and corrects rather than merely rejects.

---

7. The Full Stack & DevOps layers — briefly

Backend (FastAPI, hexagonal): the pipeline never imports cv.storm_event_generator.detect or ML_after_CV.inference directly. It talks to ports (abstract interfaces); adapters provide implementations. So storage swaps at runtime — RESULT_REPOSITORY picks in-memory or Supabase, same call sites, zero pipeline changes — and the ML layer is mockable in tests without touching real checkpoints.

The load-bearing piece is schema_adapter.py, the anti-corruption layer. CV and GenAI were built by different people with different schemas and neither was rewritten. One file translates: storm_id → alert_id, scales["G"] → GScale enum, and so on. Integration cost is paid once in one file instead of being smeared across four modules owned by four people. That's "bridge, don't rewrite."

Security at the boundary: security headers on every response, request IDs for log correlation, one pipeline run per storm per 30 s (the pipeline fans out to multiple LLM calls — this stops a refresh loop draining the Groq quota), and validate_storm_id() as an allowlist regex ^\d{4}-\d{2}-G[1-5]$ applied before the ID reaches any filesystem or DB path. The same gates apply on the WebSocket path, because a socket is a trust boundary too.

Frontend (Next.js 14): typed API client with encodeURIComponent on every path param; 5xx and network errors retry once with exponential backoff while 4xx does not (a 404 won't fix itself); server stack traces never surfaced. The WS client is a small state machine with backoff from 1 s to a 30 s ceiling — malformed JSON is dropped not thrown, and a throwing listener is caught so one broken subscriber can't starve the rest. ErrorBoundary stops a render error in one card blanking the whole page, which is exactly the Groq-outage scenario in the runbook: detection and impact still render, advisory cards go empty.

Data layer: 8 tables, RLS, and invariants enforced in the database — CHECK (confidence BETWEEN 0 AND 1), UNIQUE (advisory_id, step), cascading FKs. Irregular physics payloads are JSONB; anything queried, constrained or joined is a real typed column.

DevOps: Docker (two-stage, build toolchains never reach the runtime image) → GitHub Actions CI → Kubernetes (readiness hits /health/ready so a pod with unloaded models leaves the load balancer without being killed; liveness is a bare process check so a slow dependency never causes a restart loop; maxUnavailable: 0 for zero-downtime) → Terraform → ArgoCD (selfHeal reverts manual kubectl edit drift; rollback is git revert, not an SSH session) → structured JSON logs + Prometheus → scheduled Chaos Mesh experiments in staging only → four incident runbooks.

---

8. Data — what, why, and how it flows

What data comes in:

┌───────────────────────────────┬────────────────────┬────────────────────────────────────────────────┐
│            Source             │        Type        │                    Gives us                    │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ CCOR-1 / LASCO coronagraph    │ Imagery (FITS/PNG) │ Visual CME detection, bbox, angular width      │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ NASA DONKI                    │ REST API           │ CME speed, width, direction — human-reviewed   │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ GOES XRS                      │ REST API           │ X-ray flare class (X/M/C) → R-scale            │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ DSCOVR at L1                  │ REST API           │ Bz, Bt, density, solar wind speed, arrival ETA │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ NOAA/SWPC                     │ Alert text         │ G/S/R scales, Kp index, raw alert              │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ ICAO / NERC / IMO / NOAA PDFs │ Documents          │ The actual regulatory procedures               │
├───────────────────────────────┼────────────────────┼────────────────────────────────────────────────┤
│ data/synthetic_storms.csv     │ Generated          │ ML training data                               │
└───────────────────────────────┴────────────────────┴────────────────────────────────────────────────┘

The flow:

Imagery ─┐
DONKI ───┼─► cv/fusion.py ──► StormEvent ──► 9 features ──► 6 LightGBM models
GOES ────┤                        │                              │
DSCOVR ──┘                        │                              ▼
                                  │                      ImpactPrediction (+95% CI)
                                  ▼                              │
                         schema_adapter (ACL)                    │
                                  ▼                              │
                         route_storm() ──► 4 agents ◄────────────┘
                                              │
PDFs ──► chunker ──► BGE ──► ChromaDB ────────┤ (retrieval)
                                              ▼
                                     verify_advisory()
                                              ▼
                    VerifiedAdvisory + ProvenanceTrace
                                              ▼
                    REST / WebSocket ──► Dashboard ──► Postgres

Why this data, used this way:

- Physics from authoritative sources, not learned from thin air. CME speed comes from NASA DONKI, a human-reviewed database — they explicitly did not train a regressor to guess numbers a NASA API already publishes and a regulator would accept. This is the difference between a number you can defend in a review and a number you can't.
- Four sensors, weighted, none dominant. Imagery caps at 40%. Any single feed can be wrong or unavailable, and the assessment survives.
- PDFs become retrievable chunks so the LLM cites the actual rulebook instead of its own memory.
- Similarity scores are stored, not discarded — that's what makes citation verification and the confidence score possible.
- Everything is persisted with provenance because a regulated operator cannot act on an untraceable output.

The honest bit about data: the ML training set is synthetic. telecom_kb is deliberately empty and maritime_kb has 2 chunks — so the telecom agent honestly emits LOW_COVERAGE rather than inventing content. That empty KB is arguably the best demo in the whole system: it proves the thing reports thin evidence instead of filling the gap with confident fiction.

---

9. Limitations of the platform

Straight from §7 of the deep dive and §6 of the brief, in rough priority:

┌─────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│           Limitation            │                                                  Why it matters                                                   │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ML trained on synthetic data    │ The headline R² of 0.986 measures rule-learning, not real-world accuracy. Fix: retrain on NASA OMNIWeb historical │
│                                 │  data. This is the big one.                                                                                       │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CI steps end in || true         │ Lint/test failures report but don't block merges. CI is advisory theatre right now.                               │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Rate limiter + metrics in       │ Correct at one replica. At three, each pod counts and rate-limits independently — so the numbers are wrong and    │
│ process memory                  │ the limit is 3× looser than stated. Needs Redis.                                                                  │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Checkpoints + ChromaDB not in   │ CI runs shallow; fallbacks engage instead of real code paths.                                                     │
│ git                             │                                                                                                                   │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ docker-build has push: false    │ No actual CD. Images never reach a registry.                                                                      │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ maritime_kb = 2 chunks,         │ Two of four industries have thin or no evidence base ⇒ frequent LOW_COVERAGE.                                     │
│ telecom_kb = 0                  │                                                                                                                   │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ In-memory repository is the     │ Results lost on restart unless Supabase is explicitly configured.                                                 │
│ default                         │                                                                                                                   │
├─────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Two demo storms wired for       │ Live mode exists but isn't the demo path. Not yet proven against a live event.                                    │
│ replay                          │                                                                                                                   │
└─────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Structural limitations beyond that list, reading the architecture:

- The verifier only checks what it has rules for. Four rule families (HF freq, reroute latitude, GIC step, GMDSS channel). Anything outside that set is unverified LLM output. The verifier's strength is also its ceiling: it's only as good as the constants someone encoded.
- The severity matrix is fixed. G-scale in, tier out. It doesn't know that this particular airline flies 40 polar routes and that one flies two.
- Dependent on external APIs staying up and stable. DONKI/GOES/DSCOVR outages degrade to stubs — safe, but degraded.
- Groq is the only paid external dependency and a single point of failure for the advisory layer specifically. Detection and impact survive it; advisories don't.

---

10. Impact on the space industry

Note: this is my reading of the docs' implications — the docs describe the system, not an industry impact study.

What it actually changes:

1. It closes the last mile on data that's already free. The space weather community has spent decades building sensors and models. NOAA, NASA, DSCOVR — that investment produces alerts that stop at the boundary of "here is a number." HelioOps is downstream infrastructure: it turns public space weather data into per-industry operational decisions. That's leverage on existing public spend, not new sensor cost.
2. It makes space weather actionable for non-experts. Right now, acting on a G4 alert requires a person who understands both the physics and ICAO NAT Doc 007. That person is rare and is not awake at 3am. This puts the domain expertise into a system.
3. It demonstrates a safety-critical AI pattern that generalizes. The determinism/generative split plus a downstream rule engine that corrects — that pattern applies to any regulated domain where an LLM is useful for language but untrustworthy for values. Aviation maintenance, pharma, nuclear ops. The space weather use case is a proof of the pattern.
4. It's a template for auditable AI in regulated ops. The 6-step provenance chain is designed into the schema, not bolted on as logging. That's what makes it plausible a regulator could ever approve it — and regulatory acceptance is the actual blocker for AI in these industries, not model capability.

Honest scale check: the impact is real as a pattern. Real deployed impact requires the synthetic-data problem fixed and live mode proven. Today it's an architecture the industry should copy, not yet a system the industry is running.

---

11. Business profits

Not in the docs. No revenue model, pricing, or market numbers appear in either file. This is inference from the cost profile and capability set — treat it as reasoning, not sourced fact.

What the docs do support:

The cost side is unusually strong. Runs entirely on CPU — no GPU for detection (threshold algorithm), none for impact (LightGBM, <500 KB checkpoints), none for embeddings (BGE-small, 384-dim). Input data is free and public. The only paid external dependency is the LLM, and the self-check deliberately uses a lighter 8B model to stay in free-tier rate limits. Deterministic routing means agents aren't even spawned for industries below their trigger tier.

That's a near-zero marginal cost per storm. And storms are episodic — you're not paying for idle inference 300 days a year.

Where the value sits, by customer:

┌───────────────────┬───────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────┐
│     Customer      │          What a bad space weather day costs them          │                        What they'd pay for                         │
├───────────────────┼───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Airlines          │ Polar reroutes burn fuel and hours; cancellations cost    │ Deciding which flights to move, faster and with fewer unnecessary  │
│                   │ far more                                                  │ reroutes                                                           │
├───────────────────┼───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Grid operators    │ Transformer damage runs into millions; blackouts far more │ Cited NERC operating steps, on time                                │
├───────────────────┼───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Shipping          │ Degraded safety-of-life comms in remote waters            │ GMDSS fallback guidance                                            │
├───────────────────┼───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Telecom /         │ Link outages, timing drift                                │ Advance warning with quantified probability                        │
│ satellite         │                                                           │                                                                    │
└───────────────────┴───────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────┘

The economics are asymmetric in the classic insurance way: subscription cost is trivial against one avoided transformer failure or one avoided unnecessary mass-reroute.

Plausible models: per-seat SaaS for ops desks; per-industry tiers; an API/data feed for operators with their own dashboards; enterprise licence where regulated customers self-host for data residency. The audit trail is itself a sellable feature — regulated operators need to demonstrate they followed procedure, and the provenance chain is that documentation, generated automatically.

Reality check on the business: the sales cycle for safety-critical software in aviation and grid is long and evidence-heavy. Nobody buys this on an R² measured against synthetic data. The path is: fix the training data → prove it against historical storms → get a design partner → certification conversations. That's years, not quarters.

---

12. The market gap, and how it's filled

The gap in one sentence: the sensing layer is solved and free, the procedures exist and are public, and nothing connects them under time pressure with an audit trail.

More precisely, four gaps stacked:

1. Alert → action. Everyone publishes alerts. Nobody publishes your actions.
2. Procedures are unusable at speed. Hundreds of PDF pages, per industry, mid-emergency.
3. Generic AI can't fill it. The obvious shortcut — ask a chatbot — fabricates safety-critical values.
4. Auditability. Regulated operators can't act on untraceable output, which disqualifies almost every AI approach on its own.

The interesting structural point: gaps 3 and 4 are why the gap persists. It's not that nobody noticed alerts aren't actions. It's that the obvious solution is unsafe and the safe solution is boring, unglamorous, and requires reading regulatory PDFs.

How HelioOps fills each:

┌───────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│        Gap        │                                                      Fill                                                       │
├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Alert → action    │ Deterministic severity matrix + 4 industry agents producing numbered action lists with timing windows           │
├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PDFs unusable     │ RAG over the actual rulebooks — ICAO NAT Doc 007, NERC TPL-007-4, IMO GMDSS — with chunk-level citation         │
├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Generic AI unsafe │ Ten anti-hallucination layers + a zero-LLM verifier that corrects unsafe values against authoritative constants │
├───────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Not auditable     │ 6-step provenance per advisory, in the schema, in the API, on screen, in Postgres                               │
└───────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

---

13. Current similar products

The docs name no commercial competitors. What §5 of the brief gives is a comparison against three categories of existing alternative:

┌─────────────────────────────────┬─────────────────┬───────────────────────┬───────────────────────────┬──────────┐
│                                 │ Raw NOAA alerts │ Generic LLM assistant │ Consultancy / manual desk │ HelioOps │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Per-industry actions            │ ✗               │ ~                     │ ✓                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Grounded in real rulebooks      │ ✗               │ ✗                     │ ✓                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Safety-critical values verified │ n/a             │ ✗                     │ ~                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Quantified uncertainty          │ ✗               │ ✗                     │ ~                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Full audit trail                │ ✗               │ ✗                     │ ~                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Reproducible                    │ ✓               │ ✗                     │ ✗                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Real time                       │ ✓               │ n/a                   │ ✗                         │ ✓        │
├─────────────────────────────────┼─────────────────┼───────────────────────┼───────────────────────────┼──────────┤
│ Cost                            │ free            │ low                   │ very high                 │ low      │
└─────────────────────────────────┴─────────────────┴───────────────────────┴───────────────────────────┴──────────┘

Read the columns: NOAA is free, real-time and reproducible but gives you no actions. A generic LLM gives you actions but fails every safety column. A human consultancy passes on substance but fails on real-time and cost. HelioOps is claiming the intersection — consultancy-grade output at API speed and cost.

Three things the brief argues are hard to copy:

1. The verifier. Anyone can wire an LLM to a vector store — that's a weekend. Almost nobody puts a deterministic rule engine downstream that rewrites unsafe values and logs the correction.
2. The provenance chain. Designed in from the schema up. Bolting auditability onto an existing system afterwards is enormously harder than designing for it.
3. The honesty of the failure modes. LOW_COVERAGE, CITATION_GAP, SEVERITY_MISMATCH, LOW_CONFIDENCE — the system tells you when to distrust it.

I'd add a fourth: the regulatory corpus and the encoded constants. Knowing that ICAO NAT valid HF frequencies are {3, 5, 8, 11, 17} and that G4 means reroute below 70°N is domain knowledge someone had to dig out of PDFs. That's the unglamorous moat.

Caveat: absence of named competitors in the docs is not evidence none exist. Commercial space weather services do operate in this space. I can't assess them from these two files.

---

14. Why did nobody think of this before?

My reading, not stated in the docs.

I don't think the honest answer is "nobody thought of it." Connecting alerts to actions is an obvious idea. The answer is more that the pieces only recently became simultaneously cheap enough and safe enough, and the work required is the kind people avoid:

a) The enabling tech is ~2 years old. RAG over a regulatory corpus that produces cited output needs good embeddings and reliable JSON-mode LLMs. Before that, you'd have hand-coded an expert system per industry — which people did try, and which is brutal to maintain.

b) The obvious version is unsafe, and that kills projects. Wire GPT to the rulebooks, ship it. It hallucinates a frequency. In aviation that's not a bug report, it's an incident. Most teams that get here either ship it anyway (and shouldn't) or abandon it. Getting past that requires accepting that the LLM must not be the last word — and building a boring deterministic rule engine downstream. That's unfashionable work.

c) It requires four disciplines at once. CV, quantile ML, agentic AI with RAG, and full-stack + DevOps. Plus enough domain knowledge to read ICAO and NERC documents. This repo had four owners specializing in four layers, with contracts.py fixing interfaces so they could build in parallel. A solo builder stalls; most orgs silo these people.

d) The customers are conservative and slow. Aviation and grid don't adopt unproven software. That's a rational deterrent to building it speculatively.

e) The incumbents are optimized elsewhere. NOAA's mandate is forecasting, not per-airline dispatch advice. Consultancies bill hours — automating themselves out of a per-event fee is not their incentive. Neither party is positioned to build this.

f) Space weather is episodic and easy to discount. Big storms are rare. Rare risks get underinvested until one lands. The 1989 Québec blackout and the 2003 Halloween storms are decades apart. Between events, budget goes elsewhere.

So: the gap persisted because it sits between institutions, requires four skill sets, requires reading regulatory PDFs, and has a conservative buyer for a rare risk. Not because it's a novel insight.

---

15. Gimmick or real impact?

Real, with a specific and stated asterisk.

What makes it real, not a demo:

1. They deleted their own ML when it wasn't defensible. The CNN was removed because no labeled data exists and DONKI already publishes reviewed kinematics. A gimmick adds AI for the pitch. This team removed it and wrote down why. That is the single strongest credibility signal in the repo.
2. The verifier does actual work. It's not decoration — it catches "21 MHz," rewrites it to 5, records the correction, and shows the operator both. It exists because RAG doesn't eliminate hallucination, and they knew that.
3. The failure modes are designed, not discovered. Every layer has a defined fallback, and every fallback errs toward caution: stub events, 20 m / 85% pessimistic defaults, ESCALATE TO SPECIALIST. And every degradation is visible — a flag, a health check, or a log event. Nothing degrades silently. That's an operations mindset, not a demo mindset.
4. The tests are real and target failure paths. ~137 Python, ~255 frontend, weighted toward what actually breaks in an ops console: 29 API client tests, 24 WebSocket tests (reconnect backoff, malformed frames, listener isolation), error-boundary suites.
5. The concurrency bugs are real bugs. The embedder prewarm is a genuine PyTorch meta-tensor race, found and fixed at the source rather than by adding a lock everywhere. The post-loop final drain in the event queue is a subtle correctness fix. You don't hit those without actually running the thing.
6. The gaps are documented, not hidden. "Training data is synthetic. Our R² measures rule-learning, not accuracy." A gimmick leads with 0.986. This repo leads with 0.986 and then tells you exactly what it doesn't mean.
7. The empty telecom_kb is deliberate. They left a knowledge base empty so the system would visibly emit LOW_COVERAGE. Choosing to demo your system's honesty about not knowing is the opposite of a gimmick.

Where it isn't proven yet:

- The impact models have never seen a real storm. Until OMNIWeb retraining happens, ② is an architecture, not a validated predictor.
- Live mode exists but isn't the demo path — two cached storms.
- CI doesn't block; there's no CD; metrics and rate limiting break past one replica.

Verdict: the architecture is real and would survive a regulator's questions. The empirical validation isn't there yet, and the docs say so plainly. That combination — sound design, honest gaps — is what a serious early-stage system looks like. A gimmick would have the opposite profile: impressive numbers, undisclosed foundations.

The tell, for me, is the direction of the exaggeration. Gimmicks overstate. This repo is written to understate its ML results.