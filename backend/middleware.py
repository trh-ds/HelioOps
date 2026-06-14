"""
backend/middleware.py — Security middleware for HelioOps.

Provides:
  - Security headers on all responses
  - Request ID tracing
  - Pipeline rate limiting (1 run per storm per 30s)
  - Storm ID format validation
"""

from __future__ import annotations

import re
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ── Security Headers ────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response


# ── Request ID ──────────────────────────────────────────────────────────────

_request_id_counter = 0


def _next_request_id() -> str:
    global _request_id_counter
    _request_id_counter += 1
    return f"req-{int(time.time())}-{_request_id_counter}"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = _next_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Pipeline Rate Limiting ──────────────────────────────────────────────────

_pipeline_calls: dict[str, float] = {}
RATE_LIMIT_SECONDS = 30  # one pipeline run per storm per 30s


def check_rate_limit(storm_id: str) -> bool:
    """
    Return True if the pipeline call is allowed, False if rate-limited.
    """
    now = time.time()
    last = _pipeline_calls.get(storm_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _pipeline_calls[storm_id] = now
    return True


# ── Storm ID Validation ────────────────────────────────────────────────────

STORM_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-G[1-5]$")


def validate_storm_id(storm_id: str) -> bool:
    """Return True if storm_id matches the required format."""
    return bool(STORM_ID_PATTERN.match(storm_id))
