**HelioOps**

Product Requirements Document

Vision, problem statement, target users, feature requirements, and success
metrics

**Field**

**Value**

Author

Neal Daftary — B\.Tech CSE AI/ML, Nirma University

Sponsor / Operator

Zylon Labs

Document Version

v1\.0 — Draft

Date

June 2026

Status

In Review

Classification

Confidential

# **1\. Executive Summary**

HelioOps is an AI\-native space weather intelligence platform that translates
real\-time NOAA solar weather alerts into industry\-specific operational
advisories for airlines, power grid operators, telecom companies, and maritime
shipping companies\. The platform ingests free public data from NOAA's Space
Weather Prediction Center \(SWPC\), classifies storm events, routes impact
assessments to domain\-specific LLM agents, and delivers actionable guidance to
the right operations team within three minutes of a NOAA alert — a task that
currently takes trained analysts 2–4 hours and is often skipped entirely\.

HelioOps is built as a vertical SaaS product for Zylon Labs, extending Zylon's
existing capabilities in AI automation, custom CRM, dashboards, and AWS
infrastructure into the aerospace intelligence vertical\. The platform targets
regulated industries in high\-latitude geographies \(Scandinavia, Canada, UK\)
that face acute space weather exposure, with an initial beachhead in the
Scandinavian market where Zylon already operates\.

**One\-Line Pitch**

Space weather affects every industry\. Nobody tells businesses what to do when a
storm hits\. HelioOps closes that gap with autonomous, industry\-specific ops
advisories delivered in under three minutes\.

# **2\. Problem Statement**

## **2\.1 The Gap**

The NOAA Space Weather Prediction Center issues alerts in real time for every
significant solar event\. These alerts contain precise physical measurements: Kp
indices, G\-scale classifications, solar proton flux, radio blackout levels\.
They are scientifically accurate and freely available\.

The problem is that the businesses most affected by these events — airlines
rerouting polar flights, grid operators protecting transformers from GIC damage,
telecom companies managing GPS accuracy degradation — do not have the domain
translation layer to act on them\. The alerts speak to physicists\. The
operations teams speak in ICAO procedures, NERC standards, GMDSS protocols, and
SLA thresholds\.

The translation today is entirely manual: a small number of specialist
meteorologists and space weather consultants who are expensive, not available
24/7, and serve a limited client base\. The rest of industry either ignores the
alerts entirely or acts too late\.

## **2\.2 Scale of the Problem**

**Industry**

**Primary Impact**

**Annual Cost of Inaction**

**Coverage Today**

Aviation

HF comms blackout, polar route diversions

$50–100M per major storm \(fuel, delays\)

Manual, airline\-by\-airline

Power Grid

GIC transformer damage, grid instability

$10–100B in extreme events \(Quebec 1989\)

Partial — NERC GMD standard only

Telecom / GPS

GPS accuracy degradation, satellite uplink fade

$1–5B in precision\-dependent services

Almost none at SME level

Maritime

GMDSS HF failures, AIS degradation

$500M\+ in rerouting and delays

Ad hoc, no systematic coverage

## **2\.3 The March 2024 G4 Storm — A Case Study**

On 10–11 May 2024, Earth experienced the strongest geomagnetic storm since 2003
\(Kp=9, G4/G5 peak\)\. Auroras were visible as far south as India and Texas\.
Documented impacts included: over 500 polar flight diversions, GPS accuracy
degraded by 15–40 metres on L1 civilian receivers, HF radio blackouts across the
North Atlantic, and emergency GIC warnings issued by grid operators in Canada,
the UK, and Scandinavia\. Every operator received the same generic NOAA text
alert\. No automated, industry\-specific advisory was dispatched to any of
them\.

# **3\. Product Vision**

**Vision Statement**

HelioOps becomes the operational backbone of space weather risk management for
every regulated industry — the system that turns a NOAA physicist's alert into a
fleet manager's work order, an airline dispatcher's re\-route, and a grid
operator's protection activation\. Every storm event becomes structured,
traceable, and learnable\.

## **3\.1 North Star Metric**

Time from NOAA alert issuance to industry\-specific operational advisory
delivered: target < 3 minutes, current baseline: 2–4 hours \(manual\) or never\.

## **3\.2 Product Principles**

- **An advisory that tells a Scandinavian Airlines dispatcher exactly which HF
  frequencies to switch to and which polar latitude to reroute below is worth
  100x more than a generic storm warning\.** Specificity over speed\.
- **Every advisory must conclude with a numbered action list, a time window, and
  a named responsible party\. No advisory should leave a human reader uncertain
  about what to do next\.** Actions, not information\.
- **The product creates a CRM ticket, a notification, and an audit trail for
  every advisory\. The loop closes when the operator confirms action or the
  storm window passes\.** Closed loop by default\.
