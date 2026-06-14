# HelioOps
## AI-Powered Space Weather Operations Platform

**Detect · Predict · Verify · Protect**

*Real-time solar storm intelligence for aviation, power grids, maritime, and telecom operations.*

---

---

## Slide 2 — Meet the Team

| Name | Role |
|------|------|
| **Parshva Shah** *(Team Lead)* | ML Impact Prediction — synthetic data pipeline, LightGBM quantile models |
| **Neal Daftary** | CV Detection — solar imagery processing, multi-source fusion, ML integration |
| **Priyanshu Doshi** | GenAI Advisory — AI agents, anti-hallucination pipeline, backend, database |
| **Tirth Patel** | Frontend Dashboard — deployment, DevOps, Kubernetes, monitoring |

---

---

## Slide 3 — The Invisible Threat Above Us

### What Is a Solar Storm?

The Sun does not simply shine light and warmth onto Earth. It also continuously fires a stream of charged particles into space — a stream called the solar wind. On most days, Earth's magnetic field deflects this stream harmlessly around the planet.

But several times a year, the Sun erupts. These eruptions release enormous quantities of magnetized plasma — billions of tons of it — and hurl it across the solar system at speeds reaching millions of kilometers per hour. When such an eruption is aimed at Earth, it is called a **solar storm**.

Solar storms come in three forms:

- **Coronal Mass Ejections (CMEs)** — The most dangerous type. A massive bubble of magnetized plasma is expelled from the Sun's outer atmosphere (the corona) and travels toward Earth. When it strikes, it compresses Earth's magnetic field and triggers the chain of effects described below.

- **Solar Radiation Storms** — High-energy particles — primarily protons — are accelerated to near-light speed by solar eruptions. These can penetrate spacecraft and affect satellites in orbit, as well as increase radiation exposure for aircrew on polar flight routes.

- **Geomagnetic Storms** — When a CME arrives at Earth, it disturbs the planet's magnetic field. This disturbance propagates through the atmosphere, the ionosphere (a charged layer of the upper atmosphere), and even into the ground, creating effects across the entire planet simultaneously.

### What Happens When a Storm Reaches Earth?

The effects are invisible — no sound, no flash, no visible warning — but the consequences across interconnected infrastructure are severe:

**Aviation**
High-frequency (HF) radio — the backbone of communication on long transoceanic flights, particularly over the North Atlantic — is disrupted or blacked out entirely. GPS navigation accuracy degrades. Pilots flying polar routes face increased radiation exposure, sometimes requiring aircraft to descend to lower, less efficient altitudes. Routes must be rerouted southward, adding hours of flight time and thousands of dollars in extra fuel per aircraft.

**Telecommunications and Navigation**
The GPS satellites in orbit transmit signals through the ionosphere to receivers on the ground. During a storm, the ionosphere becomes turbulent and delays those signals unpredictably, introducing positioning errors that can reach tens of meters. Satellite communication links experience signal degradation. These effects ripple into banking, logistics, emergency services, and precision operations that rely on GPS.

**Maritime Operations**
Ships at sea rely on HF radio and satellite communication for distress signaling, navigation, and weather updates. During a strong geomagnetic storm, GMDSS (Global Maritime Distress and Safety System) communication channels can fail, leaving vessels at sea without the legally mandated backup communication systems.

**Power Grids**
This is perhaps the least visible but most catastrophic effect. As the Earth's magnetic field is disturbed, it induces electrical currents — called Geomagnetically Induced Currents (GIC) — in long metallic conductors on the ground: power lines, pipelines, and railway tracks. In a power grid, these unexpected direct currents can saturate and overheat high-voltage transformers. A single failed extra-high-voltage transformer costs between three and ten million dollars and takes twelve to eighteen months to manufacture. There are no strategic spares.

A single extreme solar storm can trigger all of these failures simultaneously, across entire continents.

---

---

## Slide 4 — The Cost of Ignoring Space Weather

### The World Depends on Systems That Solar Storms Can Destroy

Modern civilization is built on infrastructure that is silently vulnerable to space weather: GPS-guided navigation, satellite communications, interconnected power grids, and HF radio networks. These systems were designed for the threat environment of the 20th century — not for extreme space weather events.

The consequences of ignoring this vulnerability are not theoretical. History has already demonstrated them.

---

**1989 — The Quebec Blackout**

On March 13, 1989, a powerful geomagnetic storm struck Earth. Geomagnetically Induced Currents surged through the power lines of Hydro-Québec, the electricity provider for the Canadian province of Quebec. Within 90 seconds, the entire Hydro-Québec network collapsed. Nine million people lost power in the middle of a winter night. The blackout lasted nine hours. Transformers were damaged beyond immediate repair. This event occurred during a relatively moderate storm by historical standards — not an extreme one.

---

**2003 — The Halloween Solar Storms**

Over several days in late October and early November 2003, the Sun unleashed a series of X-class solar flares — the most powerful category. The resulting geomagnetic storms were among the most intense ever recorded. Satellites experienced anomalies and outright failures. Aviation operators rerouted flights away from polar regions due to communication blackouts and elevated radiation. Power grids in Sweden experienced outages. The storm was strong enough that it disrupted operations at a level most operators had never prepared for.

---

