**HelioOps**

Implementation Roadmap

Phased execution plan, milestones, dependencies, resource requirements, and risk
register

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

**Purpose**

This document defines the phased execution plan for HelioOps from hackathon
prototype through to a production\-grade commercial product\. It specifies
milestones, dependencies, ownership, resource requirements, and success gates at
each phase transition\.

# **1\. Guiding Principles**

- Ship working software at every phase boundary\. No phase ends with an
  incomplete product — each phase produces a demoable, testable artifact\.
- The March 2024 G4 storm replay is the continuous integration test\. If the
  system handles that storm end\-to\-end correctly, the phase gate passes\.
- Build the data flywheel from day one\. Every operator interaction must be
  logged even in Phase 0\.
- Zylon's existing service catalogue is the infrastructure constraint\. No
  technology not on Zylon's AWS stack in production without explicit
  architectural review\.

# **2\. Phase 0 — Hackathon MVP \(48 hours\)**

## **2\.1 Goal**

Produce a working demo of the full HelioOps pipeline using replayed March 2024
G4 storm data\. The demo must show: NOAA data ingestion → storm classification →
two industry advisories \(Aviation \+ Grid\) → dashboard with live agent
reasoning → CRM ticket creation\.

## **2\.2 Deliverables**

**Deliverable**

**Owner**

**Done When**

NOAA SWPC API integration \+ replay mode

Neal

3 storms can be replayed on demand from archive

Event Classifier \(Groq Llama 3\.3 70B\)

Neal

Correctly classifies March 2024 G4 storm parameters

Impact Router \(hardcoded matrix, 2 industries\)

Neal

Aviation and Grid are correctly selected for G4

Aviation KB \(20 docs, ChromaDB\)

Neal

RAG query returns ICAO HF procedure for G4 scenario

Grid KB \(15 docs, ChromaDB\)

Neal

RAG query returns NERC GMD protection procedure

LangGraph pipeline \(storm_detector → delivery\)

Neal

Full pipeline executes in < 3 minutes on demo laptop

FastAPI backend \+ WebSocket streaming

Neal

Reasoning tokens stream to frontend in real time

Next\.js dashboard \(MVP: storm banner \+ 2 cards\)

Neal

Dashboard shows both advisories with approve buttons

CRM ticket creation \(mock CRM\)

Neal

Ticket created and displayed after approval

Pitch deck \(10 slides\)

Neal

Covers problem, solution, demo, market, Zylon fit

## **2\.3 Out of Scope in Phase 0**

- Telecom and Maritime agents \(scoped for Phase 1\)
- Real email / Slack notification dispatch \(show UI mock only\)
- User authentication
- Production deployment \(runs on localhost for demo\)

# **3\. Phase 1 — Foundation \(Weeks 1–4 post\-hackathon\)**

## **3\.1 Goal**

Expand to all 4 industry agents, add real notification dispatch, deploy to
Railway \(production URL\), build out 5 full knowledge bases, and onboard a
first advisory reviewer \(space weather risk analyst or Zylon team member\)\.

## **3\.2 Milestones**

**Week**

**Milestone**

**Success Gate**

Week 1

Telecom \+ Maritime agents complete

All 4 agents produce correct advisories on March 2024 replay

Week 1

Full ChromaDB KBs ingested \(100\+ docs each\)

Aviation KB: ICAO NAT Doc 007 fully indexed; Grid KB: NERC GMD standard fully
indexed

Week 2

Sendgrid email \+ Slack Bolt integration live

Test advisory dispatched to internal Slack channel

Week 2

PostgreSQL schema deployed on Railway

All 5 tables created, migration scripts version\-controlled

Week 3

Human approval gate with 10\-minute auto\-approve timeout

Approval flow works; rejected advisory logged with reason

Week 3

Full feedback_log table live with operator action capture

5 simulated storm events logged with feedback

Week 4

Production deployment on Railway, HTTPS, DNS

Pilot reviewer can access dashboard and approve advisories

Week 4

Monitoring: Sentry \+ Grafana Cloud

Pipeline failure alerts firing to Slack \#heliops\-alerts

# **4\. Phase 2 — Production Ready \(Weeks 5–12\)**

## **4\.1 Goal**

Harden the system for a real paying client\. This includes client configuration,
white\-label/multi\-tenant capability, REST API, historical storm replay, and a
polished dashboard meeting the design spec in Document 4\.

**Feature**

**Priority**

**Effort \(dev\-days\)**

Per\-client impact matrix override \(YAML config\)

P0

3

Multi\-tenant architecture \(client_id isolation in DB\)

P0

5

REST API v1 with API key auth

P0

4

Historical storm replay UI \(date picker → replay\)

P1

3

Full Next\.js dashboard redesign \(Design Doc spec\)

P0

8

Kp sparkline \+ live solar wind chart

P1

2

Live agent reasoning panel \(right sidebar\)

P1

3

SMS notifications via Twilio \(CRITICAL only\)

P2

2

Custom stakeholder contact configuration per client

P0

2

Data flywheel model retraining pipeline \(weekly batch\)

P1

5

White\-label domain \+ branding config

P2

3

Pilot client onboarding \(Zylon target: Scandinavian airline\)

P0

