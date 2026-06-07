**HelioOps**

Technical Specification

Architecture, tech stack, API contracts, database schema, and engineering
decisions

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

**Scope**

This document specifies the complete technical architecture of HelioOps v1\.0:
technology stack, system components, API contracts, database schema, integration
design, security model, and deployment architecture\. It is the reference
document for all engineering decisions\.

# **1\. Technology Stack**

**Layer**

**Technology**

**Rationale**

Agent Orchestration

LangGraph 0\.2 \(Python\)

Stateful multi\-node graphs with conditional edges, parallel branches, and Redis
checkpointing\. Native support for the fan\-out / fan\-in pattern required by
parallel industry agents\.

LLM Inference

Groq — Llama 3\.3 70B

Sub\-500ms inference latency at hackathon cost point \(~$0\.001 per advisory\)\.
Easy swap to Anthropic Claude or GPT\-4o for production\.

Vector Store / RAG

ChromaDB \(local, persistent\)

Zero infrastructure cost for v1\. Migrates to Qdrant or Pinecone at scale\. Five
separate collections, one per knowledge domain\.

Embedding Model

text\-embedding\-3\-small \(OpenAI\)

1536\-dim, $0\.00002/1K tokens\. Cached — embeddings are pre\-computed at KB
ingestion time\.

Backend API

FastAPI \(Python 3\.11\)

Async by default, native WebSocket support for streaming agent reasoning to
dashboard\. OpenAPI docs auto\-generated\.

Real\-time Push

WebSocket \(FastAPI native\) \+ Redis pub/sub

Agent reasoning streamed token\-by\-token to dashboard\. Redis pub/sub allows
multiple FastAPI workers to share WebSocket state\.

Database

PostgreSQL 15 \(RDS on AWS\)

Storm events, advisories, CRM tickets, feedback logs\. JSONB columns for
flexible advisory schema\.

Cache / State

Redis 7 \(ElastiCache\)

LangGraph checkpoint store\. API response cache \(NOAA data, 5\-min TTL\)\.
Deduplication set for alert IDs\.

Frontend

Next\.js 14 \(TypeScript, App Router\)

SSR for dashboard SEO\. Tailwind CSS\. Recharts for Kp sparklines\. WebSocket
hook for live updates\.

Scheduler

APScheduler \(Python\)

5\-minute NOAA polling loop\. Embedded in FastAPI process for v1\. Migrates to
Celery Beat at scale\.

Notifications

SendGrid \(email\) \+ Slack Bolt SDK

Transactional email with HTML templates\. Slack Block Kit messages with approve
/ reject interactive buttons\.

Infrastructure

Docker \+ Railway \(v1 hackathon\) → AWS ECS Fargate \(production\)

Railway for zero\-infrastructure\-cost deployment during hackathon\. ECS for
production HA\.

Monitoring

Sentry \(errors\) \+ Grafana Cloud free tier \(metrics\)

Agent chain errors and latency tracked\. NOAA polling success rate alerted\.

# **2\. System Architecture**

## **2\.1 Component Overview**

HelioOps has three logical layers: Data Ingestion, Agent Pipeline, and
Output/Delivery\. These map to three FastAPI services in production \(or one
monolith for v1\):

- Ingestion Service — NOAA poller, alert parser, deduplication, event queue
  writer\.
- Agent Service — LangGraph pipeline: event classifier, impact router, 4
  industry agents, advisory formatter, delivery agent\.
- Delivery Service — CRM ticket creation, notification dispatch, WebSocket push,
  dashboard API\.

## **2\.2 Data Flow**

1. APScheduler fires every 5 minutes, triggering the NOAA poller\.
2. Poller fetches Kp index, solar wind, and alert text concurrently\.
3. Trigger condition evaluated\. If no storm: log and return\.
4. Raw payload written to storm_events \(status=raw\)\. Alert ID written to
   Redis dedup set\.
5. LangGraph pipeline invoked with storm_event_id as input\.
6. Event Classifier node extracts StormEvent struct from raw payload\.
7. Impact Router determines affected_industries list\.
8. LangGraph fan\-out: all relevant industry agents run in parallel\.
9. Each agent: ChromaDB query \(top\-5 chunks\) → LLM invoke → AdvisoryOutput\.
10. Advisory Formatter aggregates all AdvisoryOutput objects\.
11. Delivery Agent creates CRM tickets, dispatches notifications, pushes to
    WebSocket\.
