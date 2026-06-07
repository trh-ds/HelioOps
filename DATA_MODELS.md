# Data Models

## Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   storm_events   │       │    advisories    │       │   crm_tickets    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (UUID PK)     │◄──────│ id (UUID PK)     │◄──────│ id (UUID PK)     │
│ alert_id (UNIQUE)│       │ storm_event_id   │       │ advisory_id      │
│ raw_payload      │       │ industry         │       │ assignee         │
│ g_scale          │       │ severity         │       │ title            │
│ s_scale          │       │ advisory_json    │       │ body             │
│ r_scale          │       │ crm_ticket_id    │       │ status           │
│ kp_index         │       │ status           │       │ outcome          │
│ eta_minutes      │       │ confidence       │       │ created_at       │
│ peak_window_start│       │ approved_by      │       │ closed_at        │
│ peak_window_end  │       │ approved_at      │       └──────────────────┘
│ status           │       │ generation_ms    │               │
│ created_at       │       │ created_at       │               │
│ resolved_at      │       └────────┬─────────┘               │
└──────────────────┘                │                        │
                                    │                        │
                                    │  ┌──────────────────┐  │
                                    └──│  feedback_log    │──┘
                                       ├──────────────────┤
                                       │ id (UUID PK)     │
                                       │ advisory_id      │
                                       │ operator_action  │
                                       │ edited_fields    │
                                       │ outcome          │
                                       │ operator_notes   │
                                       │ logged_at        │
                                       └──────────────────┘

┌──────────────────┐
│    api_keys      │
├──────────────────┤
│ id (UUID PK)     │
│ key_hash         │
│ role             │
│ client_id        │
│ description      │
│ is_active        │
│ created_at       │
│ last_used_at     │
└──────────────────┘
```

---

## storm_events

Stores raw NOAA alert data and classified storm parameters.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | Auto-generated |
| alert_id | VARCHAR(64) | UNIQUE, NOT NULL | SHA-256 hash of NOAA alert text — dedup key |
| raw_payload | TEXT | NOT NULL | Raw NOAA alert text or JSON |
| g_scale | SMALLINT | 0–5 | Geomagnetic storm scale |
| s_scale | SMALLINT | 0–5 | Solar radiation storm scale |
| r_scale | SMALLINT | 0–5 | Radio blackout scale |
| kp_index | DECIMAL(4,1) | 0.0–9.0 | Planetary K index |
| eta_minutes | SMALLINT | > 0 | Estimated Earth arrival time from L1 |
| peak_window_start | TIMESTAMPTZ | | Estimated peak impact start |
| peak_window_end | TIMESTAMPTZ | | Estimated peak impact end |
| status | VARCHAR(20) | NOT NULL, default 'raw' | raw → classifying → routing → generating → formatting → delivered → resolved |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | UTC creation timestamp |
| resolved_at | TIMESTAMPTZ | | NULL until storm passes |

**Indexes**: `idx_storm_events_status` on `status`, `idx_storm_events_created_at` on `created_at`

---

## advisories

Stores per-industry advisory outputs from the agent pipeline.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Auto-generated |
| storm_event_id | UUID | FK → storm_events.id, NOT NULL | Parent storm event |
| industry | VARCHAR(20) | NOT NULL | aviation, grid, telecom, maritime |
| severity | VARCHAR(10) | NOT NULL | CRITICAL, HIGH, MEDIUM, LOW |
| advisory_json | JSONB | NOT NULL | Full AdvisoryOutput object |
| crm_ticket_id | UUID | FK → crm_tickets.id | CRM ticket reference |
| status | VARCHAR(20) | NOT NULL, default 'pending_review' | pending_review → approved/rejected → dispatched |
| confidence | DECIMAL(3,2) | 0.00–1.00 | LLM confidence score |
| approved_by | VARCHAR(100) | | Operator name/ID (NULL if auto-approved) |
| approved_at | TIMESTAMPTZ | | NULL until approved |
| generation_ms | INTEGER | | Agent generation time in ms |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | |

**Indexes**: `idx_advisories_storm` on `storm_event_id`, `idx_advisories_industry_status` on `(industry, status)`

---

## crm_tickets

Tracks per-advisory CRM ticket lifecycle.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Auto-generated |
| advisory_id | UUID | FK → advisories.id, UNIQUE | 1:1 with advisory |
| assignee | VARCHAR(100) | | Configured stakeholder contact |
| title | VARCHAR(255) | NOT NULL | Auto: "G{n} Storm — {Industry} Advisory — {date}" |
| body | TEXT | | Formatted action_items + technical_details |
| status | VARCHAR(20) | NOT NULL, default 'pending_review' | pending_review → approved/rejected → actioned/resolved |
| outcome | VARCHAR(30) | | actions_taken, false_positive, storm_subsided, n/a |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | |
| closed_at | TIMESTAMPTZ | | NULL until ticket closed |

---

## feedback_log

Data flywheel — every operator interaction is a labeled training example.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Auto-generated |
| advisory_id | UUID | FK → advisories.id, NOT NULL | Referenced advisory |
| operator_action | VARCHAR(30) | NOT NULL | approved, edited, rejected, escalated |
| edited_fields | JSONB | | Which fields changed and to what |
| outcome | VARCHAR(30) | | actions_taken, false_positive, storm_subsided, n/a |
| operator_notes | TEXT | | Free-text feedback |
| logged_at | TIMESTAMPTZ | NOT NULL, default NOW() | |

---

## api_keys

Stores hashed API keys for authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Auto-generated |
| key_hash | VARCHAR(64) | UNIQUE, NOT NULL | SHA-256 hex digest of the raw key |
| role | VARCHAR(20) | NOT NULL, default 'viewer' | admin, operator, viewer |
| client_id | VARCHAR(100) | | Tenant/client identifier |
| description | VARCHAR(255) | | Human-readable label |
| is_active | BOOLEAN | NOT NULL, default true | Soft disable |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | |
| last_used_at | TIMESTAMPTZ | | Updated on each request |

---

## AdvisoryOutput JSONB Schema

The `advisory_json` column in the `advisories` table stores this structure:

```json
{
  "severity": "CRITICAL",
  "action_items": [
    "Re-route all flights above 78N",
    "Switch HF to 8825 kHz backup"
  ],
  "timing_window": "2026-06-08T06:00Z/18:00Z",
  "affected_routes": ["NAT Track A", "NAT Track B", "Polar 1"],
  "hf_frequencies_affected": ["13360 kHz", "11279 kHz"],
  "hf_backup_frequencies": ["8825 kHz", "11384 kHz"],
  "polar_latitude_threshold": 78.0,
  "technical_details": "HF blackout expected for 8-12 hours...",
  "reference_procedures": ["ICAO NAT Doc 007 §3.4"],
  "precedent_storms": ["Sep 2017 G4 — Finnair FIN006"],
  "confidence": 0.91
}
```