**2024 — The Extreme G5 Solar Storm**

In May 2024, the most powerful geomagnetic storm in over twenty years struck Earth, reaching G5 status — the highest classification on the NOAA geomagnetic storm scale, equivalent to a Kp index of 9.0. A coronal mass ejection traveling at 2,200 km/s delivered a southward interplanetary magnetic field of negative 46 nanoteslas — a value that overwhelmed Earth's magnetic defenses.

GPS systems degraded across the globe. Satellite systems experienced disruptions. The aurora — normally visible only near the poles — was seen as far south as Florida, Texas, and Spain. Grid operators increased monitoring across vulnerable high-latitude regions.

This storm happened. The next one is not a question of if.

---

### The Core Challenge

The world has become increasingly effective at detecting and forecasting solar storms. NOAA's Space Weather Prediction Center issues watches, warnings, and alerts. Observatories around the planet monitor the Sun continuously.

But detection is only half the problem.

When a G4 or G5 alert is issued, the question that actually matters to the people responsible for keeping systems running is not *"Is there a storm?"* It is:

> **"What should I do right now — specifically, in my industry, with my equipment, under my regulatory obligations?"**

That question remains unanswered by existing systems. Today, operators across critical infrastructure receive generic alerts in text formats written for scientific audiences. Translating those alerts into verified, industry-specific, regulation-compliant operational actions still requires human experts working manually — slowly, inconsistently, and not always available when a storm strikes at 3 AM.

---

---

## Slide 5 — Why This Problem Is Still Unsolved

Despite decades of space weather research and investment, a fundamental operational gap persists. Understanding why requires looking honestly at where current systems fall short.

---

### Detection Exists — But Stops There

Space agencies and national meteorological services can detect, classify, and forecast solar storms with increasing accuracy. Solar imagery, magnetometer networks, L1 solar wind monitors, and space weather satellites provide a rich data picture.

The gap is not in detection. The gap is in what happens after detection.

Available data — solar imagery, CME observations, geomagnetic alerts — tells operators *that* a storm is happening and roughly *how severe* it is on a general scale. It does not tell them what specific actions their operations require, which regulatory procedures to invoke, or how severe the impact will be on their specific systems.

---

### Impact Remains Uncertain

Operators across aviation, grid management, maritime, and telecoms face questions that raw space weather data cannot answer:

- How much will GPS accuracy degrade — by one meter or by fifteen meters?
- What is the probability of a complete HF radio blackout on North Atlantic routes?
- Which transmission corridors in the grid are most at risk of transformer damage?
- Should we reroute now, or is there a four-hour window before the main wave arrives?

Most systems stop before estimating real-world operational impacts with the quantified confidence that safety-critical decisions require.

---

### AI Can Generate Advice — But Cannot Be Trusted Without Verification

Large language models — the AI systems behind tools like ChatGPT — can read space weather data and produce text that looks like an operational advisory. But in safety-critical industries, an advisory that *looks* correct and an advisory that *is* correct are very different things.

AI systems hallucinate. They produce technically plausible but factually wrong outputs, including:

- Wrong HF radio frequencies (e.g., recommending a frequency that is not authorized for North Atlantic aviation use)
- Incorrect reroute latitude thresholds (e.g., citing a reroute trigger at the wrong degree of latitude)
- Invalid regulatory procedure codes (e.g., citing a NERC operating step that does not exist)
- Severity underreporting (e.g., classifying a G4 situation as moderate when regulations require critical response)

In a context where a pilot or grid operator acts directly on an advisory, a hallucinated value is not an inconvenience — it is a safety risk.

---

### Human Experts Are the Bottleneck

Today, the translation from space weather alerts to operational decisions largely depends on experienced specialists. These experts are few in number, not available around the clock, variable in judgment, and unable to serve multiple industries simultaneously during the same storm event.

A G5 storm affecting aviation, power grids, maritime, and telecom at the same moment requires coordinated, simultaneous, multi-industry advisory generation. Manual expert response cannot provide that at the speed and scale required.

The problem is not that the expertise does not exist. The problem is that the expertise cannot scale.

---

---

## Slide 6 — Introducing HelioOps

### From Solar Storm Detection to Verified Operational Action

HelioOps is a real-time space weather operations platform that bridges the gap between raw heliospheric data and the specific, verified, regulation-compliant operational decisions that critical infrastructure operators need.

It does not simply warn that a storm is coming. It processes solar imagery, fuses data from multiple scientific instruments, predicts quantified operational impacts with statistical confidence intervals, generates industry-specific advisories grounded in the actual regulatory documents operators are required to follow, and verifies every single advisory against authoritative rule sets — all automatically, in real time, in parallel for four industries simultaneously.

---

### Four Core Capabilities

**Detect**
HelioOps ingests coronagraph imagery from solar telescopes and combines it with data from NASA's CME tracking database, NOAA's solar flare monitors, and the DSCOVR spacecraft that measures the solar wind arriving at Earth. A deterministic, physics-based algorithm processes this data to produce a structured, machine-readable storm event — with confidence scores, severity scales, and CME kinematics — that feeds every downstream component.

