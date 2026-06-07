**HelioOps**

Feature Specification

Detailed user flows, edge cases, acceptance criteria, and dependencies per
feature

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

This document specifies the detailed behaviour of every HelioOps feature: user
flows, edge cases, acceptance criteria, and dependencies\. Engineers treat this
as the definitive source of 'what correct looks like' for each feature\.

# **1\. Storm Detection \(F\-01\)**

## **1\.1 Overview**

The Storm Detector is a background service that runs continuously, polling three
NOAA SWPC endpoints every 5 minutes\. It is the single entry point for all storm
events in the system\.

## **1\.2 NOAA Endpoints**

**Endpoint**

**Data**

**Poll Interval**

**Trigger Condition**

services\.swpc\.noaa\.gov/json/planetary_k_index_1m\.json

Kp index, 1\-min cadence

5 min

Kp >= 5\.0

services\.swpc\.noaa\.gov/products/alerts\.txt

Official Watch / Warning / Alert text

5 min

Any new WATCH, WARNING, or ALERT string in feed

services\.swpc\.noaa\.gov/json/goes/primary/xrays\-6\-hour\.json

GOES X\-ray flux \(M/X\-class flares\)

5 min

Flux >= M5\.0 class \(R2\+ radio blackout\)

## **1\.3 User Flow**

1. Scheduler ticks every 5 minutes\.
2. Fetch all 3 endpoints concurrently\.
3. Evaluate trigger conditions\. If none met: log 'no event', return\.
4. If triggered: write raw payload to storm_events table with status='raw',
   publish to event_queue\.
5. Storm Detector emits 'storm\.detected' event consumed by Event Classifier\.

## **1\.4 Edge Cases**

**Edge Case**

**Expected Behaviour**

NOAA API returns 429 / 503

Retry with exponential backoff \(1s, 2s, 4s\)\. After 3 failures, alert Ops via
Slack \#heliops\-alerts\. Cache last\-known\-good response for up to 30 min\.

Kp spikes then drops within one polling cycle

Trigger advisory if peak Kp >= threshold even if current Kp has dropped\.
Include 'Storm subsiding, peak passed' note in advisory\.

Multiple storms in 24\-hour window

Each storm is a separate event\. Advisories are additive — a 'storm ongoing'
banner persists on dashboard until all events resolve\.

NOAA alert for same event appears twice \(duplicate\)

Deduplicate by alert_id hash\. Do not re\-trigger advisory for same event\.

Test / drill alerts from NOAA

Filter alerts containing 'TEST' or 'DRILL' in text\. Log but do not trigger
pipeline\.

## **1\.5 Acceptance Criteria**

- GIVEN a Kp reading >= 5\.0, WHEN the poller runs, THEN a storm event is
  created and the pipeline is triggered within one polling cycle \(max 5 min\)\.
- GIVEN NOAA API is unreachable, WHEN the poller runs, THEN no false storm event
  is created and an Ops alert is sent after 3 consecutive failures\.
- GIVEN a duplicate NOAA alert, WHEN the poller processes it, THEN no second
  advisory is dispatched for the same event\.

# **2\. Event Classification \(F\-02\)**

## **2\.1 StormEvent Schema**

The classifier produces a typed StormEvent object used by all downstream nodes:

**StormEvent TypedDict**

g_scale: int \(0–5\) | s_scale: int \(0–5\) | r_scale: int \(0–5\) | kp_index:
float \(0–9\) | eta_minutes: int | peak_window_utc: str \(ISO 8601 interval\) |
confidence: float \(0–1\) | raw_alert_id: str

## **2\.2 ETA Calculation**

ETA to Earth is calculated from L1 solar wind velocity \(km/s\)\. L1 is
approximately 1\.5 million km upstream of Earth\. ETA = 1,500,000 /
solar_wind_speed_kmps / 60 \(minutes\)\. For a typical solar wind speed of 500
km/s: ETA = 50 minutes\. This is included in every advisory as the 'impact
window opens in X minutes' statement\.

## **2\.3 Acceptance Criteria**

- GIVEN NOAA alert text for the March 2024 G4 storm, WHEN classified, THEN
  g_scale=4, kp_index>=8\.0, eta_minutes between 30–60\.
- GIVEN ambiguous or partial alert text, WHEN confidence < 0\.7, THEN advisory
  is flagged as 'low confidence — verify before dispatch'\.

# **3\. Impact Routing \(F\-03\)**

## **3\.1 Default Impact Matrix**

**Storm Scale**

**Aviation**

**Power Grid**

**Telecom/GPS**

**Maritime**

G1 \(Kp=5\)

LOW — monitor HF

LOW — monitor GIC

NONE

NONE

G2 \(Kp=6\)

MEDIUM — HF degraded

MEDIUM — GIC elevated

LOW — GPS minor drift

LOW — HF margin reduced

G3 \(Kp=7\)

HIGH — partial blackout

HIGH — GIC significant

MEDIUM — GPS degraded

MEDIUM — HF unreliable

G4 \(Kp=8–9\)

CRITICAL — blackout

CRITICAL — transformer risk

HIGH — GPS 10–40m error

HIGH — GMDSS failure risk

G5 \(Kp=9\+\)

CRITICAL — full blackout

CRITICAL — grid instability

CRITICAL — L1 GPS unusable

CRITICAL — HF blackout

## **3\.2 Client Override**

Operators can override the default matrix via a YAML config\. Example: an
airline that specifically flies polar routes above 80N may set their Aviation
trigger at G2 rather than G3\. These overrides are stored per\-client in the
config service and applied before routing\.

