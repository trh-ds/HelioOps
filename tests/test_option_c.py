"""
tests/test_option_c.py — Option C pipeline tests

Covers:
  - threshold_detector: algorithm correctness on synthetic diff frames
  - flare_classifier: R-scale mapping (verbatim from imp.md)
  - donki_client: arrival computation + direction classification
  - fusion: confidence weights + StormEvent contract shape
  - detect: stub fallback returns valid StormEvent

All tests are zero-network and zero-disk (except detect stub test which reads
the committed ml/stubs/ JSON files).

Run:
    pytest tests/test_option_c.py -v
"""

from __future__ import annotations

import json
import math
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cv.threshold_detector import (
    detect_cme_in_frame,
    detect_cme_in_sequence,
    _annular_mask,
    _circular_mean_deg,
    _circular_range_deg,
    estimate_speed_from_centroids,
    DEFAULT_OCCULTER_R,
    DEFAULT_CENTER_XY,
)
from cv.flare_classifier import classify_flare
from cv.donki_client import _compute_arrival, _classify_direction, cme_to_fields
from cv.fusion import StormEvent, fuse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_diff_frame(
    cme_angle_deg: float = 90.0,
    cme_brightness: float = 0.85,
    cme_arc_width_deg: float = 40.0,
    size: int = 512,
    cx: int = 256,
    cy: int = 256,
    occulter_r: int = 80,
) -> np.ndarray:
    """
    Synthetic running-difference frame with a CME arc at a specified angle.

    Background ~ 0.5 (neutral diff).
    CME arc = bright pixels at radius ~130px, centered on cme_angle_deg.
    """
    frame = np.full((size, size), 0.5, dtype=np.float32)
    # Add small noise to background
    rng = np.random.default_rng(42)
    frame += rng.normal(0, 0.02, frame.shape).astype(np.float32)
    frame = np.clip(frame, 0.0, 1.0)

    # Draw a bright arc at radius 130px
    arc_r = 130
    half = cme_arc_width_deg / 2.0
    for r_offset in range(-6, 7):
        r = arc_r + r_offset
        for angle_offset in np.linspace(-half, half, int(half * 4)):
            img_angle_rad = math.radians(cme_angle_deg + angle_offset)
            px = int(round(cx + r * math.cos(img_angle_rad)))
            py = int(round(cy - r * math.sin(img_angle_rad)))
            if 0 <= px < size and 0 <= py < size:
                frame[py, px] = cme_brightness

    return frame