- **Every operator interaction — approval, edit, rejection of an advisory — is a
  labeled training example\. The product must get measurably sharper every
  month\.** Compounding intelligence\.

# **4\. Target Users**

## **4\.1 Primary Personas**

**Persona**

**Role**

**Pain**

**What They Need from HelioOps**

Flight Dispatch Supervisor

Airlines — North Atlantic / Polar routes

HF comms degrade mid\-flight with no warning\. Fuel reserves for diversions are
finite\.

Specific HF backup frequencies, latitude threshold, estimated blackout window\.

Grid Operations Engineer

TSO / ISO — High\-latitude grids

GIC can damage transformers worth $10M\+ each\. NERC GMD requires a response
plan they struggle to operationalize\.

Specific transformer zones to monitor, activation steps, timing estimate\.

Network Operations Center \(NOC\) Lead

Telco / Satellite operator

GPS\-dependent services \(precision agriculture, autonomous vehicles\) SLA
breaches during storms\.

GPS accuracy degradation estimate, which client segments to alert, satellite
uplink margin\.

Fleet Operations Manager

Maritime shipping — high\-latitude routes

GMDSS HF failures leave vessels without primary comms\. AIS accuracy drops,
increasing collision risk\.

GMDSS backup channels, affected vessel list, AIS unreliability window\.

Space Weather Risk Analyst

Regulator / Reinsurer

Manual advisory writing is their full\-time job\. They serve 10 clients max\.

Automated first draft they can review and send in 2 minutes instead of 90\.

## **4\.2 Secondary Users**

- Emergency management agencies — municipal and national bodies needing
  infrastructure risk assessments\.
- Space insurance underwriters — needing real\-time storm context for claims and
  pricing\.
- Research institutions — needing structured storm event databases for academic
  work\.

## **4\.3 Non\-Users \(v1 Out of Scope\)**

- Individual consumers \(no B2C in v1\)
- Space tourism operators \(addressed in v2\)
- CubeSat / satellite operators \(separate product — OrbitOps\)

# **5\. Feature Requirements**

## **5\.1 Feature Overview**

**Feature Area**

**Priority**

**Phase**

Storm detection & polling \(NOAA SWPC API\)

P0 — Must have

Phase 1

Event classification \(G/S/R scale, Kp, ETA\)

P0 — Must have

Phase 1

Industry impact routing matrix

P0 — Must have

Phase 1

Aviation advisory agent \(RAG \+ LLM\)

P0 — Must have

Phase 1

Grid advisory agent \(RAG \+ LLM\)

P0 — Must have

Phase 1

Telecom advisory agent \(RAG \+ LLM\)

P1 — Should have

Phase 2

Maritime advisory agent \(RAG \+ LLM\)

P1 — Should have

Phase 2

Advisory formatter & CRM ticket creation

P0 — Must have

Phase 1

Email / Slack notification delivery

P0 — Must have

Phase 1

Multi\-industry live dashboard

P1 — Should have

Phase 2

Human review & approval gate

P1 — Should have

Phase 2

Feedback logging & data flywheel

P1 — Should have

Phase 2

Historical storm replay

P2 — Nice to have

Phase 3

Custom threshold configuration per client

P1 — Should have

Phase 2

White\-label / multi\-tenant mode

P2 — Nice to have

Phase 3

REST API for third\-party integration

P1 — Should have

Phase 3

## **5\.2 P0 Feature Descriptions**

### **F\-01: Storm Detection**

The system polls NOAA SWPC APIs on a 5\-minute cycle for Kp index, solar wind L1
data, and alert text\. A storm event is triggered when Kp >= 5\.0 \(G1
threshold\) or when an official NOAA Watch / Warning / Alert appears in the
alert feed\. The system must detect and trigger within one polling cycle of a
NOAA alert issuance\.

### **F\-02: Event Classification**

An LLM node parses the raw NOAA alert text and L1 solar wind velocity into a
structured StormEvent object: G\-scale \(0–5\), S\-scale \(0–5\), R\-scale
\(0–5\), Kp index \(float\), Earth arrival time estimate \(minutes from L1,
derived from solar wind speed\), and peak impact window \(UTC range\)\.

### **F\-03: Industry Impact Routing**

A deterministic matrix maps G/S/R scale to affected industries and severity
tiers\. G3\+ triggers Aviation \(CRITICAL\) and Grid \(CRITICAL\)\. G2\+
triggers Telecom \(HIGH\) and Maritime \(MEDIUM\)\. R2\+ additionally triggers
Aviation for HF blackout regardless of G\-scale\. The matrix is configurable per
client via YAML\.

### **F\-04 / F\-05: Industry Advisory Agents**

