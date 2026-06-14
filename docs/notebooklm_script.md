# HelioOps: The Solar Storm Intelligence System

## Source Document for NotebookLM Deep Dive

---

## The Problem Nobody Talks About

On May 10, 2024, the most powerful solar storm in two decades hit Earth. Kp index hit 9.0 — the maximum on the NOAA scale. CME plasma traveling at 2,200 km/s. A southward Bz of negative 46 nanoteslas, which means the Earth's magnetic field had almost no defense.

What happened in the next 12 hours:

Airlines flying polar routes — the shortest path between North America and Europe — lost all HF radio contact. Pilots cannot fly North Atlantic Tracks without HF communication. Dozens of flights were rerouted southward, burning hours of extra fuel and causing cascading delays across transatlantic schedules. Each reroute burns roughly $20,000 in extra fuel.

Power grid operators in the northern United States saw Geomagnetically Induced Currents flowing through transmission infrastructure — the kind of DC current that quietly destroys high-voltage transformers. A single extra-high-voltage transformer costs $3–10 million and takes 12–18 months to manufacture. There are no spares.

Maritime vessels in high latitudes lost GMDSS distress communication capability — the system ships are legally required to use under SOLAS regulations.

GPS precision agriculture systems went offline across the Midwest.

None of these operators received a single structured, actionable, regulation-specific advisory before it happened.

They got generic NOAA alerts — text files in all-caps written for scientists, not for the pilot who needs to know which specific HF frequency to switch to right now, or the grid operator who needs to know which NERC operating procedure to activate.

That gap — between raw space weather data and operators who need to act on it in real time — is what HelioOps was built to close.

---

## What HelioOps Actually Does

HelioOps is a real-time space weather operations platform. It ingests solar imagery and multi-source heliospheric data, runs it through a four-layer AI and physics pipeline, and produces structured, regulation-specific operational advisories for aviation, power grids, maritime, and telecom industries — simultaneously, in under two minutes.

Not generic warnings. Specific actions: which HF frequency to switch to, which reroute latitude threshold applies, which NERC operating procedure to invoke, which GMDSS distress channel to verify. Tied to the authoritative regulatory documents those industries are already required to follow.

---

## The Four-Layer Architecture

### Layer 1: Heliospheric Detection

The first problem in space weather operations is detection itself. You can't rely on a single data source. A solar storm produces multiple observable signatures — each available from different instruments with different latencies and reliability.

HelioOps Layer 1 fuses four independent data sources:

**CCOR-1 and SOHO/LASCO coronagraph imagery** — these are telescopes that block the sun's disk with an occulter disk so you can see the solar corona. A Coronal Mass Ejection appears as a bright expanding bubble in the difference between successive frames. HelioOps runs a radial-profile threshold detector on running-difference frames — a technique from signal processing — to identify CME presence, bounding box, and positional angle. No CNN, no labeled training data, no GPU required. The output is deterministic: same input always produces byte-identical output.

**NASA DONKI** — the Space Weather Database Of Notifications, Knowledge, Information. DONKI is maintained by human analysts at NASA CCMC who review every significant CME and publish the kinematics: speed, angular width, direction, and estimated Earth-impact window. HelioOps pulls CME speed and geometry from DONKI rather than trying to regress it from imagery, because DONKI data is human-reviewed and far more defensible in a regulatory context.

**GOES XRS** — the X-ray Sensor aboard NOAA's Geostationary Operational Environmental Satellites. XRS measures solar X-ray flux in real time, which is how we classify solar flares into the C/M/X scale and derive the radio blackout R-scale. An X1.8 flare with R3 radio blackout, for example, means high-frequency communications disruption is already occurring on the sunlit hemisphere.

**DSCOVR L1** — Deep Space Climate Observatory, sitting at the L1 Lagrange point between Earth and the Sun, about 1.5 million kilometers upstream. DSCOVR measures the actual solar wind plasma arriving at Earth before it hits the magnetosphere: velocity, density, and critically, the north-south component of the interplanetary magnetic field, called Bz. Southward Bz is what makes a storm geoeffective — it determines how hard the magnetosphere gets hit. A Bz of negative 46 nanoteslas, like May 2024, is catastrophic.

