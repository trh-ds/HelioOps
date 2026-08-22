"""
backend/app.py — FastAPI server bridging all HelioOps layers.

Architecture: Adapter-wrapped layers
  - Adapters wrap external systems (cv, ML, genai, supabase)
  - Dependency injection wires adapters at startup

Endpoints:
    POST /api/detect/{storm_id}    — run full pipeline
    GET  /api/preflight/{storm_id} — read-only pre-run conflict check
    GET  /api/storms               — list available + completed storms
    GET  /api/advisory/{id}        — single verified advisory + provenance
    GET  /api/result/{storm_id}    — full pipeline result
    WS   /ws/stream                — real-time pipeline streaming
    GET  /health                   — liveness
    GET  /health/ready             — readiness (checks dep layers)
    GET  /health/live              — liveness (process check)
    GET  /metrics                  — Prometheus metrics
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager

from backend.config import settings
from backend.logging import setup_logging, get_logger

setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
log = get_logger("backend.app")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.middleware import (
    SecurityHeadersMiddleware,
    RequestIDMiddleware,
    check_rate_limit,
    validate_storm_id,
)

from backend.adapters.repository_adapter import InMemoryResultRepository, SupabaseResultRepository
from backend.health import router as health_router
from backend.health import (
    record_pipeline_request,
    record_pipeline_error,
    record_pipeline_duration,
    record_detection_request,
    record_advisory_request,
)
from backend.health import _requester_metrics
from backend.pipeline import (
    PipelineResult,
    detection_adapter,
    get_result,
    run_full_pipeline,
    stream_full_pipeline,
)

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """
    The Run gate calls /api/preflight on every click, and its health section
    loads the six ML checkpoints and counts every Chroma collection: ~10s cold.
    Pay it once at boot so no user ever waits for it.
    """
    from backend.preflight import health_snapshot

    try:
        await asyncio.to_thread(health_snapshot, True)
    except Exception as exc:  # a warm-up must never stop the app from serving
        log.warning("preflight health warm-up skipped: %s", exc)
    yield


app = FastAPI(
    title="HelioOps API",
    description="Space weather detection → impact prediction → advisory generation → verification",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(health_router)


def _build_result_repository():
    if settings.RESULT_REPOSITORY.lower() == "supabase":
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise RuntimeError(
                "Supabase repository selected, but HELIOOPS_SUPABASE_URL "
                "or HELIOOPS_SUPABASE_ANON_KEY is missing."
            )
        return SupabaseResultRepository(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
            pipeline_results_table=settings.SUPABASE_PIPELINE_RESULTS_TABLE,
            advisories_table=settings.SUPABASE_ADVISORIES_TABLE,
            verified_advisories_table=settings.SUPABASE_VERIFIED_ADVISORIES_TABLE,
            provenance_traces_table=settings.SUPABASE_PROVENANCE_TRACES_TABLE,
        )
    return InMemoryResultRepository()


result_repo = _build_result_repository()


def _persist_result(result: PipelineResult) -> None:
    result_repo.save(result.storm_id, result)
    for advisory, verified, provenance in zip(
        result.advisories,
        result.verified_advisories,
        result.provenance_traces,
    ):
        record = {
            "storm_id": result.storm_id,
            "advisory": advisory,
            "verified_advisory": verified,
            "provenance_trace": provenance,
        }
        # Index under BOTH ids. The verifier mints its own readable id
        # ("adv_2024-05-G5_aviation_838a16bf") and only that one used to be
        # stored — but the payload the dashboard renders is the raw advisory,
        # which carries a UUID. So every lookup driven by what the UI actually
        # displays (and by api.ts, which documents the param as a UUID) 404'd.
        advisory_id = _advisory_field(advisory, "advisory_id")
        verified_id = verified.get("advisory_id") if isinstance(verified, dict) else None
        for key in {advisory_id, verified_id}:
            if key:
                result_repo.save_advisory(key, record)


def _advisory_field(advisory, field: str):
    """Advisories cross this boundary as either a model or an already-dumped dict."""
    if isinstance(advisory, dict):
        return advisory.get(field)
    return getattr(advisory, field, None)


def _available_storms() -> list[str]:
    return detection_adapter.available_storm_ids()


@app.post("/api/detect/{storm_id}", response_model=PipelineResult)
async def detect_storm(storm_id: str):
    if not validate_storm_id(storm_id):
        raise HTTPException(
            status_code=400, detail=f"Invalid storm_id format: {storm_id}"
        )
    if not check_rate_limit(storm_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit: wait 30s between pipeline runs for this storm",
        )

    start = time.monotonic()
    record_pipeline_request()
    record_detection_request()
    available = _available_storms()
    if storm_id not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown storm_id '{storm_id}'. Available: {available}",
        )

    try:
        result = await run_full_pipeline(storm_id)
    except Exception as exc:
        record_pipeline_error()
        log.error("pipeline_error", storm_id=storm_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")

    duration = time.monotonic() - start
    record_pipeline_duration(duration)
    log.info(
        "pipeline_completed", storm_id=storm_id, duration_seconds=round(duration, 3)
    )
    try:
        _persist_result(result)
    except Exception as exc:
        record_pipeline_error()
        log.error("repository_persist_error", storm_id=storm_id, error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Pipeline result could not be saved: {exc}"
        )

    if not result.cv_event:
        record_pipeline_error()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {result.errors}")

    return result


@app.get("/api/preflight/{storm_id}")
async def preflight_storm(storm_id: str):
    # Same gates as detect_storm, minus everything that mutates: no
    # check_rate_limit (it records on read), no record_* counters.
    if not validate_storm_id(storm_id):
        raise HTTPException(
            status_code=400, detail=f"Invalid storm_id format: {storm_id}"
        )
    available = _available_storms()
    if storm_id not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown storm_id '{storm_id}'. Available: {available}",
        )
    from backend.preflight import run_preflight

    return await run_preflight(storm_id)


@app.get("/api/storms")
async def list_storms():
    available = _available_storms()
    completed = result_repo.get_all()

    return {
        "available_storms": available,
        "completed": {
            sid: {
                "storm_id": r.storm_id,
                "completed_at": r.completed_at,
                "advisory_count": len(r.advisories),
                "verified_count": len(r.verified_advisories),
                "error_count": len(r.errors),
            }
            for sid, r in completed.items()
        },
    }


@app.get("/api/advisory/{advisory_id}")
async def get_advisory_endpoint(advisory_id: str):
    record_advisory_request()
    data = result_repo.get_advisory(advisory_id)
    if data is None:
        raise HTTPException(
            status_code=404, detail=f"Advisory '{advisory_id}' not found"
        )
    return data


@app.get("/api/result/{storm_id}")
async def get_result_endpoint(storm_id: str):
    result = result_repo.get(storm_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result for storm '{storm_id}'")
    return result


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        _requester_metrics["ws_connections_total"] += 1

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def send(self, ws: WebSocket, data: dict):
        await ws.send_text(json.dumps(data, default=str))


_ws_manager = ConnectionManager()


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    origin = ws.headers.get("origin", "")
    allowed = settings.CORS_ORIGINS
    if origin and not any(origin.startswith(o) for o in allowed):
        await ws.close(code=4003, reason="Origin not allowed")
        return

    await _ws_manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_manager.send(
                    ws, {"event": "error", "message": "Invalid JSON"}
                )
                continue

            action = msg.get("action")
            storm_id = msg.get("storm_id")

            if action == "run_pipeline" and storm_id:
                if not validate_storm_id(storm_id):
                    await _ws_manager.send(
                        ws,
                        {
                            "event": "error",
                            "message": f"Invalid storm_id format: {storm_id}",
                        },
                    )
                    continue

                available = _available_storms()
                if storm_id not in available:
                    await _ws_manager.send(
                        ws,
                        {
                            "event": "error",
                            "message": f"Unknown storm_id. Available: {available}",
                        },
                    )
                    continue

                if not check_rate_limit(storm_id):
                    await _ws_manager.send(
                        ws,
                        {
                            "event": "error",
                            "message": "Rate limit: wait 30s between pipeline runs for this storm",
                        },
                    )
                    continue

                async for event in stream_full_pipeline(storm_id):
                    await _ws_manager.send(ws, event)
                streamed_result = get_result(storm_id)
                if streamed_result:
                    try:
                        _persist_result(streamed_result)
                    except Exception as exc:
                        log.error(
                            "repository_persist_error",
                            storm_id=storm_id,
                            error=str(exc),
                        )
                        await _ws_manager.send(
                            ws,
                            {
                                "event": "error",
                                "message": f"Pipeline result could not be saved: {exc}",
                            },
                        )
            else:
                await _ws_manager.send(
                    ws,
                    {
                        "event": "error",
                        "message": 'Send {"action": "run_pipeline", "storm_id": "..."}',
                    },
                )
    except WebSocketDisconnect:
        _ws_manager.disconnect(ws)
