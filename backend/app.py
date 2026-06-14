"""
backend/app.py — FastAPI server bridging all HelioOps layers.

Architecture: Hexagonal (Ports & Adapters)
  - Domain logic depends on abstract ports (backend.ports.*)
  - Adapters (backend.adapters.*) provide concrete implementations
  - Dependency injection wires adapters to ports at startup

Endpoints:
    POST /api/detect/{storm_id}    — run full pipeline
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
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from backend.config import settings
from backend.logging import setup_logging, get_logger

setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
log = get_logger("backend.app")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.detection_adapter import CVDetectionAdapter
from backend.adapters.prediction_adapter import MLPredictionAdapter
from backend.adapters.advisory_adapter import GenAIAdvisoryAdapter, GenAIVerificationAdapter
from backend.adapters.repository_adapter import InMemoryResultRepository
from backend.adapters.schema_adapter import adapt_storm_event
from backend.health import router as health_router
from backend.health import (
    record_pipeline_request,
    record_pipeline_error,
    record_pipeline_duration,
    record_detection_request,
    record_advisory_request,
)
from backend.health import _requester_metrics
from backend.pipeline import PipelineResult, run_full_pipeline, stream_full_pipeline

app = FastAPI(
    title="HelioOps API",
    description="Space weather detection → impact prediction → advisory generation → verification",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

detection_adapter = CVDetectionAdapter(available_storm_ids=settings.AVAILABLE_STORM_IDS)
prediction_adapter = MLPredictionAdapter()
advisory_adapter = GenAIAdvisoryAdapter()
verification_adapter = GenAIVerificationAdapter()
result_repo = InMemoryResultRepository()


def _available_storms() -> list[str]:
    return detection_adapter.available_storm_ids()


@app.post("/api/detect/{storm_id}", response_model=PipelineResult)
async def detect_storm(storm_id: str):
    start = time.monotonic()
    record_pipeline_request()
    available = _available_storms()
    if storm_id not in available:
        raise HTTPException(status_code=404, detail=f"Unknown storm_id '{storm_id}'. Available: {available}")

    try:
        result = await run_full_pipeline(storm_id)
    except Exception as exc:
        record_pipeline_error()
        log.error("pipeline_error", storm_id=storm_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")

    duration = time.monotonic() - start
    record_pipeline_duration(duration)
    log.info("pipeline_completed", storm_id=storm_id, duration_seconds=round(duration, 3))

    if not result.cv_event:
        record_pipeline_error()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {result.errors}")

    return result


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
    data = result_repo.get_advisory(advisory_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Advisory '{advisory_id}' not found")
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
    await _ws_manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_manager.send(ws, {"event": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")
            storm_id = msg.get("storm_id")

            if action == "run_pipeline" and storm_id:
                available = _available_storms()
                if storm_id not in available:
                    await _ws_manager.send(ws, {
                        "event": "error",
                        "message": f"Unknown storm_id. Available: {available}",
                    })
                    continue

                async for event in stream_full_pipeline(storm_id):
                    await _ws_manager.send(ws, event)
            else:
                await _ws_manager.send(ws, {
                    "event": "error",
                    "message": "Send {\"action\": \"run_pipeline\", \"storm_id\": \"...\"}",
                })
    except WebSocketDisconnect:
        _ws_manager.disconnect(ws)