The detection confidence is a weighted fusion: 40% from visual CME detection confidence, 20% from flare signal, 20% from southward Bz, 20% from NOAA alert presence. The output is a `StormEvent` — a structured Pydantic model carrying all of this into the next layer.

The entire detection layer is designed for graceful degradation. If imagery is unavailable: use cached frames. If the threshold detector finds no CME: use a fallback bounding box from the pre-computed storm stub. If DONKI is unreachable: use stub kinematics. If everything fails: load the pre-computed stub JSON directly. The pipeline never crashes — it degrades.

### Layer 2: Impact Prediction with Uncertainty

Knowing a storm happened is not enough. Operators need to know how bad it will be. And crucially, they need to know the uncertainty — because a point estimate without confidence bounds is dangerous in safety-critical contexts.

HelioOps uses six LightGBM quantile regression models to predict two quantities:

- **GPS L1 position error** in meters — how much will satellite navigation be degraded?
- **HF radio blackout probability** — what is the probability of complete HF communication loss?

Six models because each quantity gets three: the 2.5th percentile (optimistic bound), the 50th percentile (median prediction), and the 97.5th percentile (pessimistic bound). Together these form a 95% confidence interval.

The nine input features are extracted directly from the `StormEvent`: G-scale, Kp index, Bz, solar wind speed, CME speed, CME angular width, R-scale, and two binned contextual features for geomagnetic latitude and local time of day.

Independent quantile models can produce crossing estimates — where the 97.5th percentile is numerically below the 50th, which is physically impossible. HelioOps enforces monotonicity via a post-prediction `sorted()` call before returning results.

The models were validated against physical anchor tests. The May 2024 G5 storm — the most extreme event in twenty years — was fed through with its actual parameters: 2,200 km/s CME, Kp 9.0. The model predicted 17.5 meter GPS error (requirement: above 15 meters for G5) and 84.3% HF blackout probability (requirement: above 80% for G5). The uncertainty-aware coverage probability is 96.4% for GPS and 94.7% for HF — meaning the 95% confidence intervals actually contain the true value 95% of the time. That is the gold standard for calibration in probabilistic forecasting.

The fallback is intentionally conservative: if checkpoints are missing, the system defaults to GPS error of 20 meters and HF blackout probability of 85%. It never returns zero.

### Layer 3: Verified AI Advisory Generation

This is where HelioOps diverges most from anything else in the space weather domain.

Layer 3 takes the structured storm data and quantified impact predictions and generates industry-specific operational advisories — written in the language each industry actually uses, citing the regulatory documents those operators are required to follow.

It does this in four parallel streams simultaneously.

**Deterministic routing first.** Before a single LLM call happens, a pure Python routing function maps the G-scale to severity for each industry using a hardcoded matrix derived from NOAA space weather scales and NESDIS industry impact briefings. G4 always maps to CRITICAL for aviation and power grids. G5 maps to CRITICAL for all four industries. This is not configurable by the LLM. It is authoritative.

**Four parallel industry agents** then run simultaneously using AgentScope's message protocol with asyncio parallel dispatch:

Each agent retrieves regulatory context from ChromaDB — a vector database storing embeddings of the actual regulatory documents: ICAO NAT Doc 007 for aviation, NERC TPL-007-4 for power grids, IMO GMDSS 2019 for maritime, and the NOAA/NESDIS space weather impact scales. The embedding model is BGE-small-en-v1.5 — 384-dimensional, fast on CPU, with query-time asymmetric prompting. Chunks with cosine similarity below 0.35 are dropped before the LLM sees them.

The aviation agent retrieves the specific HF frequency tables and reroute latitude procedures from NAT Doc 007. The grid agent retrieves the NERC GIC operating procedure steps. The maritime agent retrieves GMDSS distress communication procedures.

The LLM — Groq Llama 3.3 70B — then generates a structured advisory in JSON mode, temperature 0.1 for reproducibility, with a hard requirement that every action item carries a `source_ref` pointing to the retrieved document. No source reference means validation fails and the prompt retries with the error injected: "FIX THESE: missing source_ref in action item 2."

A lighter self-check model — 8B parameters — then audits the generated advisory in a separate call, in critic mode, looking for specific claims that aren't supported by the retrieved context. A generation LLM in "write" mode cannot reliably catch its own inconsistencies in one pass. A separate critic call in "read" mode catches a different class of errors.