**Predict**
Six machine learning models translate storm measurements into operational impact forecasts: how many meters of GPS positioning error to expect, and what probability of HF radio blackout to plan for. Critically, these are not single-number guesses. Each prediction comes with a 95% confidence interval — a range that the system is statistically calibrated to contain the true value 95% of the time. Operators get the optimistic case, the most likely case, and the pessimistic case.

**Verify**
This is what makes HelioOps fundamentally different from any general-purpose AI advisory tool. After AI agents generate advisories, a separate, zero-AI rule engine checks every technical value against the authoritative regulatory sources. Wrong HF frequency? Corrected. Wrong reroute latitude? Corrected. Missing procedure reference? Flagged. Only advisories that pass this verification gate reach operators — and every correction made is logged and traceable.

**Deliver**
HelioOps streams verified advisories to operators through a real-time dashboard and API. Events flow through a WebSocket connection, so operators see each stage of the pipeline as it happens: detection complete, impact predicted, aviation advisory ready, verifier check passed. The entire chain from storm detection to verified advisory, for all four industries simultaneously, runs in under two minutes.

---

---

## Slide 7 — HelioOps System Architecture

HelioOps is built as four sequential layers, each producing structured output that feeds the next. No layer relies on a single data source or a single method — every layer has fallback mechanisms that prevent the system from failing silently.

---

### Layer 1 — Detection and Event Fusion

**Purpose:** Identify an incoming solar storm, characterize its severity, and produce a structured event record.

**What goes in:**
- Coronagraph imagery from CCOR-1 and SOHO/LASCO solar telescopes — sequences of images showing the Sun's outer atmosphere, where CMEs appear as expanding bright arcs against the background
- CME kinematic data from NASA DONKI — the Space Weather Database Of Notifications, Knowledge, Information, maintained by human analysts who review every significant eruption
- X-ray flux measurements from GOES satellites operated by NOAA — used to classify solar flares on the X/M/C scale and derive the Radio Blackout (R) scale
- Solar wind plasma measurements from DSCOVR at the L1 Lagrange point — particularly the north-south component of the interplanetary magnetic field (Bz), which determines how hard Earth's magnetic field is hit

**What comes out:**
A `StormEvent` — a structured data record containing storm severity (G, S, and R scales), CME speed and width, flare classification, solar wind measurements, and a composite confidence score.

**Innovation:**
- *Deterministic CME Detection*: Rather than training a neural network on labeled imagery — labeled data that does not exist at the required quality or scale — HelioOps uses a threshold-based detector on frame-difference imagery. The same input always produces the same output. The system is explainable, reproducible, and requires no GPU.
- *Physics-Based Fusion*: CME kinematics come from NASA's human-reviewed DONKI database, not from machine learning regression on imagery. This makes the outputs defensible in a regulatory context.
- *Resilient Fallback Chain*: If imagery is unavailable, the system uses cached frames. If the detector finds no CME, it uses a pre-computed fallback. If DONKI is unreachable, it uses cached kinematics. The pipeline never crashes.

---

### Layer 2 — Impact Intelligence

**Purpose:** Translate the storm characterization into quantified, operationally meaningful impact forecasts with statistical uncertainty bounds.

**What goes in:** The `StormEvent` from Layer 1, with its G-scale, solar wind Bz, CME speed, flare class, and other measurements.

**What comes out:** Two impact predictions, each with a median value and a 95% confidence interval:
- **GPS L1 Position Error** (in meters) — how much satellite navigation will degrade
- **HF Radio Blackout Probability** (0 to 100%) — the likelihood of complete HF communication loss

**Innovation:**
- *Six LightGBM Quantile Regression Models*: Rather than training one model to predict a single number, six separate models each predict a different point on the probability distribution: the 2.5th percentile (optimistic), the 50th percentile (median), and the 97.5th percentile (pessimistic). This approach — called quantile regression with pinball loss — produces calibrated uncertainty intervals without requiring complex distribution-fitting.
- *Quantified Uncertainty*: Operators receive not just a prediction but a statistical range they can trust. A 95% confidence interval means: in 95 out of 100 comparable situations, the true value falls within the stated range.
- *Conservative Fallback*: If the ML models are unavailable, the system defaults to GPS error of 20 meters and HF blackout probability of 85% — conservative estimates that lean toward caution rather than false reassurance.

---

### Layer 3 — Verified Advisory Engine

**Purpose:** Convert storm severity and impact predictions into industry-specific operational advisories that are grounded in regulatory documents and verified against authoritative rule sets.

This layer has three sub-components:

**Deterministic Routing (no AI involved):**
Before any AI system is invoked, a hardcoded matrix maps the storm's G-scale to a severity tier for each industry. This matrix is derived from NOAA's official Space Weather Scales and NESDIS industry impact briefings. G4 always means CRITICAL for aviation and power grids. This is not configurable or variable — it is an authoritative, auditable mapping that the AI cannot override downward.

**Four Parallel Industry Agents (AI-powered):**
Once routing is complete, four advisory agents run simultaneously — one for aviation, one for power grids, one for maritime, and one for telecom. Each agent:
1. Retrieves the most relevant passages from the regulatory knowledge base using semantic search — pulling, for example, the specific HF frequency tables from ICAO NAT Doc 007 for an aviation advisory
2. Constructs an advisory using Groq's Llama 3.3 70B language model at near-zero temperature (meaning: near-deterministic, not creative)
3. Validates that every action item cites a specific source document
4. Runs a separate self-check model to audit the advisory for claims that are not supported by the retrieved text
5. Retries up to three times if validation fails, feeding each error back into the next prompt
6. Falls back to "ESCALATE TO SPECIALIST" if all retries are exhausted

