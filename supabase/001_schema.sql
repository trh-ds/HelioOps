-- ============================================================================
-- HelioOps Supabase Schema
-- Run this FIRST in the Supabase SQL Editor
-- ============================================================================

-- ── Enums ───────────────────────────────────────────────────────────────────

CREATE TYPE industry_type    AS ENUM ('aviation', 'grid', 'maritime', 'telecom');
CREATE TYPE severity_tier    AS ENUM ('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE verifier_status  AS ENUM ('passed', 'passed_with_corrections', 'blocked');
CREATE TYPE check_status     AS ENUM ('pass', 'blocked');

-- ── 1. storm_events ─────────────────────────────────────────────────────────
-- Source: cv/fusion.py StormEvent

CREATE TABLE storm_events (
    storm_id        TEXT PRIMARY KEY,
    detected_at     TIMESTAMPTZ NOT NULL,
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    g_scale         SMALLINT NOT NULL CHECK (g_scale BETWEEN 0 AND 5),
    s_scale         SMALLINT NOT NULL DEFAULT 0 CHECK (s_scale BETWEEN 0 AND 5),
    r_scale         SMALLINT NOT NULL DEFAULT 0 CHECK (r_scale BETWEEN 0 AND 5),
    scales          JSONB NOT NULL,
    cme             JSONB NOT NULL,
    flare           JSONB NOT NULL,
    l1_solar_wind   JSONB NOT NULL,
    timeline        JSONB NOT NULL,
    noaa_alert_raw  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2. impact_predictions ───────────────────────────────────────────────────
-- Source: ML_after_CV/inference.py ImpactPrediction

CREATE TABLE impact_predictions (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    storm_id             TEXT NOT NULL UNIQUE REFERENCES storm_events(storm_id) ON DELETE CASCADE,
    gps_error_m          REAL NOT NULL,
    gps_error_ci_low     REAL NOT NULL,
    gps_error_ci_high    REAL NOT NULL,
    hf_blackout_prob     REAL NOT NULL CHECK (hf_blackout_prob BETWEEN 0 AND 1),
    hf_blackout_ci_low   REAL NOT NULL CHECK (hf_blackout_ci_low BETWEEN 0 AND 1),
    hf_blackout_ci_high  REAL NOT NULL CHECK (hf_blackout_ci_high BETWEEN 0 AND 1),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 3. advisories ───────────────────────────────────────────────────────────
-- Source: genai/models.py AdvisoryOutput

CREATE TABLE advisories (
    advisory_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storm_event_id           TEXT NOT NULL REFERENCES storm_events(storm_id) ON DELETE CASCADE,
    industry                 industry_type NOT NULL,
    severity                 severity_tier NOT NULL,
    confidence_score         REAL NOT NULL DEFAULT 0 CHECK (confidence_score BETWEEN 0 AND 1),
    summary                  TEXT NOT NULL,
    estimated_impact_window  TEXT,
    sources_cited            TEXT[] NOT NULL DEFAULT '{}',
    validation_passed        BOOLEAN NOT NULL DEFAULT false,
    generated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_used               TEXT NOT NULL DEFAULT '',
    safety_flags             TEXT[] NOT NULL DEFAULT '{}',
    generation_errors        TEXT[] NOT NULL DEFAULT '{}',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 4. action_items ─────────────────────────────────────────────────────────
-- Source: genai/models.py ActionItem

CREATE TABLE action_items (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    advisory_id     UUID NOT NULL REFERENCES advisories(advisory_id) ON DELETE CASCADE,
    step            SMALLINT NOT NULL CHECK (step >= 1),
    action          TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    source_ref      TEXT,
    time_window     TEXT,
    UNIQUE (advisory_id, step)
);

-- ── 5. verified_advisories ──────────────────────────────────────────────────
-- Source: genai/contracts.py VerifiedAdvisory

CREATE TABLE verified_advisories (
    advisory_id        TEXT PRIMARY KEY,
    storm_id           TEXT NOT NULL REFERENCES storm_events(storm_id) ON DELETE CASCADE,
    source_advisory_id UUID REFERENCES advisories(advisory_id) ON DELETE SET NULL,
    industry           industry_type NOT NULL,
    severity           TEXT NOT NULL,
    numbered_actions   TEXT[] NOT NULL DEFAULT '{}',
    timing_window      JSONB NOT NULL DEFAULT '{}',
    technical_details  TEXT NOT NULL DEFAULT '',
    cited_procedure    JSONB NOT NULL DEFAULT '{}',
    verifier_status    verifier_status NOT NULL,
    requires_human     BOOLEAN NOT NULL DEFAULT false,
    provenance_ref     TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 6. verifier_checks ─────────────────────────────────────────────────────
-- Source: genai/contracts.py VerifierCheck

CREATE TABLE verifier_checks (
    id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    verified_advisory_id   TEXT NOT NULL REFERENCES verified_advisories(advisory_id) ON DELETE CASCADE,
    field                  TEXT NOT NULL,
    proposed               JSONB,
    status                 check_status NOT NULL,
    corrected_to           JSONB,
    reason                 TEXT
);

-- ── 7. provenance_traces ────────────────────────────────────────────────────
-- Source: genai/contracts.py ProvenanceTrace

CREATE TABLE provenance_traces (
    trace_id        TEXT PRIMARY KEY,
    advisory_id     TEXT NOT NULL,
    chain           JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 8. pipeline_runs ────────────────────────────────────────────────────────
-- Denormalized summary of each pipeline execution

CREATE TABLE pipeline_runs (
    storm_id         TEXT PRIMARY KEY REFERENCES storm_events(storm_id) ON DELETE CASCADE,
    completed_at     TIMESTAMPTZ NOT NULL,
    advisory_count   SMALLINT NOT NULL DEFAULT 0,
    verified_count   SMALLINT NOT NULL DEFAULT 0,
    error_count      SMALLINT NOT NULL DEFAULT 0,
    errors           TEXT[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes ─────────────────────────────────────────────────────────────────

CREATE INDEX idx_storm_events_g_scale            ON storm_events (g_scale);
CREATE INDEX idx_advisories_storm_event_id       ON advisories (storm_event_id);
CREATE INDEX idx_advisories_storm_industry       ON advisories (storm_event_id, industry);
CREATE INDEX idx_advisories_severity             ON advisories (severity);
CREATE INDEX idx_action_items_advisory_id        ON action_items (advisory_id);
CREATE INDEX idx_verified_advisories_storm_id    ON verified_advisories (storm_id);
CREATE INDEX idx_verified_advisories_industry    ON verified_advisories (industry);
CREATE INDEX idx_verifier_checks_advisory_id     ON verifier_checks (verified_advisory_id);
CREATE INDEX idx_provenance_traces_advisory_id   ON provenance_traces (advisory_id);

-- ── updated_at trigger ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON storm_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON advisories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON verified_advisories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
