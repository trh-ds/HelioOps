-- ============================================================================
-- HelioOps Row Level Security Policies
-- Run AFTER 001_schema.sql
-- ============================================================================

-- ── Enable RLS on all tables ────────────────────────────────────────────────

ALTER TABLE storm_events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE impact_predictions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE advisories            ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE verified_advisories   ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifier_checks       ENABLE ROW LEVEL SECURITY;
ALTER TABLE provenance_traces     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs         ENABLE ROW LEVEL SECURITY;

-- ── Anonymous read-only (frontend dashboard) ────────────────────────────────

CREATE POLICY "anon_read" ON storm_events        FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON impact_predictions   FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON advisories           FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON action_items         FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON verified_advisories  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON verifier_checks      FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON provenance_traces    FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON pipeline_runs        FOR SELECT TO anon USING (true);

-- ── Service role full access (backend pipeline writes) ──────────────────────

CREATE POLICY "service_all" ON storm_events        FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON impact_predictions   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON advisories           FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON action_items         FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON verified_advisories  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON verifier_checks      FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON provenance_traces    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_all" ON pipeline_runs        FOR ALL TO service_role USING (true) WITH CHECK (true);