**Ten Anti-Hallucination Layers:**
Rather than relying on a single safeguard, HelioOps implements ten independent techniques: context-only grounding, mandatory citation enforcement, retrieval quality filtering, JSON schema validation, deterministic severity floor, source cross-checking, LLM self-checking, error-injected retries, confidence scoring, and conservative fallback. Each layer catches a different class of error.

**Deterministic Verifier (no AI involved):**
After advisories are generated, a pure rule engine checks every technical value against authoritative tables:
- HF frequencies must be in the set {3, 5, 8, 11, 17} MHz — the ICAO NAT-approved frequencies
- Reroute latitude thresholds must match the G-scale: G3 requires below 78°N, G4 below 70°N, G5 below 60°N
- Grid actions must reference valid NERC TPL-007-4 Appendix B operating procedures
- Maritime actions must reference valid GMDSS distress and working channels

If any value is wrong, the verifier corrects it, logs the correction, and streams the event to the dashboard. The final advisory reflects the corrected value, with a full audit trail showing what the AI originally wrote and what was changed.

**What comes out:** A `VerifiedAdvisory` for each triggered industry, containing numbered action items, severity level, timing window, confidence score, regulatory citations, verifier status, and a `ProvenanceTrace` — a six-step chain from raw solar data to final output that any auditor or regulator can follow.

---

### Layer 4 — Real-Time Delivery

**Purpose:** Present verified intelligence to operators at the moment decisions need to be made.

**Features:**
- **Live Dashboard** — A Next.js web application displaying the real-time pipeline: storm event details, impact predictions with confidence interval charts, and per-industry advisory cards with action items and confidence scores
- **REST API** — Full programmatic access for integration into operator systems
- **WebSocket Streaming** — Events are pushed to the dashboard as each stage completes, so operators see detection complete, then impact predicted, then each advisory as it generates, then each verifier check as it passes or corrects — in real time, not as a single batch at the end
- **Supabase PostgreSQL** — Optional persistent storage across eight tables, with full row-level security, preserving every storm event, prediction, advisory, and provenance trace

---

---

## Slide 8 — How the Four Layers Work Together

The diagram on this slide illustrates the complete data flow through the HelioOps pipeline, from raw solar imagery on the left to verified operator advisories on the right.

The key architectural property to understand is **layered independence**: each layer communicates with the next through a defined data contract — a structured format both layers agree on — rather than being tightly coupled. This means:

- Layer 1 can be updated with a new detection algorithm without changing anything in Layers 2, 3, or 4
- Layer 2 can be retrained on new data without affecting advisory generation
- Layer 3's regulatory knowledge bases can be updated when regulations change, without touching the ML models
- Layer 4's delivery mechanisms can evolve — new dashboards, new API formats — without altering any upstream logic

A second key property is **graceful degradation**: at every point in the pipeline, a failure in one component activates a defined fallback rather than crashing the system. Operators receive the best possible advisory given available data, with a clear indication of which components were operating normally and which were in fallback mode.

The pipeline connects two types of intelligence — deterministic rules and learned models — in deliberate sequence. Physics and regulatory rules govern what the system *must* do. AI handles the language and nuance of *how* it communicates that. The two are never confused.

---

---

## Slide 9 — Objectives

### Problem Statement

Critical infrastructure operators — commercial airlines, electricity grid companies, maritime vessel operators, and telecommunications providers — currently receive space weather alerts in formats designed for scientific audiences. These alerts communicate the existence and severity of a geomagnetic storm, but they do not translate that information into the specific, regulation-referenced operational actions that operators in each industry are required to take.

The result is a dangerous gap between awareness and action, one that widens under time pressure, at night, and during simultaneous multi-industry events. HelioOps was built to close that gap.

---

### Project Goals

1. Build a physics-based, deterministic solar storm detection pipeline that fuses coronagraph imagery, NASA CME data, NOAA flare measurements, and DSCOVR solar wind readings into a structured, machine-readable storm event — with no labeled training data, no GPU dependency, and fully reproducible output.

2. Develop quantitative impact prediction models that translate storm measurements into operationally meaningful numbers — GPS degradation in meters, HF blackout probability in percent — with calibrated 95% confidence intervals that operators can rely on for go/no-go decisions.

3. Create a verified AI advisory system that generates industry-specific operational advisories grounded in the actual regulatory documents (ICAO NAT Doc 007, NERC TPL-007-4, IMO GMDSS 2019) and verified by a deterministic rule engine that catches and corrects AI errors before advisories reach operators.

4. Deliver these capabilities through a real-time streaming interface — REST API, WebSocket, and live dashboard — that gives operators full situational awareness as the pipeline executes, not as a batch report after the fact.

---

### Expected Outcomes