def _make_norm_frame(size: int = 512) -> np.ndarray:
    """Flat normalised frame — detector uses diff frame for all logic."""
    return np.full((size, size), 0.3, dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Threshold detector
# ─────────────────────────────────────────────────────────────────────────────

class TestAnnularMask:
    def test_center_excluded(self):
        mask = _annular_mask((512, 512), 256, 256, inner_r=80, outer_r=220)
        assert not mask[256, 256], "Center pixel must be masked out"

    def test_corners_excluded(self):
        mask = _annular_mask((512, 512), 256, 256, inner_r=80, outer_r=220)
        assert not mask[0, 0]
        assert not mask[511, 511]

    def test_ring_pixels_included(self):
        mask = _annular_mask((512, 512), 256, 256, inner_r=80, outer_r=220)
        # Point at radius ~150px (between inner and outer)
        assert mask[256, 256 + 150]

    def test_shape_preserved(self):
        mask = _annular_mask((512, 512), 256, 256, 80, 220)
        assert mask.shape == (512, 512)
        assert mask.dtype == bool


class TestCircularStats:
    def test_circular_mean_0_360_boundary(self):
        angles = np.array([350.0, 355.0, 5.0, 10.0])
        mean = _circular_mean_deg(angles)
        # True circular mean ≈ 0° (wraps correctly)
        assert abs(mean) < 15.0 or abs(mean - 360.0) < 15.0

    def test_circular_mean_cardinal(self):
        angles = np.array([90.0, 90.0, 90.0])
        mean = _circular_mean_deg(angles)
        assert abs(mean - 90.0) < 1.0

    def test_circular_range_narrow(self):
        angles = np.array([45.0, 50.0, 55.0, 60.0])
        r = _circular_range_deg(angles)
        assert r < 30.0

    def test_circular_range_wide(self):
        angles = np.linspace(0.0, 180.0, 20)
        r = _circular_range_deg(angles)
        assert r > 100.0


class TestDetectCmeInFrame:
    def test_detects_synthetic_cme(self):
        diff = _make_diff_frame(cme_angle_deg=45.0, cme_brightness=0.9)
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        assert result["detected"], "Should detect bright arc above threshold"

    def test_no_detection_on_flat_frame(self):
        diff = np.full((512, 512), 0.5, dtype=np.float32)
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        assert not result["detected"], "Flat frame should produce no detection"

    def test_bbox_norm_in_unit_range(self):
        diff = _make_diff_frame(cme_brightness=0.9)
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        if result["detected"]:
            x1, y1, x2, y2 = result["bbox_norm"]
            assert 0.0 <= x1 < x2 <= 1.0
            assert 0.0 <= y1 < y2 <= 1.0

    def test_confidence_between_0_and_1(self):
        diff = _make_diff_frame(cme_brightness=0.9)
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        if result["detected"]:
            assert 0.0 <= result["confidence"] <= 1.0

    def test_cpa_in_valid_range(self):
        diff = _make_diff_frame(cme_angle_deg=45.0, cme_brightness=0.9)
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        if result["detected"]:
            assert 0.0 <= result["cpa_deg"] < 360.0

    def test_determinism(self):
        """Identical inputs must produce bit-identical outputs."""
        diff = _make_diff_frame(cme_brightness=0.85)
        norm = _make_norm_frame()
        r1 = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        r2 = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        assert r1 == r2

    def test_no_cme_below_pixel_minimum(self):
        """A single bright pixel below MIN_BRIGHT_PX should not trigger detection."""
        diff = np.full((512, 512), 0.5, dtype=np.float32)
        diff[200, 200] = 0.95  # 1 pixel — below 40px minimum
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        assert not result["detected"]

    def test_occulter_zone_ignored(self):
        """Bright pixels inside the occulter radius must NOT trigger detection."""
        diff = np.full((512, 512), 0.5, dtype=np.float32)
        # Fill occulter region (r < 80) with very bright values
        for py in range(180, 340):
            for px in range(180, 340):
                if (px - 256) ** 2 + (py - 256) ** 2 < 80 ** 2:
                    diff[py, px] = 0.99
        norm = _make_norm_frame()
        result = detect_cme_in_frame(diff, norm, DEFAULT_OCCULTER_R, DEFAULT_CENTER_XY)
        assert not result["detected"], "Occulter zone must be excluded from detection"


class TestDetectSequence:
    def test_sequence_finds_best_frame(self):
        # Frame 0: weak CME; Frame 1: strong CME; Frame 2: no CME
        diff_frames = [
            _make_diff_frame(cme_brightness=0.72),  # weak
            _make_diff_frame(cme_brightness=0.95),  # strong → should be best
            np.full((512, 512), 0.5, dtype=np.float32),
        ]
        norm_frames = [_make_norm_frame()] * 4  # N+1 norm frames
        result = detect_cme_in_sequence(diff_frames, norm_frames)
        assert result["detected_count"] >= 1
        assert "best_frame_idx" in result

    def test_empty_sequence_returns_gracefully(self):
        result = detect_cme_in_sequence([], [], 80, (256, 256))
        assert result["detected_count"] == 0
        assert result["frames"] == []


class TestSpeedFromCentroids:
    def test_physical_range(self):
        centroids = [(256, 200), (256, 190), (256, 180)]
        speed = estimate_speed_from_centroids(centroids)
        assert 50.0 <= speed <= 5000.0

    def test_single_centroid_returns_default(self):
        speed = estimate_speed_from_centroids([(256, 256)])
        assert speed == 500.0

    def test_empty_returns_default(self):
        speed = estimate_speed_from_centroids([])
        assert speed == 500.0


# ─────────────────────────────────────────────────────────────────────────────
# Flare classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyFlare:
    @pytest.mark.parametrize("flux,expected_class_prefix,expected_r", [
        (2e-3,  "X", 5),   # X20 → R5
        (1.5e-3,"X", 4),   # X15 → R4
        (1.8e-4,"X", 3),   # X1.8 → R3
        (5.8e-4,"X", 3),   # X5.8 → R3
        (5e-5,  "M", 2),   # M5.0 → R2
        (1e-5,  "M", 1),   # M1.0 → R1
        (1e-6,  "C", 0),   # C-class → R0
    ])
    def test_classification(self, flux, expected_class_prefix, expected_r):
        cls, r = classify_flare(flux)
        assert cls.startswith(expected_class_prefix), f"flux={flux:.1e}: expected {expected_class_prefix}-class, got {cls}"
        assert r == expected_r, f"flux={flux:.1e}: expected R{expected_r}, got R{r}"

    def test_x1_8_matches_oct2024_storm(self):
        cls, r = classify_flare(1.8e-4)
        assert cls.startswith("X"), f"Expected X-class, got {cls}"
        assert r == 3  # Oct 2024 storm was R3

    def test_x5_8_matches_may2024_storm(self):
        cls, r = classify_flare(5.8e-4)
        assert cls.startswith("X"), f"Expected X-class, got {cls}"
        assert r == 3  # X5.8 maps to R3 (R5 only for >= X20)


# ─────────────────────────────────────────────────────────────────────────────
# DONKI client
# ─────────────────────────────────────────────────────────────────────────────

class TestDonkiClient:
    def test_arrival_computation_physical(self):
        # ~1480 km/s should give ~22-24h transit
        arrival = _compute_arrival("2024-10-10T12:00:00Z", 1480.0)
        from datetime import datetime, timezone
        t0  = datetime(2024, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        arr = datetime.fromisoformat(arrival)
        delta_h = (arr - t0).total_seconds() / 3600.0
        assert 15.0 <= delta_h <= 35.0, f"Arrival delta {delta_h:.1f}h outside 15–35h window"

    def test_arrival_fast_cme(self):
        # 2200 km/s should arrive in ~17h
        arrival = _compute_arrival("2024-05-10T06:00:00Z", 2200.0)
        from datetime import datetime, timezone
        t0  = datetime(2024, 5, 10, 6, 0, 0, tzinfo=timezone.utc)
        arr = datetime.fromisoformat(arrival)
        delta_h = (arr - t0).total_seconds() / 3600.0
        assert 10.0 <= delta_h <= 25.0, f"Arrival delta {delta_h:.1f}h outside 10–25h window"

    def test_direction_earth_directed(self):
        assert _classify_direction(10.0, -15.0) == "earth_directed"
        assert _classify_direction(0.0, 0.0) == "earth_directed"

    def test_direction_off_limb(self):
        assert _classify_direction(40.0, 60.0) == "off_limb"
        assert _classify_direction(5.0, 80.0) == "off_limb"

    def test_direction_none(self):
        assert _classify_direction(None, None) == "unknown"

    def test_cme_to_fields_complete_record(self):
        record = {
            "isMostAccurate": True,
            "time21_5": "2024-10-10T14:00:00Z",
            "speed": 1480,
            "halfAngle": 55,
            "latitude": 12.0,
            "longitude": -8.0,
            "activityID": "2024-10-10T12:00:00-CME-001",
        }
        fields = cme_to_fields(record)
        assert fields["speed_km_s"] == 1480.0
        assert fields["angular_width_deg"] == 110.0
        assert fields["direction"] == "earth_directed"
        assert fields["arrival_estimate"] != ""
        assert fields["donki_id"] != ""

    def test_cme_to_fields_missing_speed_defaults(self):
        record = {"isMostAccurate": True, "time21_5": "2024-10-10T14:00:00Z"}
        fields = cme_to_fields(record)
        assert fields["speed_km_s"] == 500.0  # default


# ─────────────────────────────────────────────────────────────────────────────
# Fusion
# ─────────────────────────────────────────────────────────────────────────────

class TestFusion:
    def _make_cme(self, **kwargs):
        base = {
            "speed_km_s": 1480.0, "angular_width_deg": 110.0,
            "direction": "earth_directed", "arrival_estimate": "2024-10-11T18:00:00Z",
            "detected": True, "source": "CCOR-1", "confidence": 0.88,
            "frame_path": "data/cached/ccor1/2024-10/annotated/frame_012.png",
            "bbox_norm": [0.28, 0.18, 0.74, 0.62],
        }
        return {**base, **kwargs}

    def _make_flare(self, **kwargs):
        return {"detected": True, "class": "X1.8", "r_scale": 3, "s_scale": 0,
                "source": "GOES-XRS", "onset": "2024-10-10T12:30:00Z", **kwargs}

    def _make_l1(self, **kwargs):
        return {"speed_km_s": 720.0, "bz_nt": -28.0, "bt_nt": 30.0,
                "density_cm3": 8.0, "measured_at": "2024-10-11T17:10:00Z",
                "g_scale": 4, **kwargs}

    def test_returns_storm_event(self):
        event = fuse(self._make_cme(), self._make_flare(), self._make_l1(),
                     "G4 Watch", "2024-10-G4")
        assert isinstance(event, StormEvent)

    def test_confidence_between_0_and_1(self):
        event = fuse(self._make_cme(), self._make_flare(), self._make_l1(),
                     "G4 Watch", "2024-10-G4")
        assert 0.0 <= event.confidence <= 1.0

    def test_eta_minutes_physical(self):
        event = fuse(self._make_cme(), self._make_flare(), self._make_l1(),
                     "G4 Watch", "2024-10-G4")
        eta = event.l1_solar_wind["eta_minutes"]
        # 1,500,000 / 720 / 60 ≈ 34.7 minutes
        assert 20 <= eta <= 60, f"ETA {eta} min out of physical range"

    def test_southward_bz_boosts_confidence(self):
        l1_south = self._make_l1(bz_nt=-30.0)
        l1_north = self._make_l1(bz_nt=+10.0)
        ev_south = fuse(self._make_cme(), self._make_flare(), l1_south, "G4", "x")
        ev_north = fuse(self._make_cme(), self._make_flare(), l1_north, "G4", "x")
        assert ev_south.confidence > ev_north.confidence

    def test_alert_empty_reduces_confidence(self):
        ev_alert    = fuse(self._make_cme(), self._make_flare(), self._make_l1(), "G4 Watch", "x")
        ev_no_alert = fuse(self._make_cme(), self._make_flare(), self._make_l1(), "", "x")
        assert ev_alert.confidence > ev_no_alert.confidence

    def test_timeline_has_three_horizons(self):
        event = fuse(self._make_cme(), self._make_flare(), self._make_l1(), "alert", "id")
        horizons = [t["horizon"] for t in event.timeline]
        assert set(horizons) == {"days_out", "one_hour", "onset"}

    def test_r_scale_propagated(self):
        event = fuse(self._make_cme(), self._make_flare(r_scale=5), self._make_l1(), "", "id")
        assert event.scales["R"] == 5

    def test_serialisable(self):
        event = fuse(self._make_cme(), self._make_flare(), self._make_l1(), "alert", "id")
        dumped = event.model_dump()
        json.dumps(dumped, default=str)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# detect() stub fallback (no network, no FITS)
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectStubFallback:
    """
    Verifies detect() returns a valid StormEvent using only the committed
    stub JSON when no cached PNGs exist.  Zero network calls.
    """

    @pytest.mark.parametrize("storm_id", ["2024-10-G4", "2024-05-G5"])
    def test_stub_loads_directly(self, storm_id):
        stub_path = Path(__file__).parent.parent / "ml" / "stubs" / f"storm_event_{storm_id}.json"
        assert stub_path.exists(), f"Stub not found: {stub_path}"
        with open(stub_path) as f:
            data = json.load(f)
        event = StormEvent(**data)
        assert event.storm_id == storm_id
        assert 0.0 < event.confidence <= 1.0
        assert event.cme["detected"] is True
        assert "frame_path" in event.cme
        assert "bbox_norm" in event.cme
        assert len(event.cme["bbox_norm"]) == 4

    @pytest.mark.parametrize("storm_id", ["2024-10-G4", "2024-05-G5"])
    def test_detect_falls_back_to_stub_when_no_pngs(self, storm_id, tmp_path):
        """
        With an empty png_dir, detect() should fall back to stub JSON.
        """
        from cv.detect import detect, STORM_CONFIGS
        import cv.detect as det_module

        # Patch STORM_CONFIGS to point png_dir to a non-existent directory
        patched = {
            **STORM_CONFIGS[storm_id],
            "png_dir":       str(tmp_path / "empty_png_dir"),
            "annotated_dir": str(tmp_path / "annotated"),
        }
        with patch.dict(det_module.STORM_CONFIGS, {storm_id: patched}):
            event = detect(storm_id, base_dir=str(Path(__file__).parent.parent))
        assert isinstance(event, StormEvent)
        assert event.storm_id == storm_id

    def test_g4_stub_physics_in_range(self):
        stub_path = Path(__file__).parent.parent / "ml" / "stubs" / "storm_event_2024-10-G4.json"
        with open(stub_path) as f:
            data = json.load(f)
        cme = data["cme"]
        assert 500 <= cme["speed_km_s"] <= 3000, "G4 CME speed out of physical range"
        assert 30 <= cme["angular_width_deg"] <= 360
        assert data["scales"]["G"] == 4

    def test_g5_stub_physics_in_range(self):
        stub_path = Path(__file__).parent.parent / "ml" / "stubs" / "storm_event_2024-05-G5.json"
        with open(stub_path) as f:
            data = json.load(f)
        cme = data["cme"]
        assert 500 <= cme["speed_km_s"] <= 5000, "G5 CME speed out of physical range"
        assert data["scales"]["G"] == 5
        assert data["scales"]["R"] == 5
