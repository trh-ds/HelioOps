"""
tests/test_api_endpoints.py — Integration tests for API endpoint contracts.

Covers:
  - GET /health returns 200 + correct schema
  - GET /health/ready returns 200 or 503
  - GET /api/storms returns correct schema
  - POST /api/detect/{valid_id} returns 200 or 500
  - POST /api/detect/{invalid_id} returns 400
  - GET /api/result/{unknown} returns 404
  - GET /api/advisory/{unknown} returns 404
  - GET /metrics returns text/plain
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app, raise_server_exceptions=False)

# The only test in the suite that spends real Groq quota. CI passes the
# placeholder GROQ_API_KEY=test-key, which cannot authenticate, so the run
# burns 9-12 minutes discovering that - and _pick_key()'s unbounded `while
# True` can park it indefinitely rather than failing. Gate on a key that is
# at least shaped like a real one.
requires_live_groq = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY", "").startswith("gsk_"),
    reason="live Groq call - needs a real key",
)


class TestHealthEndpoint:
    """GET /health — liveness probe."""

    def test_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_schema(self):
        data = client.get("/health").json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert data["status"] == "ok"


class TestReadinessEndpoint:
    """GET /health/ready — readiness probe."""

    def test_returns_200_or_503(self):
        resp = client.get("/health/ready")
        assert resp.status_code in (200, 503)

    def test_schema(self):
        resp = client.get("/health/ready")
        assert resp.status_code in (200, 503)
        data = resp.json()
        # FastAPI may serialize tuple return as list or dict depending on version
        if isinstance(data, list):
            body = data[0]
        else:
            body = data
        assert "status" in body
        assert "checks" in body
        assert "version" in body
        assert body["status"] in ("ready", "degraded")


class TestListStormsEndpoint:
    """GET /api/storms — list available and completed storms."""

    def test_returns_200(self):
        resp = client.get("/api/storms")
        assert resp.status_code == 200

    def test_schema(self):
        data = client.get("/api/storms").json()
        assert "available_storms" in data
        assert "completed" in data
        assert isinstance(data["available_storms"], list)
        assert isinstance(data["completed"], dict)


class TestDetectEndpoint:
    """POST /api/detect/{storm_id} — run pipeline."""

    def test_invalid_storm_id_returns_400(self):
        resp = client.post("/api/detect/invalid-id")
        assert resp.status_code == 400
        assert "Invalid storm_id format" in resp.json()["detail"]

    def test_path_traversal_returns_400_or_404(self):
        # FastAPI normalizes /../../ paths, so we get 404 (route not found)
        # or 400 (validation error) — both are safe responses
        resp = client.post("/api/detect/../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_sql_injection_returns_400(self):
        resp = client.post("/api/detect/'; DROP TABLE--")
        assert resp.status_code == 400

    @requires_live_groq
    def test_valid_storm_id_returns_200_or_500_or_429(self):
        """Valid storm_id returns 200 (success), 500 (pipeline error), or 429 (rate limited)."""
        resp = client.post("/api/detect/2024-10-G4")
        assert resp.status_code in (200, 500, 429)

    def test_unknown_storm_id_returns_404(self):
        """Valid format but unknown storm returns 404."""
        resp = client.post("/api/detect/2099-01-G5")
        assert resp.status_code == 404


class TestPreflightEndpoint:
    """GET /api/preflight/{storm_id} — read-only pre-run check."""

    def test_returns_200_with_schema(self):
        resp = client.get("/api/preflight/2024-10-G4")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == {"storm_id", "ready", "estimated_duration_s", "findings"}
        assert isinstance(data["findings"], list)

    def test_invalid_storm_id_returns_400(self):
        resp = client.get("/api/preflight/invalid-id")
        assert resp.status_code == 400

    def test_unknown_storm_id_returns_404(self):
        resp = client.get("/api/preflight/2099-01-G5")
        assert resp.status_code == 404

    def test_does_not_consume_rate_limit_slot(self):
        # Inspect the state dict directly — POSTing detect to verify would run
        # the real pipeline against live Groq.
        from backend import middleware

        middleware._pipeline_calls.pop("2024-05-G5", None)
        resp = client.get("/api/preflight/2024-05-G5")
        assert resp.status_code == 200
        assert "2024-05-G5" not in middleware._pipeline_calls


class TestResultEndpoint:
    """GET /api/result/{storm_id} — fetch pipeline result."""

    def test_unknown_storm_returns_404(self):
        resp = client.get("/api/result/unknown-storm")
        assert resp.status_code == 404


class TestAdvisoryEndpoint:
    """GET /api/advisory/{advisory_id} — fetch advisory."""

    def test_unknown_advisory_returns_404(self):
        resp = client.get("/api/advisory/unknown-advisory")
        assert resp.status_code == 404


class TestMetricsEndpoint:
    """GET /metrics — Prometheus-compatible metrics."""

    def test_returns_200(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_returns_text_plain(self):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    def test_contains_expected_metrics(self):
        resp = client.get("/metrics")
        body = resp.text
        assert "helioops_uptime_seconds" in body
        assert "helioops_pipeline_requests_total" in body
        assert "helioops_pipeline_errors_total" in body
