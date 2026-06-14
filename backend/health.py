"""
Health check and Prometheus metrics endpoints.

Provides:
  GET /health        — Basic liveness
  GET /health/ready  — Readiness (checks all dependency layers)
  GET /health/live   — Liveness (simple process check)
  GET /metrics        — Prometheus-compatible metrics
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

router = APIRouter(tags=["monitoring"])

_START_TIME = time.monotonic()
_ARTIFACT_VERSION = "0.1.0"


class _HealthCollector:
    _instance = None
    _checks: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._checks = {}
        return cls._instance

    def register(self, name: str, check_fn) -> None:
        self._checks[name] = check_fn

    def run(self) -> dict[str, bool]:
        results = {}
        for name, fn in self._checks.items():
            try:
                results[name] = fn()
            except Exception:
                results[name] = False
        return results


health_collector = _HealthCollector()


def _check_detection() -> bool:
    try:
        from cv.detect import STORM_CONFIGS
        return len(STORM_CONFIGS) > 0
    except Exception:
        return False


def _check_ml() -> bool:
    try:
        from ML_after_CV.inference import _MODELS, _load_models
        _load_models()
        return len(_MODELS) >= 6
    except Exception:
        return False


def _check_genai() -> bool:
    try:
        from genai.impact_router import route_storm
        return True
    except Exception:
        return False


health_collector.register("detection", _check_detection)
health_collector.register("ml_models", _check_ml)
health_collector.register("genai_module", _check_genai)


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": _ARTIFACT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    checks = health_collector.run()
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "version": _ARTIFACT_VERSION,
    }, status_code


_requester_metrics = {
    "pipeline_requests_total": 0,
    "pipeline_errors_total": 0,
    "pipeline_duration_seconds": [],
    "detection_requests_total": 0,
    "advisory_requests_total": 0,
    "ws_connections_total": 0,
}


def record_pipeline_request():
    _requester_metrics["pipeline_requests_total"] += 1


def record_pipeline_error():
    _requester_metrics["pipeline_errors_total"] += 1


def record_pipeline_duration(seconds: float):
    _requester_metrics["pipeline_duration_seconds"].append(seconds)
    if len(_requester_metrics["pipeline_duration_seconds"]) > 1000:
        _requester_metrics["pipeline_duration_seconds"] = _requester_metrics["pipeline_duration_seconds"][-500:]


def record_detection_request():
    _requester_metrics["detection_requests_total"] += 1


def record_advisory_request():
    _requester_metrics["advisory_requests_total"] += 1


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    uptime = time.monotonic() - _START_TIME
    durations = _requester_metrics["pipeline_duration_seconds"]
    avg_duration = sum(durations) / len(durations) if durations else 0
    p99_duration = sorted(durations)[int(len(durations) * 0.99)] if durations else 0

    lines = [
        "# HELP helioops_uptime_seconds Process uptime in seconds",
        "# TYPE helioops_uptime_seconds gauge",
        f"helioops_uptime_seconds {uptime:.2f}",
        "",
        "# HELP helioops_pipeline_requests_total Total pipeline requests",
        "# TYPE helioops_pipeline_requests_total counter",
        f"helioops_pipeline_requests_total {_requester_metrics['pipeline_requests_total']}",
        "",
        "# HELP helioops_pipeline_errors_total Total pipeline errors",
        "# TYPE helioops_pipeline_errors_total counter",
        f"helioops_pipeline_errors_total {_requester_metrics['pipeline_errors_total']}",
        "",
        "# HELP helioops_pipeline_duration_seconds_avg Average pipeline duration",
        "# TYPE helioops_pipeline_duration_seconds_avg gauge",
        f"helioops_pipeline_duration_seconds_avg {avg_duration:.4f}",
        "",
        "# HELP helioops_pipeline_duration_seconds_p99 P99 pipeline duration",
        "# TYPE helioops_pipeline_duration_seconds_p99 gauge",
        f"helioops_pipeline_duration_seconds_p99 {p99_duration:.4f}",
        "",
        "# HELP helioops_detection_requests_total Total detection requests",
        "# TYPE helioops_detection_requests_total counter",
        f"helioops_detection_requests_total {_requester_metrics['detection_requests_total']}",
        "",
        "# HELP helioops_advisory_requests_total Total advisory requests",
        "# TYPE helioops_advisory_requests_total counter",
        f"helioops_advisory_requests_total {_requester_metrics['advisory_requests_total']}",
        "",
        "# HELP helioops_ws_connections_total Total WebSocket connections",
        "# TYPE helioops_ws_connections_total counter",
        f"helioops_ws_connections_total {_requester_metrics['ws_connections_total']}",
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/plain")