Each industry has a dedicated LangGraph node that: \(a\) retrieves relevant
context from a domain\-specific ChromaDB knowledge base using the storm
parameters as a query, \(b\) generates a structured advisory via Groq Llama 3\.3
70B, \(c\) returns a typed AdvisoryOutput object containing: severity,
action_items \(numbered list\), timing_window, technical_details,
affected_zones_or_routes, and reference_procedures\.

### **F\-06: Advisory Delivery & CRM**

A Delivery Agent node creates a CRM ticket per industry advisory, routes
email/Slack notifications to configured stakeholder contacts, and updates the
dashboard\. All actions are logged to the audit trail with timestamps\.

# **6\. Success Metrics**

## **6\.1 Core KPIs**

**Metric**

**Target**

**Measurement Method**

Advisory delivery time \(NOAA alert → dispatched\)

< 3 minutes

System timestamp comparison

Advisory accuracy \(action items validated by operator\)

> 85% correct at P1 launch

Operator feedback on CRM ticket

Storm coverage rate \(% of NOAA G1\+ events generating advisories\)

> 99%

NOAA archive vs HelioOps event log

Industry agents active

2 at launch \(Aviation \+ Grid\), 4 by Month 3

Feature flag tracking

False positive rate \(non\-events triggering advisories\)

< 5%

Operator rejection rate on CRM tickets

Data flywheel growth \(labeled examples per month\)

> 50 per storm event

DB record count

Paying clients \(Zylon revenue\)

1 pilot client by Month 3, 5 by Month 6

Contract signed

## **6\.2 Business Metrics for Zylon**

**Metric**

**Target \(12 months\)**

Setup revenue per client

SEK 150,000–250,000 \(approx\. ₹15–25K USD\)

Monthly retainer per client

SEK 30,000–60,000 \(approx\. ₹3–6K USD\)

Clients by end of Year 1

5 active paying clients

ARR target

SEK 2,000,000 \(approx\. ₹200K USD\)

Target verticals in Year 1

Aviation \+ Grid \(Scandinavia\-first\)

# **7\. Assumptions & Dependencies**

- NOAA SWPC APIs remain free and publicly accessible with no rate limiting that
  prevents 5\-minute polling\.
- Groq inference API provides < 500ms LLM response time for advisory generation
  at target throughput\.
- Industry knowledge bases \(ICAO procedures, NERC GMD standard, ITU ionospheric
  docs\) are publicly available for RAG ingestion without licensing
  restrictions\.
- Zylon Labs provides AWS infrastructure \(EC2, RDS, ElastiCache\) for
  production deployment\.
- Pilot clients exist in the Scandinavian market reachable via Zylon's existing
  network\.
- The March 2024 G4 storm data serves as the primary demo and validation
  dataset\.

# **8\. Risks & Mitigations**

**Risk**

**Probability**

**Impact**

**Mitigation**

NOAA API changes or downtime

Low

High

Cache last 24hrs of data; fallback to backup NOAA mirror; alert Ops on API
failure\.

LLM hallucination in advisory \(wrong frequencies / thresholds\)

Medium

High

Hard\-code all critical thresholds in the knowledge base\. Require operator
approval before dispatch\. Flag low\-confidence advisories\.

Regulatory liability for incorrect advisory

Medium

High

All advisories include explicit disclaimer: 'For informational purposes only\.
Verify against official NOTAMs and operational procedures before acting\.'

Low adoption — operators ignore advisories

Medium

Medium

Integration into existing ops CRM via webhook\. Make the advisory a push
notification, not a pull interface\.

Slow data flywheel due to infrequent storms

Low

Medium

Use the NOAA historical archive \(2000–2024\) to pre\-seed the feedback database
with 200\+ labeled storm events\.

# **9\. Out of Scope — v1**

- Space tourism passenger health risk advisory
- Satellite operator subsystem impact advisory \(OrbitOps is a separate
  product\)
- Re\-entry debris impact prediction \(AeroCast is a separate product\)
- Consumer\-facing space weather apps
- Real\-time financial market space weather indexing
- Integration with commercial space weather providers \(Spaceweather\.com,
  MeteoGroup\) — NOAA only in v1

# **10\. Timeline**

**Phase**

**Duration**

**Key Deliverables**

**Status**

Phase 0: Hackathon MVP

48 hours

Storm detection \+ Aviation \+ Grid agents \+ demo dashboard

In Progress

Phase 1: Foundation

Weeks 1–4

All 4 agents, CRM integration, Slack notifications, ChromaDB KBs

Planned

Phase 2: Production

Weeks 5–12

Human approval gate, data flywheel, white\-label, Zylon pilot client

Planned

Phase 3: Scale

Months 4–6

REST API, custom thresholds, historical replay, second pilot client

Planned

Phase 4: Expand

Months 7–12

Maritime \+ Space Weather Risk Analyst persona, multi\-tenant, 5 clients

Planned