12. Dashboard receives real\-time update; operator reviews and approves\.
13. Approved advisory logged with outcome to feedback table \(data flywheel\)\.

# **3\. Database Schema**

## **3\.1 Tables**

### **storm_events**

**Column**

**Type**

**Description**

id

UUID PK

Auto\-generated

alert_id

VARCHAR\(64\) UNIQUE

Hash of NOAA alert text — used for deduplication

raw_payload

TEXT

Raw NOAA alert text

g_scale

SMALLINT

0–5

s_scale

SMALLINT

0–5

r_scale

SMALLINT

0–5

kp_index

DECIMAL\(4,1\)

0\.0–9\.0

eta_minutes

SMALLINT

Estimated Earth arrival time from L1

peak_window_start

TIMESTAMPTZ

Estimated peak impact start

peak_window_end

TIMESTAMPTZ

Estimated peak impact end

status

VARCHAR\(20\)

raw | classifying | routing | generating | formatting | delivered | resolved

created_at

TIMESTAMPTZ

UTC creation timestamp

resolved_at

TIMESTAMPTZ

NULL until storm passes

### **advisories**

**Column**

**Type**

**Description**

id

UUID PK

storm_event_id

UUID FK

References storm_events\.id

industry

VARCHAR\(20\)

aviation | grid | telecom | maritime

severity

VARCHAR\(10\)

CRITICAL | HIGH | MEDIUM | LOW

advisory_json

JSONB

Full AdvisoryOutput object

crm_ticket_id

UUID FK

References crm_tickets\.id

status

VARCHAR\(20\)

pending_review | approved | rejected | dispatched

confidence

DECIMAL\(3,2\)

LLM confidence score 0–1

approved_by

VARCHAR\(100\)

Operator name/ID — NULL if auto\-approved

approved_at

TIMESTAMPTZ

NULL until approved

generation_ms

INTEGER

Total agent generation time in milliseconds

### **feedback_log \(data flywheel\)**

**Column**

**Type**

**Description**

id

UUID PK

advisory_id

UUID FK

References advisories\.id

operator_action

VARCHAR\(30\)

approved | edited | rejected | escalated

edited_fields

JSONB

Which fields were changed and to what \(for training\)

outcome

VARCHAR\(30\)

actions_taken | false_positive | storm_subsided | n/a

operator_notes

TEXT

Free\-text feedback

logged_at

TIMESTAMPTZ

# **4\. API Contracts**

## **4\.1 Core REST Endpoints**

**Method**

**Path**

**Description**

**Auth**

GET

/api/v1/storms

List recent storm events with pagination

API key

GET

/api/v1/storms/\{id\}

Get full storm event with all advisories

API key

GET

/api/v1/advisories

List advisories, filterable by industry and status

API key

POST

/api/v1/advisories/\{id\}/approve

Approve advisory for dispatch

API key \+ role

POST

/api/v1/advisories/\{id\}/reject

Reject advisory with reason

API key \+ role

GET

/api/v1/dashboard/summary

Current storm status \+ active advisories

API key

POST

/api/v1/replay

Replay a historical storm from NOAA archive date

Admin only

GET

/ws/stream

WebSocket — real\-time agent reasoning \+ advisory updates

API key

## **4\.2 WebSocket Message Types**

**Event Type**

**Payload**

**Description**

storm\.detected

\{ event_id, g_scale, kp_index, eta_min \}

Fires when storm threshold crossed

agent\.thinking

\{ industry, token, cumulative_text \}

Streams LLM reasoning tokens in real time

advisory\.ready

\{ advisory_id, industry, severity, action_items \}

Advisory generation complete

advisory\.dispatched

\{ advisory_id, channels, ticket_id \}

Delivery confirmed

storm\.resolved

\{ event_id, duration_min \}

Storm window passed

# **5\. Integration Points**

## **5\.1 NOAA SWPC Integration**

**Parameter**

**Value**

Base URL