- **Regulatory-grade advisories** with full traceability from raw solar data to final operator action, verifiable by any auditor
- **Calibrated uncertainty quantification** — 95% confidence intervals that contain the true impact value 95% of the time, giving operators a statistically honest picture of best-case, expected, and worst-case scenarios
- **Demonstrated hallucination resistance** — an AI system whose outputs are checked by a separate rule engine, ensuring that regulatory values (frequencies, latitudes, procedure codes) are always correct regardless of what the AI originally generated
- **Multi-industry parallel coverage** — four industries served simultaneously in a single pipeline run, replacing the need for four separate expert consultations

---

---

## Slide 10 — Methodology

HelioOps was built along two parallel tracks that ultimately converge in the Layer 3 advisory engine. Both tracks were developed independently and then integrated through defined data contracts.

---

### Track 1: Physics-First Detection Pipeline

The starting point was a fundamental design decision: not to train a machine learning model for CME detection.

The reason is practical. CME detection in coronagraph imagery requires a labeled dataset — sequences of frames annotated to show where a CME is present and where it is not. No publicly available dataset of this kind exists at the quality and scale required to train a reliable neural network. Attempting to use a small or poorly labeled dataset would produce a detector with unknown failure modes.

Instead, HelioOps uses a **threshold detector on running-difference frames**. Running-difference imaging is a standard technique in heliospheric science: subtract each frame from the one before it, so static background is eliminated and moving structures (like an expanding CME) appear as bright regions. The threshold detector identifies these bright regions using radial-profile analysis and classifies them as CME-present or CME-absent.

CME kinematics — speed, angular width, direction, and estimated Earth-arrival time — are sourced from **NASA DONKI** (the Space Weather Database Of Notifications, Knowledge, Information). DONKI is maintained by human analysts at NASA's Community Coordinated Modeling Center, who review every significant CME. Using this database rather than a learned regression model means the kinematic inputs are defensible in a regulatory context: they were produced by human experts, not inferred from images.

This detection output is fused with flare data from GOES XRS and solar wind data from DSCOVR L1 using a weighted confidence formula, producing a single structured `StormEvent`.

---

### Track 2: AI-Verified Advisory Pipeline

**Step 1 — Impact Quantification**

Six LightGBM gradient-boosted decision tree models were trained using the **pinball loss function** — a technique that trains each model to predict not the average outcome but a specific point on the outcome distribution. Three models predict GPS positioning error (2.5th, 50th, and 97.5th percentile), and three predict HF blackout probability (same percentiles).

Training used synthetic data generated from physical proxy relationships — known mappings between storm parameters (G-scale, Kp index, CME speed, Bz, flare class) and real-world impacts documented in historical event studies. Models were validated against both standard regression metrics and against a "black-swan anchor test" — the actual parameters of the May 2024 G5 storm — to confirm that the models perform correctly at the extreme end of the scale, not just on average.

**Step 2 — Regulatory Knowledge Base Construction**

Three regulatory documents were processed, chunked into 512-token segments, and embedded into a ChromaDB vector database using the BGE-small-en-v1.5 embedding model:
- ICAO NAT Doc 007 — the regulatory document governing HF radio use and polar route procedures for North Atlantic aviation
- NERC TPL-007-4 — the North American electric reliability standard covering grid operations during geomagnetic disturbances
- IMO GMDSS Resolution A.1001(25) — the maritime distress and safety communication standard

This knowledge base is what the AI advisory agents retrieve from when generating advisories. By restricting the AI to only the text it has retrieved, the system prevents it from inventing regulations or citing documents it has not read.

**Step 3 — Parallel Advisory Generation with Guardrails**

Four industry agents (aviation, grid, maritime, telecom) run simultaneously using AgentScope's message protocol. Each agent retrieves the most relevant regulatory passages using semantic similarity search, constructs a prompt containing storm data and retrieved context, and generates a structured advisory using Groq's Llama 3.3 70B language model.

Ten independent validation layers check the output before it advances. A separate, lighter-weight AI model then audits the advisory in "critic mode" — a different cognitive orientation that is more effective at catching inconsistencies than having the same model check its own output.

**Step 4 — Deterministic Verification**

After all agents complete, a pure Python rule engine (no AI) checks every technical value in every advisory against authoritative tables: ICAO HF frequency sets, G-scale reroute latitude thresholds, NERC operating procedure keywords, and GMDSS distress channel identifiers. Any violation is corrected in place, logged, and streamed to the dashboard.

---

---

## Slide 11 — Tools and Materials

### Technology Stack

**Layer 1 — Detection**

| Tool | Purpose |
|------|---------|
| Python 3.12 | Core language for all pipeline components |
| OpenCV / NumPy | Image processing, running-difference frame computation |
| NASA DONKI API | CME kinematic data (speed, width, direction, arrival estimate) |
| NOAA GOES XRS API | Solar flare X-ray flux classification |
| NOAA DSCOVR API | L1 solar wind measurements (Bz, speed, density) |
| Pydantic | Structured data validation for `StormEvent` schema |

**Layer 2 — Impact Prediction**

| Tool | Purpose |
|------|---------|
| LightGBM | Gradient-boosted quantile regression models |
| scikit-learn | Training infrastructure, cross-validation |
| Optuna | Automated hyperparameter tuning |
| pandas / NumPy | Feature extraction and data manipulation |
| joblib | Model serialization and checkpoint loading |

**Layer 3 — Advisory Generation**