10 \(sales \+ integration\)

# **5\. Phase 3 — Scale \(Months 4–6\)**

## **5\.1 Goals**

Migrate infrastructure to AWS ECS Fargate for HA\. Onboard second client\.
Expand knowledge bases with client\-specific content\. Begin building
defensibility through proprietary feedback dataset\.

**Milestone**

**Target Date**

AWS ECS Fargate migration with RDS multi\-AZ

Month 4

ChromaDB → Qdrant migration for production scale

Month 4

2nd paying client onboarded

Month 5

500\+ labeled storm\-advisory\-outcome triples in feedback_log

Month 5

Custom fine\-tuning run on feedback data \(LoRA on Llama 3 70B\)

Month 6

Space Weather Risk Analyst persona \(advisory drafting tool\)

Month 6

# **6\. Phase 4 — Expand Verticals \(Months 7–12\)**

## **6\.1 New Products Built on HelioOps Core**

- AeroCast — satellite re\-entry precision prediction API\. Reuses NOAA solar
  activity data ingestion; adds NORAD TLE tracking\.
- OrbitOps — CubeSat conjunction risk ops CRM\. Reuses LangGraph agent pattern;
  adds Space\-Track API integration\.
- Space Weather Insurance API — risk scoring and premium recommendation for
  satellite operators\. Reuses storm classification \+ impact routing\.

## **6\.2 5\-Client Revenue Model**

**Client Type**

**Setup \(SEK\)**

**Monthly Retainer \(SEK\)**

**Notes**

Scandinavian airline \(polar routes\)

200,000

50,000

Aviation \+ telecom advisories

Nordic TSO / grid operator

200,000

60,000

Grid advisory, GIC monitoring

Scandinavian telecom \(GPS infra\)

150,000

40,000

Telecom \+ GPS advisory

Baltic maritime shipping

150,000

35,000

Maritime \+ HF GMDSS advisory

Space weather risk consultancy

100,000

80,000

White\-label, all 4 agents

TOTAL \(5 clients, Year 1\)

800,000 setup

265,000 / month

ARR = ~SEK 3\.98M

# **7\. Critical Path & Dependencies**

**Dependency**

**Blocks**

**Mitigation if Delayed**

NOAA SWPC API availability

Entire pipeline

Pre\-download 90 days of archive\. System can run on cached data for weeks\.

Groq API access / quota

All 4 industry agents

Fallback to local Ollama \(Llama 3 8B — reduced quality but functional\)\.

ChromaDB KB population \(100\+ docs per domain\)

Advisory quality

Start with 20 docs per domain for Phase 0\. Quality improves with each doc
added\.

Pilot client commitment from Zylon network

Phase 2 revenue

Use Zylon's existing Swedish contacts\. Offer free 3\-month pilot with full
refund guarantee\.

Railway → AWS migration

Phase 3 HA

Railway can sustain 2\-3 clients\. Migration deferred to Month 4 if client count
stays low\.

# **8\. Risk Register**

**Risk**

**Probability**

**Impact**

**Owner**

**Mitigation**

Advisory hallucination causes operator error

Medium

Critical

Neal

Mandatory disclaimer on every advisory\. Human approval gate\. Low\-confidence
flag\.

NOAA API deprecates or changes format

Low

High

Neal

Monitor NOAA developer mailing list\. Implement adapter pattern for easy swap\.

Pilot client data privacy concerns \(advisory contents\)

Medium

High

Zylon

All client advisory data isolated by tenant\. No cross\-client model sharing
without consent\.

Competition from existing space weather consultancies

Low

Medium

Neal

Speed advantage: 3 minutes vs 2–4 hours is a 40x improvement\. Focus on SME
clients they don't serve\.

Hackathon judges unfamiliar with space weather

Medium

Medium

Neal

Demo the March 2024 G4 storm they can verify on Wikipedia\. Open with the ₹
cost, not the physics\.

# **9\. Resource Requirements**

## **9\.1 Hackathon \(48 hours\)**

**Resource**

**Requirement**

**Cost**

Groq API

Free tier — sufficient for demo

$0

OpenAI embedding API

~$0\.50 for KB ingestion

$0\.50

Railway deployment

Free tier \(500 hours\)

$0

NOAA SWPC data

Fully public, no API key

$0

Total hackathon cost

$0\.50

## **9\.2 Production \(Monthly, 5 clients\)**

**Resource**

**Specification**

**Monthly Cost \(USD\)**

AWS ECS Fargate \(2 tasks, 1 vCPU, 2GB\)

API \+ Agent service

~$80

AWS RDS PostgreSQL \(db\.t3\.small, multi\-AZ\)

Production database

~$60

AWS ElastiCache Redis \(cache\.t3\.micro\)

Session \+ pub/sub cache

~$20

Qdrant Cloud \(1GB plan\)

Vector store at scale

~$25

Groq API \(production tier\)

~500 advisory runs/month

~$50

Sendgrid \(Essentials\)

Email notifications

~$20

Sentry \+ Grafana Cloud

Monitoring

~$30

Total infrastructure \(5 clients\)

~$285/month

Revenue at 5 clients \(retainer only\)

~$13,500/month USD

Infrastructure as % of revenue

2\.1% — healthy margin
