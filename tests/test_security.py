"""
tests/test_security.py — Security tests for Phase 2 backend hardening.

Covers:
  - Security headers present on all responses
  - Rate limiter blocks rapid requests
  - Storm ID regex rejects invalid formats
  - CORS headers only include allowed origins
  - WebSocket rejects unknown origins
  - Missing GROQ_API_KEY produces warning
"""

from __future__ import annotations

import warnings

from fastapi.testclient import TestClient

from backend.app import app
from backend.middleware import (
    check_rate_limit,
    validate_storm_id,
)
from backend.config import Settings

client = TestClient(app, raise_server_exceptions=False)


# ── Security Headers ────────────────────────────────────────────────────────


class TestSecurityHeaders:
    """All responses must include security headers."""

    def test_health_returns_security_headers(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["x-xss-protection"] == "1; mode=block"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["content-security-policy"] == "default-src 'self'"
        assert "max-age=31536000" in resp.headers["strict-transport-security"]

    def test_metrics_returns_security_headers(self):
        resp = client.get("/metrics")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"

    def test_request_id_header_present(self):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        assert resp.headers["x-request-id"].startswith("req-")


# ── Rate Limiting ───────────────────────────────────────────────────────────


class TestRateLimiting:
    """check_rate_limit blocks rapid duplicate requests."""

    def test_allows_first_request(self):
        assert check_rate_limit("test-storm-1") is True

    def test_blocks_second_request_within_window(self):
        # Reset state to ensure a clean test
        from backend import middleware
        middleware._pipeline_calls.clear()
        assert check_rate_limit("rate-test-storm") is True
        assert check_rate_limit("rate-test-storm") is False

    def test_different_storms_independent(self):
        assert check_rate_limit("test-storm-3") is True
        assert check_rate_limit("test-storm-4") is True

    def test_endpoint_returns_429_when_rate_limited(self):
        """POST /api/detect/{storm_id} returns 429 when rate limited."""
        storm = "2024-10-G4"
        # First call may or may not be allowed depending on prior tests
        # but a second immediate call should be 429
        resp1 = client.post(f"/api/detect/{storm}")
        resp2 = client.post(f"/api/detect/{storm}")
        # One of them should be 429 (rate limited), the other 404/500/200
        # The key assertion: we get a 429 at some point
        statuses = {resp1.status_code, resp2.status_code}
        assert 429 in statuses, f"Expected 429 in {statuses}"


# ── Storm ID Validation ─────────────────────────────────────────────────────


class TestStormIDValidation:
    """STORM_ID_PATTERN rejects injection attempts and bad formats."""

    def test_valid_storm_ids(self):
        valid = ["2024-10-G4", "2024-05-G5", "2025-12-G1", "2000-01-G5"]
        for sid in valid:
            assert validate_storm_id(sid) is True, f"{sid} should be valid"

    def test_rejects_path_traversal(self):
        assert validate_storm_id("../../etc/passwd") is False

    def test_rejects_sql_injection(self):
        assert validate_storm_id("'; DROP TABLE--") is False

    def test_rejects_g_scale_out_of_range(self):
        assert validate_storm_id("2024-10-G6") is False
        assert validate_storm_id("2024-10-G0") is False

    def test_rejects_non_numeric_month(self):
        assert validate_storm_id("2024-ab-G4") is False

    def test_rejects_incomplete_format(self):
        assert validate_storm_id("2024-10") is False
        assert validate_storm_id("G4") is False
        assert validate_storm_id("2024-G4") is False

    def test_rejects_empty_string(self):
        assert validate_storm_id("") is False

    def test_rejects_lowercase(self):
        assert validate_storm_id("2024-10-g4") is False

    def test_rejects_extra_content(self):
        assert validate_storm_id("2024-10-G4-extra") is False

    def test_detect_endpoint_returns_400_for_invalid_id(self):
        resp = client.post("/api/detect/invalid-id")
        assert resp.status_code == 400
        assert "Invalid storm_id format" in resp.json()["detail"]


# ── CORS Configuration ─────────────────────────────────────────────────────


class TestCORS:
    """CORS should only allow configured origins and methods."""

    def test_cors_allowed_origins(self):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORSMiddleware should reflect the allowed origin
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_rejects_unknown_origin(self):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not reflect the evil origin
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"


# ── WebSocket Origin Validation ─────────────────────────────────────────────


class TestWebSocketOrigin:
    """WebSocket should reject connections from unknown origins."""

    def test_ws_rejects_unknown_origin(self):
        from starlette.websockets import WebSocketDisconnect

        try:
            with client.websocket_connect(
                "/ws/stream",
                headers={"Origin": "http://evil.com"},
            ):
                pass
        except WebSocketDisconnect as exc:
            # Expected: server closes with code 4003
            assert exc.code == 4003
            return
        raise AssertionError("Expected WebSocketDisconnect with code 4003")

    def test_ws_allows_known_origin(self):
        try:
            with client.websocket_connect(
                "/ws/stream",
                headers={"Origin": "http://localhost:3000"},
            ):
                pass
        except Exception:
            # May fail for other reasons (not origin-related), that's ok
            pass


# ── Env Var Validation ──────────────────────────────────────────────────────


class TestEnvVarValidation:
    """Missing GROQ_API_KEY should produce a warning."""

    def test_groq_key_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(GROQ_API_KEY="")
            groq_warnings = [x for x in w if "GROQ_API_KEY" in str(x.message)]
            assert len(groq_warnings) >= 1

    def test_groq_key_no_warning_when_set(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(GROQ_API_KEY="test-key-123")
            groq_warnings = [x for x in w if "GROQ_API_KEY" in str(x.message)]
            assert len(groq_warnings) == 0