# **4\. Aviation Advisory Agent \(F\-04\)**

## **4\.1 Knowledge Base Contents**

- ICAO NAT \(North Atlantic Track\) space weather procedures \(Doc 007\)
- Published HF frequency management tables \(3, 5, 8, 11, 17 MHz bands\) for
  North Atlantic and polar communications
- SELCAL channel degradation thresholds and backup procedures
- Airline\-published polar route rerouting decision criteria \(public FAA/ICAO
  filings\)
- Historical advisories from Finnair, SAS, British Airways for past G3\+ storms
- NOAA/NWS aviation weather guidance for space weather events

## **4\.2 Output Schema**

**Field**

**Type**

**Example**

severity

string

CRITICAL

action_items

list\[string\]

\['Re\-route all flights above 78N', 'Switch HF to 8825 kHz backup', \.\.\.\]

timing_window

string

2024\-05\-11T06:00Z / 18:00Z

affected_routes

list\[string\]

\['NAT Track A', 'NAT Track B', 'Polar 1', 'Polar 2'\]

hf_frequencies_affected

list\[string\]

\['13360 kHz', '11279 kHz', '8831 kHz'\]

hf_backup_frequencies

list\[string\]

\['8825 kHz', '11384 kHz', '17946 kHz'\]

polar_latitude_threshold

float

78\.0

reference_procedures

list\[string\]

\['ICAO NAT Doc 007 §3\.4', 'SELCAL System User Manual §7\.2'\]

precedent_storms

list\[string\]

\['Sep 2017 G4 — Finnair FIN006 rerouted via same parameters'\]

confidence

float

0\.91

## **4\.3 Acceptance Criteria**

- GIVEN a G3 storm event, WHEN aviation agent runs, THEN action_items list is
  non\-empty and includes at least one specific HF frequency and one specific
  latitude threshold\.
- GIVEN a G1 storm event, WHEN aviation agent runs, THEN severity is LOW and
  action_items contains a monitoring instruction only\.
- GIVEN no aviation impact in routing matrix, WHEN aviation agent runs, THEN it
  skips gracefully and returns None without error\.

# **5\. Grid Advisory Agent \(F\-05\)**

## **5\.1 Knowledge Base Contents**

- NERC GMD \(Geomagnetic Disturbance\) reliability standard — full text
- GIC \(Geomagnetically Induced Current\) protection procedures for 400kV
  transmission systems
- Transformer vulnerability tables by design type \(single\-phase vs
  three\-phase, core design\)
- Svenska kraftnät \(Swedish TSO\) published space weather response procedures
- National Grid \(UK\) GMD response protocols
- Published GIC monitoring data from Halloween 2003 and March 2024 storms

## **5\.2 Key Logic — Geographic Risk Zones**

GIC risk scales with geomagnetic latitude\. Zones A \(> 60 degrees geomagnetic
latitude — Scandinavia, Canada, Scotland, Alaska\), B \(50–60 degrees — Central
Europe, Northern USA\), C \(below 50 degrees — low risk except in extreme G5
events\)\. The advisory must identify which transformer zones are in the
client's operational footprint and prioritize accordingly\.

# **6\. Advisory Delivery & CRM \(F\-06\)**

## **6\.1 CRM Ticket Schema**

**Field**

**Value**

ticket_id

UUID — auto\-generated

storm_event_id

FK to storm_events

industry

aviation | grid | telecom | maritime

severity

CRITICAL | HIGH | MEDIUM | LOW

title

Auto: 'G\{n\} Storm — \{Industry\} Advisory — \{date\}'

body

Formatted action_items \+ technical_details

assignee

Configured stakeholder contact per client

status

pending_review | approved | rejected | actioned | resolved

created_at

UTC timestamp

approved_at

UTC timestamp — null until operator approves

outcome

null | 'actions_taken' | 'false_positive' | 'storm_subsided'

## **6\.2 Notification Channels**

- Email — Sendgrid / SMTP, HTML template with severity colour coding
- Slack — Block Kit message to configured channel, with one\-click
  approve/reject actions
- Webhook — POST to client\-configured endpoint for CRM integration
- SMS \(Phase 2\) — Twilio, CRITICAL severity only

## **6\.3 Human Approval Gate**

All advisories are held in 'pending_review' status for a configurable window
\(default: 10 minutes for CRITICAL, 30 minutes for HIGH, 60 minutes for
MEDIUM\)\. If no action is taken within the window, the advisory is
auto\-approved and dispatched\. Operators can approve, edit, or reject via the
dashboard or Slack button\. Every action is logged to the audit trail\.

# **7\. Dashboard \(F\-07\)**

## **7\.1 Dashboard Components**

**Component**

**Description**

**Update Frequency**

Storm Status Banner

Full\-width bar showing current storm scale, colour\-coded: gray \(calm\), amber
\(watch\), orange \(warning\), red \(critical\)

Real\-time WebSocket

Kp / Solar Wind Timeline

24\-hour sparkline of Kp index and solar wind speed with threshold markers

5 min

Industry Advisory Cards

One card per affected industry, showing severity, top 3 action items, CRM ticket
status, and approve / reject buttons

Real\-time

Storm History Table

Last 30 storm events with advisory count, response time, operator feedback
rating

On page load \+ daily

Live Agent Reasoning Panel

Scrolling log of LLM reasoning steps, RAG retrieval context, and tool calls
during advisory generation

Real\-time streaming
