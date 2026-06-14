-- ============================================================================
-- HelioOps Demo Seed Data
-- Run AFTER 001_schema.sql and 002_rls.sql
-- Seeds 2 demo storms + impact predictions (conservative fallback values)
-- ============================================================================

-- ── Storm 1: October 2024 G4 ────────────────────────────────────────────────

INSERT INTO storm_events (
    storm_id, detected_at, confidence,
    g_scale, s_scale, r_scale, scales,
    cme, flare, l1_solar_wind, timeline,
    noaa_alert_raw
) VALUES (
    '2024-10-G4',
    '2024-10-10T12:34:00Z',
    0.91,
    4, 2, 3,
    '{"G": 4, "S": 2, "R": 3}',
    '{
        "detected": true,
        "source": "CCOR-1",
        "speed_km_s": 1480,
        "angular_width_deg": 110,
        "direction": "earth_directed",
        "arrival_estimate": "2024-10-11T18:00:00Z",
        "confidence": 0.88,
        "frame_path": "data/cached/ccor1/2024-10/annotated/frame_012.png",
        "bbox_norm": [0.28, 0.18, 0.74, 0.62]
    }',
    '{
        "detected": true,
        "class": "X1.8",
        "r_scale": 3,
        "source": "GOES-XRS",
        "onset": "2024-10-10T12:30:00Z"
    }',
    '{
        "speed_km_s": 720,
        "bz_nt": -28,
        "measured_at": "2024-10-11T17:10:00Z",
        "eta_minutes": 35
    }',
    '[
        {"horizon": "days_out", "source": "CCOR-1 CME",  "t": "2024-10-10T12:34:00Z"},
        {"horizon": "one_hour", "source": "L1 wind",      "t": "2024-10-11T17:10:00Z"},
        {"horizon": "onset",    "source": "geomagnetic",  "t": "2024-10-11T18:00:00Z"}
    ]',
    'G4 Watch, Kp 8.3, R3 in progress'
) ON CONFLICT (storm_id) DO UPDATE SET
    detected_at    = EXCLUDED.detected_at,
    confidence     = EXCLUDED.confidence,
    g_scale        = EXCLUDED.g_scale,
    s_scale        = EXCLUDED.s_scale,
    r_scale        = EXCLUDED.r_scale,
    scales         = EXCLUDED.scales,
    cme            = EXCLUDED.cme,
    flare          = EXCLUDED.flare,
    l1_solar_wind  = EXCLUDED.l1_solar_wind,
    timeline       = EXCLUDED.timeline,
    noaa_alert_raw = EXCLUDED.noaa_alert_raw,
    updated_at     = now();

-- ── Storm 2: May 2024 G5 ────────────────────────────────────────────────────

INSERT INTO storm_events (
    storm_id, detected_at, confidence,
    g_scale, s_scale, r_scale, scales,
    cme, flare, l1_solar_wind, timeline,
    noaa_alert_raw
) VALUES (
    '2024-05-G5',
    '2024-05-10T09:12:00Z',
    0.96,
    5, 3, 5,
    '{"G": 5, "S": 3, "R": 5}',
    '{
        "detected": true,
        "source": "SOHO/LASCO",
        "speed_km_s": 2200,
        "angular_width_deg": 280,
        "direction": "earth_directed",
        "arrival_estimate": "2024-05-11T06:00:00Z",
        "confidence": 0.94,
        "frame_path": "data/cached/lasco/2024-05/annotated/frame_008.png",
        "bbox_norm": [0.12, 0.08, 0.88, 0.86]
    }',
    '{
        "detected": true,
        "class": "X5.8",
        "r_scale": 5,
        "source": "GOES-XRS",
        "onset": "2024-05-10T09:00:00Z"
    }',
    '{
        "speed_km_s": 1100,
        "bz_nt": -46,
        "measured_at": "2024-05-11T05:30:00Z",
        "eta_minutes": 23
    }',
    '[
        {"horizon": "days_out", "source": "SOHO/LASCO CME", "t": "2024-05-10T09:12:00Z"},
        {"horizon": "one_hour", "source": "L1 wind",         "t": "2024-05-11T05:30:00Z"},
        {"horizon": "onset",    "source": "geomagnetic",     "t": "2024-05-11T06:00:00Z"}
    ]',
    'G5 Extreme, Kp 9+, R5 in progress, S3 in progress'
) ON CONFLICT (storm_id) DO UPDATE SET
    detected_at    = EXCLUDED.detected_at,
    confidence     = EXCLUDED.confidence,
    g_scale        = EXCLUDED.g_scale,
    s_scale        = EXCLUDED.s_scale,
    r_scale        = EXCLUDED.r_scale,
    scales         = EXCLUDED.scales,
    cme            = EXCLUDED.cme,
    flare          = EXCLUDED.flare,
    l1_solar_wind  = EXCLUDED.l1_solar_wind,
    timeline       = EXCLUDED.timeline,
    noaa_alert_raw = EXCLUDED.noaa_alert_raw,
    updated_at     = now();

-- ── Impact predictions (conservative fallback values) ───────────────────────

INSERT INTO impact_predictions (storm_id, gps_error_m, gps_error_ci_low, gps_error_ci_high, hf_blackout_prob, hf_blackout_ci_low, hf_blackout_ci_high)
VALUES ('2024-10-G4', 20.0, 8.0, 35.0, 0.85, 0.60, 0.95)
ON CONFLICT (storm_id) DO UPDATE SET
    gps_error_m         = EXCLUDED.gps_error_m,
    gps_error_ci_low    = EXCLUDED.gps_error_ci_low,
    gps_error_ci_high   = EXCLUDED.gps_error_ci_high,
    hf_blackout_prob    = EXCLUDED.hf_blackout_prob,
    hf_blackout_ci_low  = EXCLUDED.hf_blackout_ci_low,
    hf_blackout_ci_high = EXCLUDED.hf_blackout_ci_high;

INSERT INTO impact_predictions (storm_id, gps_error_m, gps_error_ci_low, gps_error_ci_high, hf_blackout_prob, hf_blackout_ci_low, hf_blackout_ci_high)
VALUES ('2024-05-G5', 20.0, 8.0, 35.0, 0.85, 0.60, 0.95)
ON CONFLICT (storm_id) DO UPDATE SET
    gps_error_m         = EXCLUDED.gps_error_m,
    gps_error_ci_low    = EXCLUDED.gps_error_ci_low,
    gps_error_ci_high   = EXCLUDED.gps_error_ci_high,
    hf_blackout_prob    = EXCLUDED.hf_blackout_prob,
    hf_blackout_ci_low  = EXCLUDED.hf_blackout_ci_low,
    hf_blackout_ci_high = EXCLUDED.hf_blackout_ci_high;

-- ── Verify ──────────────────────────────────────────────────────────────────

SELECT storm_id, g_scale, confidence, cme->>'speed_km_s' AS cme_speed
FROM storm_events;

SELECT s.storm_id, i.gps_error_m, i.hf_blackout_prob
FROM storm_events s
JOIN impact_predictions i ON s.storm_id = i.storm_id;