| Tool | Purpose |
|------|---------|
| Groq API (Llama 3.3 70B) | Primary advisory generation (primary agent) |
| Groq API (Llama 3.1 8B) | Hallucination self-check (lightweight critic model) |
| AgentScope | Multi-agent orchestration and parallel message passing |
| LangChain-Groq | LLM interface and structured output formatting |
| ChromaDB | Embedded vector database for regulatory knowledge storage |
| BGE-small-en-v1.5 | Sentence embedding model for semantic retrieval |
| tiktoken | Token counting for prompt budget management |
| pdfplumber | PDF parsing for regulatory document ingestion |

**Layer 4 — Delivery**

| Tool | Purpose |
|------|---------|
| FastAPI | REST API and WebSocket server |
| uvicorn | ASGI server for async Python |
| structlog | Structured JSON logging |
| pydantic-settings | Configuration management via environment variables |
| Next.js 14 | React-based frontend dashboard |
| TypeScript | Type-safe frontend development |
| Tailwind CSS | Dashboard styling |
| Supabase (PostgreSQL) | Optional persistent storage with row-level security |

**Infrastructure and DevOps**

| Tool | Purpose |
|------|---------|
| Docker | Containerization (multi-stage builds for backend and frontend) |
| Docker Compose | Local development environment |
| Kubernetes | Production container orchestration |
| Terraform | Cloud infrastructure provisioning (AWS EKS) |
| ArgoCD | GitOps continuous deployment |
| Prometheus | Metrics collection |
| GitHub Actions | CI/CD pipeline (lint → test → build → Docker) |
| Chaos Mesh | Controlled failure injection for resilience testing |

---

### Regulatory Source Materials

The advisory knowledge base is constructed from primary regulatory documents — the same documents that operators in each industry are legally required to follow:

| Document | Industry | Contents Used |
|----------|----------|---------------|
| **ICAO NAT Doc 007** (2025 edition) | Aviation | HF frequency allocations, polar route reroute procedures, communication backup protocols |
| **NERC TPL-007-4** Appendix B | Power Grid | Geomagnetic disturbance operating procedures, GIC monitoring steps, protective actions |
| **IMO GMDSS Resolution A.1001(25)** | Maritime | Distress communication channel assignments, backup communication procedures |
| **NOAA/NESDIS Space Weather Scales** | All industries | G/S/R scale definitions, industry impact matrix, severity classifications |

By grounding advisories in these exact documents — and verifying every numerical value against them — HelioOps produces output that operators can act on without having to independently verify regulatory compliance.

---

---

## Slide 12 — Project Results

### Machine Learning Performance

**GPS L1 Position Error Model (GPS Degradation Prediction)**

The model predicts how many meters of positioning error to expect during a storm event.

| Metric | Value | What It Means |
|--------|-------|---------------|
| R² Score | **0.9858** | The model explains 98.6% of the variation in GPS error across storm events — near-perfect statistical fit |
| MAE (Mean Absolute Error) | **0.15 meters** | On average, the median prediction is off by 15 centimeters |
| RMSE | 0.44 meters | Larger errors are rare; the model does not systematically miss extreme events |
| 95% CI Coverage (PICP) | **96.4%** | When the model says "the true value is between X and Y with 95% confidence," it is correct 96.4% of the time |
| CI Width (PINAW) | 0.047 | The confidence intervals are tight — useful for decision-making, not just wide safety margins |

**HF Radio Blackout Probability Model**

The model predicts the probability (0–100%) that HF radio communication will be completely disrupted.

| Metric | Value | What It Means |
|--------|-------|---------------|
| R² Score | **0.9577** | 95.8% of variation in blackout probability is explained by the model |
| MAE | **3.2%** | On average, the predicted blackout probability is within 3.2 percentage points of the true value |
| RMSE | 4.3% | Consistent accuracy with no large systematic errors |
| 95% CI Coverage (PICP) | **94.8%** | Calibration is accurate — the 95% confidence interval contains the true value in ~95% of cases |
| CI Width (PINAW) | 0.194 | Intervals are appropriately sized — informative without being falsely precise |

---

### Black-Swan Validation: The G5 Anchor Test

A model that performs well on average is not necessarily useful for operational safety. The events that matter most are the extreme ones — the black-swan events that fall outside the typical training distribution.

To validate that the models handle extreme events correctly, they were tested against the actual measured parameters of the May 2024 G5 storm:
- CME speed: 1,800 km/s
- Kp index: 9.0 (maximum)
- G-scale: G5 (extreme)

Physical requirements for a genuine G5 event: GPS error must exceed 15 meters, and HF blackout probability must exceed 80%.

| Metric | Model Prediction | Physical Requirement | Result |
|--------|-----------------|---------------------|--------|
| GPS L1 Error | **17.50 meters** | > 15 meters | **Passed** |
| HF Blackout Probability | **84.3%** | > 80% | **Passed** |

The models did not just fit average behavior. They learned the physics of extreme space weather and extrapolate correctly to the most dangerous events.

---

### Verifier Performance: Live Hallucination Correction

The deterministic verifier — the rule engine that checks every advisory value against authoritative regulatory tables — demonstrated its value in live pipeline runs:

