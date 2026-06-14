"""
Tests for backend/middleware.py — unit tests for security primitives.

The integration-level security tests live in test_security.py.
This file tests the functions in isolation.
"""

from __future__ import annotations

from backend.middleware import (
    STORM_ID_PATTERN,
    RATE_LIMIT_SECONDS,
    check_rate_limit,
    validate_storm_id,
    _next_request_id,
)


class TestStormIDPattern:
    """STORM_ID_PATTERN regex validation."""

    VALID = ["2024-10-G4", "2024-05-G5", "2025-12-G1", "2000-01-G5"]

    INVALID = [
        "2024-10-G6",        # G out of range
        "24-10-G4",          # Year too short
        "2024-G4",           # Missing month
        "G4",                # Just G scale
        "2024-10-g4",        # Lowercase
        "2024-10-G4-extra",  # Extra content
        "../../etc/passwd",  # Path traversal
        "'; DROP TABLE--",   # SQL injection
        "",                  # Empty
    ]

    def test_valid_ids_match(self):
        for sid in self.VALID:
            assert STORM_ID_PATTERN.match(sid), f"{sid} should match"

    def test_invalid_ids_rejected(self):
        for sid in self.INVALID:
            assert not STORM_ID_PATTERN.match(sid), f"{sid} should not match"


class TestValidateStormID:
    """validate_storm_id() wrapper function."""

    def test_valid(self):
        assert validate_storm_id("2024-10-G4") is True

    def test_invalid_format(self):
        assert validate_storm_id("invalid") is False

    def test_empty(self):
        assert validate_storm_id("") is False


class TestRateLimit:
    """check_rate_limit() — simple timestamp-based limiter."""

    def test_allows_first_call(self):
        from backend import middleware
        middleware._pipeline_calls.clear()
        assert check_rate_limit("rl-test-1") is True

    def test_blocks_second_call(self):
        from backend import middleware
        middleware._pipeline_calls.clear()
        check_rate_limit("rl-test-2")
        assert check_rate_limit("rl-test-2") is False

    def test_different_storms_independent(self):
        from backend import middleware
        middleware._pipeline_calls.clear()
        assert check_rate_limit("storm-a") is True
        assert check_rate_limit("storm-b") is True
        assert check_rate_limit("storm-a") is False
        assert check_rate_limit("storm-b") is False

    def test_rate_limit_window_constant(self):
        assert RATE_LIMIT_SECONDS == 30


class TestRequestID:
    """_next_request_id() — monotonic counter."""

    def test_format(self):
        rid = _next_request_id()
        assert rid.startswith("req-")

    def test_unique(self):
        ids = [_next_request_id() for _ in range(50)]
        assert len(ids) == len(set(ids))

    def test_increments(self):
        a = _next_request_id()
        b = _next_request_id()
        assert int(b.split("-")[-1]) > int(a.split("-")[-1])