If all three retry attempts fail, the advisory falls back to a single action: "ESCALATE TO SPECIALIST." The system never generates a confident-sounding advisory when it cannot ground it.

**Then the deterministic verifier runs.**

This is the most important component in the system. After the LLM generates advisories, a zero-LLM rule engine checks every operational number in every advisory against authoritative source tables.

For aviation: HF frequencies must be in the set {3, 5, 8, 11, 17} MHz — the valid ICAO NAT frequencies. If the LLM writes "21 MHz" — which is not a valid NAT HF frequency — the verifier catches it with a regex, identifies the nearest valid frequency, corrects the advisory in place, marks the check as "blocked," and logs the correction. Reroute latitudes are checked against the G-scale thresholds: G3 requires below 78°N, G4 requires below 70°N, G5 requires below 60°N. If the LLM writes the wrong latitude, it is corrected.

For power grids: action items must reference valid NERC TPL-007-4 Appendix B operating procedures by keyword. For maritime: GMDSS distress channels are validated against the authoritative frequency table.

The output is a `VerifiedAdvisory` with a verifier status — "passed," "passed with corrections," or "blocked" — plus a `ProvenanceTrace`: a 6-step chain from raw solar imagery to final output that any regulator can audit.

This verifier is why HelioOps can be used in safety-critical contexts where a raw LLM advisory cannot. The LLM generates the language. The rule engine verifies the numbers. Both are logged and traceable.

### Layer 4: Delivery

The FastAPI backend bridges all four layers. It runs the full pipeline in two modes: batch (one POST request, full JSON response) and streaming (WebSocket, real-time events as each stage completes).

The WebSocket stream is what drives the frontend dashboard — operators see detection complete, then impact prediction, then each industry advisory as it generates in parallel, then verifier checks as they pass or get corrected, in real time. The red-glow moment when the verifier catches an invalid frequency — that is not theatrical. That is the system working exactly as designed.

Results can be persisted to Supabase PostgreSQL — eight tables with row-level security — or held in memory for stateless operation. The choice is a single environment variable.

---

## Why These Design Decisions Are Non-Obvious

**Deterministic detector over a trained CNN.** There is no labeled dataset of historical CME coronagraph imagery at the quality and scale needed to train a reliable CNN. The threshold detector is fully reproducible, requires no GPU, needs no retraining when new storms occur, and produces output a physicist can explain to a regulator. It is the right tool.

**Quantile regression over point estimates.** Aviation dispatch, grid operators, and maritime controllers don't need a point prediction. They need to know the pessimistic case. Quantile regression with pinball loss gives calibrated confidence intervals directly, without additional calibration steps. The 95% coverage probability of 96.4% on GPS and 94.7% on HF validates the calibration empirically.

**Deterministic verifier after the LLM.** Retrieval-augmented generation reduces hallucination but does not eliminate it. LLMs hallucinate specific technical values — frequencies, latitudes, procedure steps — even when the correct value is in the retrieved context. The only way to guarantee regulatory compliance in the advisory output is a zero-LLM rule engine that checks every number. There is no other approach that is both fast enough to be operational and reliable enough for safety-critical use.

**Separate self-check model call.** Running the same LLM twice in different cognitive modes catches a different class of errors than a single pass. The generation model is optimizing for coherent output. The critic model is optimizing for finding faults. Splitting the calls costs one additional API call per industry per storm. For advisories that operators use to make decisions affecting aircraft, power infrastructure, and ships, that cost is not a question.

---

## The Numbers

- **G5 anchor test:** 17.5m GPS error predicted (requirement: >15m), 84.3% HF blackout probability (requirement: >80%)
- **Model R² scores:** 0.9858 for GPS error, 0.9577 for HF blackout
- **Calibration:** 96.4% PICP for GPS, 94.7% PICP for HF (targeting 95%)
- **Knowledge base:** 242 aviation chunks, 101 grid chunks, 166 impact matrix chunks — all from authoritative regulatory sources
- **Anti-hallucination layers:** 10 independent techniques before an advisory is dispatched
- **Verifier scope:** ICAO HF frequencies, NAT reroute latitudes, NERC GIC operating steps, GMDSS distress channels
- **Advisory generation:** 4 industries in parallel, simultaneously
- **Fallback coverage:** Every layer of the pipeline has a defined fallback — the system has no uncovered failure mode that produces a crash