**Example: HF Frequency Correction**
When running the G5 storm pipeline, the AI-generated aviation advisory included the HF frequency "21 MHz." The valid ICAO NAT frequency set for North Atlantic operations is {3, 5, 8, 11, 17} MHz. 21 MHz is not in this set.

The verifier caught the error, identified the nearest valid frequency (5 MHz — the ICAO-recommended G4+ backup frequency), corrected the advisory text in place, logged the correction with the original AI output preserved, and streamed the event to the dashboard as a "blocked" check.

This is not an edge case. Language models hallucinate specific technical values even when the correct value is present in the retrieved context. The verifier is why HelioOps advisories can be acted on without additional expert review.

---

### End-to-End Pipeline Validation

Both demo storms — the October 2024 G4 event and the May 2024 G5 event — were run through the complete pipeline:

- Layer 1 detection completed successfully for both storms, producing structured `StormEvent` records
- Layer 2 impact predictions completed with realistic values across both storms (lower impact for G4, extreme impact for G5)
- Layer 3 generated advisories for all four industries in parallel for both storms
- Layer 4 delivered all events through the real-time WebSocket stream to the dashboard

The full pipeline — from storm ID to four verified advisories — completes in under two minutes.

---

---

## Slide 13 — Discussion

### What the Results Actually Mean

The performance metrics reported for the ML models are striking — R² of 0.9858 for GPS error, 96.4% coverage probability for confidence intervals. But results should be interpreted carefully in context.

The models were trained on **synthetic data** — data generated from physical proxy relationships rather than from historical observations. This is not a weakness unique to this project; operational-quality historical space weather impact data across all four industries does not exist as a consolidated, labeled dataset. The synthetic training approach encodes known physical relationships (Kp index and GPS degradation, CME speed and arrival time, solar wind Bz and geomagnetic storm intensity) into the models.

The G5 anchor test — passing the requirement that the model correctly predicts extreme impacts for the most severe storm in recent history — provides confidence that the learned relationships generalize appropriately. The next step for production deployment would be retraining and validating against NASA OMNIWeb historical records and documented operational impact data from past major events.

---

### The Most Important Finding: The Verifier Is Non-Optional

The single most significant architectural finding from this project is not a performance metric. It is the behavior of the AI advisory agents without the deterministic verifier.

Language models hallucinate specific technical values even with retrieval-augmented generation. In testing, advisory agents consistently produced plausible but incorrect values for HF frequencies, reroute latitudes, and regulatory procedure references. These errors were not detectable from the structure or tone of the advisory — they sounded exactly as authoritative as correct values.

The deterministic verifier caught and corrected these errors every time. This finding has a direct architectural implication: in any domain where AI-generated content must comply with specific numerical or categorical requirements (frequencies, thresholds, procedure codes, regulatory references), a post-generation verification layer is not optional. It is the load-bearing safety component of the system.

---

### The Telecom Coverage Gap

The telecom knowledge base is currently empty — no authoritative, machine-readable regulatory document specifically governing space weather responses for telecommunications infrastructure exists in the public domain. As a result, the telecom advisory agent always produces an advisory flagged as `LOW_COVERAGE`, with the primary action being "ESCALATE TO SPECIALIST."

This is not a failure of the architecture. It reveals a gap in the broader space weather preparedness ecosystem. The HelioOps architecture is ready to serve telecom operators as soon as appropriate regulatory source documents become available.

---

### Deterministic Methods in a Machine Learning World

The choice to use a threshold detector for CME detection — rather than training a convolutional neural network on imagery — runs against the common assumption that machine learning always produces superior results. In this case, the choice was correct for the following reasons:

- No labeled coronagraph CME dataset of operational quality exists
- A threshold detector on running-difference frames produces byte-identical output for the same input: reproducible, auditable, and explainable to a regulator
- The approach requires no GPU, no retraining, and no distribution shift monitoring
- The physics of CME appearance in running-difference imagery is well-understood and directly encodable as geometric rules

The lesson generalizes: in domains where labeled data is scarce, where explainability is a regulatory requirement, and where reproducibility is essential, deterministic methods should be evaluated seriously before defaulting to learned models.

---

---

## Slide 14 — Conclusion

### What HelioOps Demonstrates

HelioOps demonstrates that the gap between raw space weather data and verified operational decisions is not a fundamental limitation — it is an engineering problem with a solvable architecture.

By combining deterministic physics (for detection and verification), calibrated machine learning (for impact quantification), and constrained AI generation (for advisory language), HelioOps produces outputs that are more trustworthy than either pure AI or pure human expert systems could produce alone.

The key insight is the **separation of concerns**: language models are good at translating information into natural, actionable language. Rule engines are good at guaranteeing that specific values are correct. Quantile regression models are good at producing calibrated uncertainty intervals. Assigning each role to the right tool — rather than asking any single component to do everything — is what makes the system viable for safety-critical use.

---

### The Architecture Is Replicable

The four-layer pattern HelioOps implements — detect, predict, generate, verify — is not specific to space weather. Any domain that requires AI-assisted decision-making under regulatory constraints can benefit from the same architecture:

- A regulatory compliance advisory system for financial services
- An AI-assisted triage tool in emergency medicine
- Automated safety reporting for industrial operations
- Regulatory guidance for pharmaceutical manufacturing

The core principle is always the same: let AI generate, then let rules verify.

