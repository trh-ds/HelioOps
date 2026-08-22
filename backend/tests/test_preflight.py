"""
tests/test_preflight.py — the read-only pre-run conflict check.

Covers:
  - peek_rate_limit never mutates the rate-limit state
  - cache findings fire on missing frames and stay read-only (no mkdir/fetch)
  - each conflict rule fires above threshold, stays silent below, and skips
    missing inputs
  - the committed stubs are internally consistent (no rule fires on them)
  - run_preflight end-to-end schema + block behaviour
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

from backend import middleware
from backend.cv.storm_event_generator.detect import STORM_CONFIGS
from backend.paths import BACKEND_DIR
from backend.preflight import _cache_findings, _conflict_findings, run_preflight

STORM = "2024-10-G4"
CFG = STORM_CONFIGS[STORM]


def _ids(findings):
    return [f["id"] for f in findings]


def _stub() -> dict:
    return json.loads((BACKEND_DIR / CFG["stub_path"]).read_text())


def _seed_stub(base: Path) -> None:
    dst = base / CFG["stub_path"]
    dst.parent.mkdir(parents=True)
    shutil.copy(BACKEND_DIR / CFG["stub_path"], dst)


class TestPeekRateLimit:
    def setup_method(self):
        self._saved = dict(middleware._pipeline_calls)

    def teardown_method(self):
        middleware._pipeline_calls.clear()
        middleware._pipeline_calls.update(self._saved)

    def test_fresh_storm_is_zero(self):
        middleware._pipeline_calls.pop(STORM, None)
        assert middleware.peek_rate_limit(STORM) == 0.0

    def test_recent_run_returns_wait(self):
        middleware._pipeline_calls[STORM] = time.time()
        wait = middleware.peek_rate_limit(STORM)
        assert 0 < wait <= middleware.RATE_LIMIT_SECONDS

    def test_peek_does_not_mutate(self):
        middleware._pipeline_calls.pop(STORM, None)
        before = dict(middleware._pipeline_calls)
        middleware.peek_rate_limit(STORM)
        assert middleware._pipeline_calls == before  # nothing recorded


class TestCacheFindings:
    def test_empty_base_fires_stub_replay(self, tmp_path):
        _seed_stub(tmp_path)
        findings, stub, cme, flare, l1 = _cache_findings(CFG, tmp_path)
        assert "cv_stub_replay" in _ids(findings)
        assert cme is None and flare is None and l1 is None
        assert stub["storm_id"] == STORM

    def test_frames_present_no_stub_replay(self, tmp_path):
        _seed_stub(tmp_path)
        for sub in ("png", "diff"):
            d = tmp_path / CFG["png_dir"] / sub
            d.mkdir(parents=True)
            (d / "frame_000.png").write_bytes(b"png")
        findings, *_ = _cache_findings(CFG, tmp_path)
        assert "cv_stub_replay" not in _ids(findings)

    def test_read_only_no_mkdir_no_fetch(self, tmp_path):
        # The load-bearing guarantee: the clients mkdir + fetch on miss, so
        # preflight must stat first. An empty base must stay empty.
        _seed_stub(tmp_path)
        before = set(tmp_path.rglob("*"))
        _cache_findings(CFG, tmp_path)
        assert set(tmp_path.rglob("*")) == before

    def test_l1_fallback_data_detected(self, tmp_path):
        _seed_stub(tmp_path)
        p = tmp_path / CFG["l1_cache"]
        p.parent.mkdir(parents=True)
        p.write_text("[]")  # exists but holds no reading -> fallback defaults
        findings, *_ = _cache_findings(CFG, tmp_path)
        assert "l1_fallback_data" in _ids(findings)
        assert "l1_cache_missing" not in _ids(findings)


class TestConflictRules:
    def test_l1_faster_than_launch_fires(self):
        f = _conflict_findings(_stub(), {"speed_km_s": 1000.0}, None,
                               {"speed_km_s": 1200.0, "bz_nt": -5.0})
        assert "speed_disagreement" in _ids(f)

    def test_l1_below_drag_floor_fires(self):
        f = _conflict_findings(_stub(), {"speed_km_s": 1000.0}, None,
                               {"speed_km_s": 250.0, "bz_nt": -5.0})
        assert "speed_disagreement" in _ids(f)

    def test_plausible_deceleration_silent(self):
        f = _conflict_findings(_stub(), {"speed_km_s": 1000.0}, None,
                               {"speed_km_s": 700.0, "bz_nt": -5.0})
        assert "speed_disagreement" not in _ids(f)

    def test_missing_l1_skips_speed_rule(self):
        f = _conflict_findings(_stub(), {"speed_km_s": 1000.0}, None, None)
        assert "speed_disagreement" not in _ids(f)

    def test_arrival_gap_fires_and_small_gap_silent(self):
        l1 = {"speed_km_s": 700.0, "bz_nt": -5.0,
              "measured_at": "2024-10-11T00:00:00Z", "eta_minutes": 60}
        far = _conflict_findings(_stub(), {"speed_km_s": 700.0,
                                 "arrival_estimate": "2024-10-13T00:00:00Z"}, None, l1)
        assert "arrival_eta_mismatch" in _ids(far)
        near = _conflict_findings(_stub(), {"speed_km_s": 700.0,
                                  "arrival_estimate": "2024-10-11T02:00:00Z"}, None, l1)
        assert "arrival_eta_mismatch" not in _ids(near)

    def test_unparseable_timestamp_skips_arrival_rule(self):
        l1 = {"speed_km_s": 700.0, "bz_nt": -5.0,
              "measured_at": "not-a-time", "eta_minutes": 60}
        f = _conflict_findings(_stub(), {"speed_km_s": 700.0,
                               "arrival_estimate": "2024-10-13T00:00:00Z"}, None, l1)
        assert "arrival_eta_mismatch" not in _ids(f)

    def test_northward_bz_with_strong_g_fires(self):
        f = _conflict_findings(_stub(), None, None,
                               {"speed_km_s": 700.0, "bz_nt": 5.0})
        assert "bz_northward_strong_g" in _ids(f)  # stub G is 4

    def test_southward_bz_silent(self):
        f = _conflict_findings(_stub(), None, None,
                               {"speed_km_s": 700.0, "bz_nt": -20.0})
        assert "bz_northward_strong_g" not in _ids(f)

    def test_flare_r_zero_against_strong_r_warns(self):
        f = _conflict_findings(_stub(), None, {"r_scale": 0}, None)
        hit = [x for x in f if x["id"] == "flare_r_mismatch"]
        assert hit and hit[0]["severity"] == "warn"  # stub R is 3

    def test_flare_r_two_levels_off_is_info(self):
        f = _conflict_findings(_stub(), None, {"r_scale": 1}, None)
        hit = [x for x in f if x["id"] == "flare_r_mismatch"]
        assert hit and hit[0]["severity"] == "info"

    def test_flare_r_one_level_off_silent(self):
        f = _conflict_findings(_stub(), None, {"r_scale": 2}, None)
        assert "flare_r_mismatch" not in _ids(f)

    def test_stubs_are_internally_consistent(self):
        # The rules must be silent on the committed stubs' own values —
        # otherwise every fresh checkout warns about its own reference data.
        for storm_id, cfg in STORM_CONFIGS.items():
            stub = json.loads((BACKEND_DIR / cfg["stub_path"]).read_text())
            f = _conflict_findings(stub, stub["cme"], stub["flare"],
                                   stub["l1_solar_wind"])
            assert f == [], f"{storm_id} stub fired {_ids(f)}"


class TestRunPreflight:
    def setup_method(self):
        self._saved = dict(middleware._pipeline_calls)
        middleware._pipeline_calls.pop(STORM, None)

    def teardown_method(self):
        middleware._pipeline_calls.clear()
        middleware._pipeline_calls.update(self._saved)

    def test_schema_and_ready_on_real_repo(self):
        result = asyncio.run(run_preflight(STORM))
        assert set(result) == {"storm_id", "ready", "estimated_duration_s", "findings"}
        assert result["storm_id"] == STORM
        assert result["ready"] is True
        assert isinstance(result["estimated_duration_s"], int)
        for f in result["findings"]:
            assert set(f) == {"id", "severity", "title", "detail"}
            assert f["severity"] in ("info", "warn", "block")
        # today's normal: no frames committed -> stub replay predicted
        assert "cv_stub_replay" in _ids(result["findings"])

    def test_rate_limited_blocks(self):
        middleware._pipeline_calls[STORM] = time.time()
        result = asyncio.run(run_preflight(STORM))
        blocks = [f for f in result["findings"] if f["severity"] == "block"]
        assert result["ready"] is False
        assert _ids(blocks) == ["rate_limited"]