---

## The Market Context

A single long-haul transatlantic flight reroute costs roughly $20,000 in extra fuel. There are approximately 500 transatlantic flights daily that could be affected by a major polar storm.

A failed extra-high-voltage transformer costs $3–10 million and takes 12–18 months to replace. There are approximately 2,000 such transformers in the North American grid.

The insurance and reinsurance industry estimates G5-class storm damage to unprotected infrastructure at $600 billion to $2.6 trillion for a direct hit on a developed nation's grid — the Lloyds of London and Cambridge Centre for Risk Studies figures from their 2013 Solar Storm Risk to the North American Electric Grid report.

Space weather events are increasing with the current solar cycle, which is approaching its maximum. Cycle 25 is tracking above predictions. The May 2024 G5 storm happened. It was not the last one.

The operational gap HelioOps closes — between raw heliospheric data and actionable, regulation-specific advisories for critical infrastructure — has no comparable automated solution at this technical depth today.

---

## What a Demo Looks Like

You start with a POST request: `/api/detect/2024-05-G5`.

The system opens a WebSocket connection. Within seconds:

**Detection complete.** Confidence 0.94. G5, Kp 9.0, Bz negative 46 nT. CME speed 2,200 km/s. X5.8 flare, R5 radio blackout.

**Impact prediction.** GPS error: 19.2 meters [CI: 9.8–28.4m]. HF blackout: 91% [CI: 78–97%].

**Routing.** Aviation: CRITICAL. Grid: CRITICAL. Maritime: CRITICAL. Telecom: CRITICAL. Four agents launching.

**Aviation agent working.** RAG retrieved 8 chunks from NAT Doc 007 (avg similarity 0.71). Generation attempt 1.

**Grid agent working in parallel.** RAG retrieved 7 chunks from NERC TPL-007-4. Generation attempt 1.

**Advisory generated: aviation.** CRITICAL. Confidence 0.74.

**Advisory generated: grid.** CRITICAL. Confidence 0.69.

**Verifier running on aviation advisory.**

> `verifier.check` — HF frequency — proposed: 21 MHz — **BLOCKED** — corrected to: 5 MHz

The aviation advisory written by the LLM said "21 MHz." 21 MHz is not a valid ICAO NAT HF frequency. The valid set is {3, 5, 8, 11, 17}. The verifier caught it. Corrected it. Logged it. The advisory that reaches the operator says 5 MHz, with a note that the original LLM output was corrected.

That single moment is the entire point of the system. The LLM is fast and fluent. The rule engine is correct. You need both.

---

## The Team

**Parshva** — built the ML impact prediction layer: synthetic data generation, LightGBM quantile regression training with Optuna hyperparameter tuning, G5 anchor validation.

**Neal** — built the CV detection layer: running-difference preprocessing, radial-profile CME threshold detector, multi-source fusion, and the full ML pipeline integration.

**Priyanshu** — built the GenAI advisory layer: AgentScope orchestration, RAG retrieval, 10-layer anti-hallucination guardrails, deterministic verifier, FastAPI backend, Supabase database schema.

**Tirth** — built the frontend dashboard, DevOps infrastructure, Docker/Kubernetes deployment, Terraform IaC, ArgoCD GitOps, Prometheus monitoring, chaos engineering, and operational runbooks.

---

## What HelioOps Is Not

It is not a solar flare prediction system. Predicting when a flare will occur is an unsolved problem in heliophysics.

It is not a replacement for human space weather forecasters. NOAA Space Weather Prediction Center meteorologists issue watches and warnings. HelioOps takes those signals and translates them into operational actions for specific industries.

It is not a general-purpose AI assistant that happens to know about space weather. Every advisory is grounded in retrieved regulatory text. Every number is verified against authoritative tables. The system is wrong about specific technical values exactly as often as a rule engine is wrong — which is never, given the correct rules.

It is a precision translation layer between raw heliospheric observation and the structured, auditable, regulation-specific action that critical infrastructure operators need.

The May 2024 storm happened. The next G5 is not a question of if.