---

### What Comes Next

The immediate next step is retraining the impact prediction models on historical observational data from NASA OMNIWeb and documented industry impact records, replacing the synthetic training dataset with real-world measurements.

The second priority is expanding the telecom regulatory knowledge base as authoritative source documents become available, bringing the fourth industry to full advisory capability.

The third is expanding coverage — additional regulatory frameworks, additional geographies (European grid standards, Asia-Pacific aviation procedures), and a live CCOR-1 data feed for real-time rather than replay-based detection.

---

---

## Slide 15 — Future Work

### Towards Production-Grade Space Weather Operations

HelioOps in its current form is a validated demonstration of the full pipeline. The path to operational deployment involves several clearly defined next steps.

**Real-World Training Data**
The impact prediction models are currently trained on synthetic data derived from physical proxy relationships. Production deployment requires retraining against NASA OMNIWeb historical solar wind data correlated with documented operational impact records from grid operators, aviation authorities, and maritime agencies. The model architecture requires no changes — only the training dataset.

**Live Data Integration**
The current system operates in replay mode using cached data from two known storm events. Full operational deployment requires real-time integration with:
- CCOR-1 live imagery from NOAA
- GOES XRS live feed for real-time flare monitoring
- DSCOVR real-time solar wind data
- NOAA SWPC alert stream

The `detect_live()` function in the codebase is already implemented and callable — the integration work is primarily in data access and rate management.

**Telecom Regulatory Knowledge Base**
The telecom advisory agent is architecturally complete but cannot generate well-grounded advisories until authoritative regulatory source documents for space weather telecom response are ingested into ChromaDB. Engagement with ITU-R and national telecom regulatory bodies would be required to identify and obtain suitable source documents.

**Multi-Region Coverage**
Current regulatory coverage is North Atlantic / North American:
- ICAO NAT Doc 007 (North Atlantic HF operations)
- NERC TPL-007-4 (North American grid)
- IMO GMDSS (international maritime)

Expanding to European grid standards (ENTSO-E), Asia-Pacific aviation procedures, and regional maritime frameworks would require ingesting additional regulatory documents and adjusting verifier rule tables — no architectural changes.

**Probabilistic Storm Forecasting**
HelioOps currently responds to confirmed storm events. An upstream layer that ingests NOAA 24/72-hour space weather forecasts and generates probabilistic pre-event advisories — "G4 conditions have a 65% probability within 36 hours — begin preflight preparation now" — would significantly increase operational value.

---

---

## Slide 16 — References

### Regulatory and Technical Standards

- **ICAO NAT Doc 007** — Rules of the Air and Air Traffic Services, North Atlantic Operations and Airspace Manual. International Civil Aviation Organization, 2025 edition.

- **NERC TPL-007-4** — Transmission System Planned Performance for Geomagnetic Disturbance Events. North American Electric Reliability Corporation, Appendix B: Benchmark GMD Event and Procedure.

- **IMO Resolution A.1001(25)** — Criteria for the Provision of Mobile Satellite Communication Systems in the Global Maritime Distress and Safety System. International Maritime Organization, GMDSS framework.

- **NOAA Space Weather Scales** — G/S/R scale definitions and industry impact matrix. National Oceanic and Atmospheric Administration / NESDIS, Space Weather Prediction Center.

### Data Sources

- **NASA DONKI** — Space Weather Database Of Notifications, Knowledge, Information. Community Coordinated Modeling Center, NASA Goddard Space Flight Center.

- **NOAA GOES XRS** — Geostationary Operational Environmental Satellite X-ray Sensor data, accessed via NOAA Space Weather Prediction Center API.

- **NOAA DSCOVR L1** — Deep Space Climate Observatory real-time solar wind data, L1 Lagrange point, NOAA operational satellite.

### Historical Events

- Bolduc, L. (2002). *GIC observations and studies in the Hydro-Québec power system.* Journal of Atmospheric and Solar-Terrestrial Physics, 64(16), 1793–1802.

- Lloyd's of London and Cambridge Centre for Risk Studies (2013). *Solar Storm Risk to the North American Electric Grid.*

- NOAA SWPC (2024). *May 2024 Extreme Geomagnetic Storm Event Summary.* Space Weather Prediction Center operational reports.

---

---

## Slide 17 — Thank You

### HelioOps — AI-Powered Space Weather Operations Platform

*Detect · Predict · Verify · Protect*

---

Solar storms do not wait. The gap between a NOAA alert and a verified operational decision has existed for decades. HelioOps closes that gap.

We built a system that fuses solar imagery with NASA physics data, quantifies operational impact with statistical confidence, generates regulatory-grounded advisories using AI, and verifies every value with rules that cannot hallucinate.

The May 2024 G5 storm was not the last extreme event. The infrastructure that powers aviation, the electric grid, maritime operations, and global telecommunications remains silently exposed.

HelioOps is the answer to the question operators actually need answered:

> **Not "is there a storm?" — but "what do I do right now?"**

---

**Team HelioOps**

| | |
|-|-|
| Parshva Shah *(Lead)* | Neal Daftary |
| Tirth Patel | Priyanshu Doshi |

*Contact: builtbyneal@gmail.com*

---

*Thank you for your time and attention.*