https://services\.swpc\.noaa\.gov

Authentication

None — fully public API

Rate limit

No documented limit\. HelioOps polls every 5 min \(12 calls/hour per endpoint,
36 total\)

Timeout

10 seconds per request\. Retry: 3x with exponential backoff

Caching

Redis, TTL = 5 minutes\. Serves cached response on API failure

Monitoring

Sentry alert if 3 consecutive poll failures across any endpoint

## **5\.2 Groq API Integration**

**Parameter**

**Value**

Model

llama\-3\.3\-70b\-versatile

Max tokens

1024 per advisory generation call

Temperature

0\.1 — low for deterministic advisory text

Timeout

15 seconds\. If exceeded: mark advisory as 'generation_timeout', flag for manual
review

Cost estimate

~$0\.001 per full pipeline run \(4 industry agents × ~200 input tokens \+ ~150
output tokens\)

# **6\. Security Model**

- All API endpoints require API key authentication \(header:
  X\-HelioOps\-Key\)\.
- Advisory approval / rejection requires role = 'operator' or 'admin'\.
  Read\-only operations accessible with role = 'viewer'\.
- API keys are SHA\-256 hashed before database storage\. Never stored in
  plaintext\.
- NOAA data is public — no credential management required for ingestion\.
- Groq and OpenAI API keys stored in AWS Secrets Manager, injected as
  environment variables at container start\.
- All advisory dispatch logs are append\-only in the audit trail\. No advisory
  record can be deleted — only soft\-archived\.
- Advisories contain an explicit disclaimer: 'For informational use only\.
  Verify against official sources before operational action\.'

# **7\. Performance Requirements**

**Requirement**

**Target**

**Critical Path**

Storm detection latency

< 5 minutes from NOAA alert

Polling interval

Event classification

< 2 seconds

Groq LLM call

Full pipeline \(detection → advisory dispatched\)

< 3 minutes

4 parallel LLM calls \+ ChromaDB queries

ChromaDB query latency

< 100ms per query

Local persistent store

WebSocket message delivery

< 50ms from event

Redis pub/sub \+ async push

Dashboard initial load

< 2 seconds

Next\.js SSR \+ API response time

API p99 response time

< 500ms

FastAPI \+ PostgreSQL query

System uptime target

99\.5% \(Phase 1\), 99\.9% \(Phase 3\)

AWS ECS \+ RDS multi\-AZ

# **8\. Architecture Decision Records**

## **ADR\-001: LangGraph over CrewAI**

**Decision**

Use LangGraph for agent orchestration\. NOT CrewAI or bare LangChain
AgentExecutor\.

Rationale: LangGraph provides explicit state management with TypedDict state
objects, deterministic conditional edges, and native support for parallel
branches via the fan\-out pattern\. CrewAI is opaque about intermediate state
and makes debugging production failures difficult\. The HelioOps parallel
industry agent pattern requires knowing exactly which agents fired, what they
returned, and how state was merged — LangGraph's Annotated state with
operator\.or\_ merge provides this cleanly\.

## **ADR\-002: ChromaDB over Pinecone for v1**

**Decision**

Use local persistent ChromaDB for all 5 RAG knowledge bases in v1\.

Rationale: Cost is $0 for ChromaDB at hackathon scale\. The 5 KBs combined are <
50MB\. Query latency meets the 100ms target on any modern server\. Migration
path to Qdrant or Pinecone at scale requires only swapping the VectorStore
adapter\. Pinecone's free tier is limited to 1 index; we need 5 separate domain
collections for isolation\.

## **ADR\-003: PostgreSQL with JSONB for advisory storage**

**Decision**

Store advisory content as JSONB in PostgreSQL, not in a document store\.

Rationale: The AdvisoryOutput schema will evolve as we add industries and
fields\. JSONB allows flexible schema without migrations while maintaining the
ability to query specific fields \(e\.g\., SELECT all advisories WHERE
advisory_json\->>'severity' = 'CRITICAL'\)\. The rest of the storm_events and
CRM tables benefit from relational integrity \(foreign keys, timestamps, status
enums\)\. A pure document store would sacrifice relational features without
gaining meaningful benefit at v1 scale\.
