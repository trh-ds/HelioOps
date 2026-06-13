"""
backend/app.py — FastAPI server bridging all HelioOps layers.

Endpoints:
    POST /api/detect/{storm_id}    — run full pipeline
    GET  /api/storms               — list available + completed storms
    GET  /api/advisory/{id}        — single verified advisory + provenance
    WS   /ws/stream                — real-time pipeline streaming

Launch:
    python -m backend.run
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any module reads GROQ_API_KEY
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.pipeline import (
    PipelineResult,
    get_advisory,
    get_all_results,
    get_result,
    run_full_pipeline,
    stream_full_pipeline,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="HelioOps API",
    description="Space weather detection → impact prediction → advisory generation → verification",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Available storm IDs (from cv.detect registry) ───────────────────────────

def _available_storms() -> list[str]:
    from cv.detect import STORM_CONFIGS
    return list(STORM_CONFIGS.keys())


# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/detect/{storm_id}", response_model=PipelineResult)
async def detect_storm(storm_id: str):
    """Run the full HelioOps pipeline for a given storm ID."""
    available = _available_storms()
    if storm_id not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown storm_id '{storm_id}'. Available: {available}",
        )

    result = await run_full_pipeline(storm_id)

    if not result.cv_event:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {result.errors}")

    return result


@app.get("/api/storms")
async def list_storms():
    """List available storm IDs and completed pipeline results."""
    available = _available_storms()
    completed = get_all_results()

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
    """Get a single verified advisory with its provenance trace."""
    data = get_advisory(advisory_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Advisory '{advisory_id}' not found")
    return data


@app.get("/api/result/{storm_id}")
async def get_result_endpoint(storm_id: str):
    """Get the full pipeline result for a previously processed storm."""
    result = get_result(storm_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result for storm '{storm_id}'")
    return result


# ── WebSocket Endpoint ───────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def send(self, ws: WebSocket, data: dict):
        await ws.send_text(json.dumps(data, default=str))


_ws_manager = ConnectionManager()


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """
    WebSocket endpoint for real-time pipeline streaming.

    Client sends: {"action": "run_pipeline", "storm_id": "2024-10-G4"}
    Server streams pipeline events as JSON frames.
    """
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


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "available_storms": _available_storms()}
