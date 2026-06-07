import os
import uuid
import hashlib
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncpg
import redis.asyncio as aioredis
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("heliops")

# ─── Config ─────────────────────────────────────────────────────────────────

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/heliops")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    API_KEY_ADMIN_HASH: str = os.getenv("API_KEY_ADMIN_HASH", "")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    RATE_LIMIT_AUTH_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL: str = os.getenv("SENDGRID_FROM_EMAIL", "heliops@zylonlabs.com")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_ALERTS_CHANNEL: str = os.getenv("SLACK_ALERTS_CHANNEL", "#heliops-alerts")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

settings = Settings()

# ─── Application State ──────────────────────────────────────────────────────

class AppState:
    def __init__(self):
        self.db: Optional[asyncpg.Pool] = None
        self.redis: Optional[aioredis.Redis] = None
        self.http: Optional[httpx.AsyncClient] = None
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.start_time: datetime = datetime.now(timezone.utc)
        self.ws_connections: dict[str, set[WebSocket]] = {}  # {industry: {ws, ...}}

state = AppState()

# ─── Database ────────────────────────────────────────────────────────────────

DB_POOL_MIN = 5
DB_POOL_MAX = 20

async def init_db() -> asyncpg.Pool:
    log.info("Connecting to database...")
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=DB_POOL_MIN,
        max_size=DB_POOL_MAX,
        command_timeout=10,
    )
    log.info("Database pool created (min=%d, max=%d)", DB_POOL_MIN, DB_POOL_MAX)
    return pool

async def check_db(pool: asyncpg.Pool) -> bool:
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False

# ─── Redis ───────────────────────────────────────────────────────────────────

async def init_redis() -> aioredis.Redis:
    log.info("Connecting to Redis...")
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.ping()
    log.info("Redis connected")
    return r

# ─── API Key Auth ────────────────────────────────────────────────────────────

API_KEYS_CACHE: dict[str, dict] = {}

async def load_api_keys(pool: asyncpg.Pool):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key_hash, role, client_id, is_active FROM api_keys WHERE is_active = true")
            for row in rows:
                API_KEYS_CACHE[row["key_hash"]] = {
                    "role": row["role"],
                    "client_id": row["client_id"],
                }
            log.info("Loaded %d API keys", len(rows))
    except Exception as e:
        log.warning("Could not load API keys from DB: %s — using defaults", e)
        if settings.API_KEY_ADMIN_HASH:
            API_KEYS_CACHE[settings.API_KEY_ADMIN_HASH] = {"role": "admin", "client_id": "default"}

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

async def verify_api_key(request: Request) -> dict:
    raw_key = request.headers.get("X-HelioOps-Key", "")
    if not raw_key:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Missing X-HelioOps-Key header"})
    key_hash = hash_api_key(raw_key)
    entry = API_KEYS_CACHE.get(key_hash)
    if not entry:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid API key"})
    return entry

def require_role(min_role: str):
    async def checker(auth: dict = Depends(verify_api_key)) -> dict:
        roles = {"admin": 3, "operator": 2, "viewer": 1}
        if roles.get(auth["role"], 0) < roles.get(min_role, 0):
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": f"Insufficient role. Required: {min_role}"})
        return auth
    return checker

# ─── CORS ────────────────────────────────────────────────────────────────────

# ─── Rate Limiter ────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ─── WebSocket Connection Manager ────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, industries: list[str]):
        await ws.accept()
        for ind in industries:
            self.connections.setdefault(ind, set()).add(ws)

    async def disconnect(self, ws: WebSocket, industries: list[str]):
        for ind in industries:
            self.connections.get(ind, set()).discard(ws)

    async def broadcast(self, industry: str, event: dict):
        dead = set()
        for ws in self.connections.get(industry, set()):
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        if dead:
            self.connections[industry] -= dead

    async def broadcast_all(self, event: dict):
        for ind in list(self.connections.keys()):
            await self.broadcast(ind, event)

ws_manager = ConnectionManager()

# ─── Event Types ─────────────────────────────────────────────────────────────

WS_EVENT_STORM_DETECTED = "storm.detected"
WS_EVENT_AGENT_THINKING = "agent.thinking"
WS_EVENT_ADVISORY_READY = "advisory.ready"
WS_EVENT_ADVISORY_DISPATCHED = "advisory.dispatched"
WS_EVENT_STORM_RESOLVED = "storm.resolved"

def make_ws_event(event_type: str, payload: dict) -> dict:
    return {"type": event_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)

class StormListParams(PaginationParams):
    status: Optional[str] = None

class AdvisoryListParams(PaginationParams):
    industry: Optional[str] = None
    status: Optional[str] = None
    storm_event_id: Optional[str] = None

class ApproveRequest(BaseModel):
    operator_name: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = None

class RejectRequest(BaseModel):
    operator_name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)

class ReplayRequest(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    industries: Optional[list[str]] = None

# ─── Response Helpers ────────────────────────────────────────────────────────

def ok_response(data: any) -> dict:
    return {"data": data}

def error_response(code: str, message: str, fields: Optional[dict] = None) -> dict:
    resp = {"error": {"code": code, "message": message}}
    if fields:
        resp["error"]["fields"] = fields
    return resp

def paginated_response(data: list, total: int, page: int, per_page: int) -> dict:
    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        },
    }

# ─── CRM Ticket Service ──────────────────────────────────────────────────────

CRM_STATUS_WORKFLOW = {
    "pending_review": ["approved", "rejected"],
    "approved": ["actioned", "resolved"],
    "rejected": ["resolved"],
    "actioned": ["resolved"],
    "resolved": [],
}

async def create_crm_ticket(pool: asyncpg.Pool, advisory_id: str, industry: str, severity: str, g_scale: int, action_items: list[str]) -> str:
    ticket_id = str(uuid.uuid4())
    title = f"G{g_scale} Storm — {industry.title()} Advisory — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    body = "\n".join(f"{i+1}. {item}" for i, item in enumerate(action_items))
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO crm_tickets (id, advisory_id, title, body, status, created_at)
               VALUES ($1, $2, $3, $4, 'pending_review', NOW())""",
            ticket_id, advisory_id, title, body,
        )
    return ticket_id

async def update_ticket_status(pool: asyncpg.Pool, ticket_id: str, new_status: str, outcome: Optional[str] = None):
    async with pool.acquire() as conn:
        if outcome:
            await conn.execute(
                "UPDATE crm_tickets SET status=$1, outcome=$2, closed_at=NOW() WHERE id=$3",
                new_status, outcome, ticket_id,
            )
        else:
            await conn.execute("UPDATE crm_tickets SET status=$1 WHERE id=$2", new_status, ticket_id)

# ─── Notification Service (Mocked) ───────────────────────────────────────────

class NotificationService:
    async def send_email(self, to: str, subject: str, body: str, severity: str):
        log.info("[EMAIL MOCK] To=%s | Subject=%s | Severity=%s | Body=%s", to, subject, severity, body[:200])

    async def send_slack(self, channel: str, blocks: list[dict]):
        log.info("[SLACK MOCK] Channel=%s | Blocks=%s", channel, json.dumps(blocks, indent=2)[:500])

    async def dispatch_advisory(self, advisory: dict):
        tasks = []
        tasks.append(self.send_email(
            to="ops@example.com",
            subject=f"HelioOps Advisory: {advisory['industry']} - {advisory['severity']}",
            body=json.dumps(advisory, indent=2),
            severity=advisory['severity'],
        ))
        tasks.append(self.send_slack(
            channel=settings.SLACK_ALERTS_CHANNEL,
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": f"⚠️ {advisory['severity']} - {advisory['industry'].title()} Advisory"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Action Items:*\n" + "\n".join(f"• {a}" for a in advisory.get("action_items", []))}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"}, "style": "primary", "value": f"approve:{advisory['id']}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "❌ Reject"}, "style": "danger", "value": f"reject:{advisory['id']}"},
                ]},
            ],
        ))
        await asyncio.gather(*tasks, return_exceptions=True)

notifier = NotificationService()

# ─── Cache Service ───────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[str]:
    if state.redis:
        return await state.redis.get(f"cache:{key}")
    return None

async def cache_set(key: str, value: str, ttl: int = 300):
    if state.redis:
        await state.redis.setex(f"cache:{key}", ttl, value)

# ─── Lifecycle ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting HelioOps backend...")
    state.db = await init_db()
    state.redis = await init_redis()
    state.http = httpx.AsyncClient(timeout=30.0)
    await load_api_keys(state.db)
    state.scheduler = AsyncIOScheduler()
    state.scheduler.start()
    log.info("HelioOps backend started")
    yield
    log.info("Shutting down HelioOps backend...")
    if state.scheduler:
        state.scheduler.shutdown(wait=False)
    if state.http:
        await state.http.aclose()
    if state.redis:
        await state.redis.close()
    if state.db:
        await state.db.close()
    log.info("HelioOps backend shut down")

# ─── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="HelioOps API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    db_ok = await check_db(state.db) if state.db else False
    redis_ok = await state.redis.ping() if state.redis else False
    uptime = int((datetime.now(timezone.utc) - state.start_time).total_seconds())
    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "version": "0.1.0",
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "uptime_seconds": uptime,
    }

# ─── Storms ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/storms")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def list_storms(request: Request, page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), status: Optional[str] = None, auth: dict = Depends(require_role("viewer"))):
    async with state.db.acquire() as conn:
        where = "WHERE ($1::text IS NULL OR status = $1)" if status else "WHERE TRUE"
        params = [status] if status else []
        count = await conn.fetchval(f"SELECT COUNT(*) FROM storm_events {where}", *params)
        offset = (page - 1) * per_page
        rows = await conn.fetch(
            f"SELECT id, g_scale, kp_index, eta_minutes, peak_window_start, peak_window_end, status, created_at "
            f"FROM storm_events {where} ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            *([status] if status else [None]), per_page, offset,
        )
    data = [dict(r) for r in rows]
    for d in data:
        d["id"] = str(d["id"])
        d["advisory_count"] = 0
    return paginated_response(data, count, page, per_page)

@app.get("/api/v1/storms/{storm_id}")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def get_storm(request: Request, storm_id: str, auth: dict = Depends(require_role("viewer"))):
    async with state.db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM storm_events WHERE id = $1", storm_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Storm event not found"})
        advisories = await conn.fetch("SELECT id, industry, severity, status, crm_ticket_id FROM advisories WHERE storm_event_id = $1", storm_id)
    data = dict(row)
    data["id"] = str(data["id"])
    data["advisories"] = [dict(a) for a in advisories]
    return ok_response(data)

# ─── Advisories ──────────────────────────────────────────────────────────────

@app.get("/api/v1/advisories")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def list_advisories(
    request: Request,
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    industry: Optional[str] = None, status: Optional[str] = None, storm_event_id: Optional[str] = None,
    auth: dict = Depends(require_role("viewer")),
):
    conditions = []
    params = []
    idx = 1
    if industry:
        conditions.append(f"industry = ${idx}"); params.append(industry); idx += 1
    if status:
        conditions.append(f"status = ${idx}"); params.append(status); idx += 1
    if storm_event_id:
        conditions.append(f"storm_event_id = ${idx}"); params.append(storm_event_id); idx += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else "WHERE TRUE"
    async with state.db.acquire() as conn:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM advisories {where}", *params)
        offset = (page - 1) * per_page
        rows = await conn.fetch(
            f"SELECT id, storm_event_id, industry, severity, status, confidence, crm_ticket_id, "
            f"advisory_json->>'action_items' as action_items, "
            f"advisory_json->>'timing_window' as timing_window, "
            f"advisory_json->>'affected_routes' as affected_routes, "
            f"created_at FROM advisories {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
            *params, per_page, offset,
        )
    data = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"]);
        d["storm_event_id"] = str(d["storm_event_id"])
        try:
            d["action_items"] = json.loads(d["action_items"]) if d["action_items"] else []
        except (json.JSONDecodeError, TypeError):
            d["action_items"] = []
        data.append(d)
    return paginated_response(data, count, page, per_page)

@app.post("/api/v1/advisories/{advisory_id}/approve")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def approve_advisory(request: Request, advisory_id: str, body: ApproveRequest, auth: dict = Depends(require_role("operator"))):
    async with state.db.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status, crm_ticket_id FROM advisories WHERE id = $1", advisory_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Advisory not found"})
        if row["status"] != "pending_review":
            raise HTTPException(status_code=409, detail={"code": "ALREADY_ACTIONED", "message": "Advisory already approved/rejected"})
        await conn.execute(
            "UPDATE advisories SET status='approved', approved_by=$1, approved_at=NOW() WHERE id=$2",
            body.operator_name, advisory_id,
        )
        if row["crm_ticket_id"]:
            await update_ticket_status(state.db, row["crm_ticket_id"], "approved")
        await conn.execute(
            "INSERT INTO feedback_log (id, advisory_id, operator_action, operator_notes, logged_at) VALUES ($1, $2, 'approved', $3, NOW())",
            str(uuid.uuid4()), advisory_id, body.notes or "",
        )
    await ws_manager.broadcast_all(make_ws_event("advisory.ready", {"advisory_id": advisory_id, "status": "approved"}))
    return ok_response({"id": advisory_id, "status": "approved", "approved_by": body.operator_name, "approved_at": datetime.now(timezone.utc).isoformat()})

@app.post("/api/v1/advisories/{advisory_id}/reject")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def reject_advisory(request: Request, advisory_id: str, body: RejectRequest, auth: dict = Depends(require_role("operator"))):
    async with state.db.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status, crm_ticket_id FROM advisories WHERE id = $1", advisory_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Advisory not found"})
        if row["status"] != "pending_review":
            raise HTTPException(status_code=409, detail={"code": "ALREADY_ACTIONED", "message": "Advisory already approved/rejected"})
        await conn.execute("UPDATE advisories SET status='rejected', approved_by=$1, approved_at=NOW() WHERE id=$2", body.operator_name, advisory_id)
        if row["crm_ticket_id"]:
            await update_ticket_status(state.db, row["crm_ticket_id"], "rejected", "storm_subsided")
        await conn.execute(
            "INSERT INTO feedback_log (id, advisory_id, operator_action, outcome, operator_notes, logged_at) VALUES ($1, $2, 'rejected', 'storm_subsided', $3, NOW())",
            str(uuid.uuid4()), advisory_id, body.reason,
        )
    await ws_manager.broadcast_all(make_ws_event("advisory.ready", {"advisory_id": advisory_id, "status": "rejected"}))
    return ok_response({"id": advisory_id, "status": "rejected", "approved_by": body.operator_name, "approved_at": datetime.now(timezone.utc).isoformat()})

# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard/summary")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def dashboard_summary(request: Request, auth: dict = Depends(require_role("viewer"))):
    cached = await cache_get("dashboard_summary")
    if cached:
        return ok_response(json.loads(cached))
    async with state.db.acquire() as conn:
        active = await conn.fetchval("SELECT COUNT(*) FROM storm_events WHERE status NOT IN ('resolved', 'resolved')")
        row = await conn.fetchrow("SELECT g_scale, kp_index FROM storm_events WHERE status NOT IN ('resolved') ORDER BY created_at DESC LIMIT 1")
        advisory_counts = await conn.fetch(
            "SELECT status, COUNT(*) as cnt FROM advisories GROUP BY status"
        )
        total_active = await conn.fetchval("SELECT COUNT(*) FROM advisories WHERE status IN ('pending_review', 'approved')")
        last_check = await conn.fetchval("SELECT MAX(created_at) FROM storm_events")
    by_status = {r["status"]: r["cnt"] for r in advisory_counts}
    data = {
        "current_storm_status": "critical" if row and row["g_scale"] >= 4 else ("warning" if row and row["g_scale"] >= 3 else ("watch" if row else "calm")),
        "current_g_scale": row["g_scale"] if row else 0,
        "current_kp_index": float(row["kp_index"]) if row and row["kp_index"] else 0.0,
        "active_storms": active,
        "active_advisories": sum(by_status.get(s, 0) for s in ["pending_review", "approved"]),
        "advisories_by_status": by_status,
        "last_checked": last_check.isoformat() if last_check else None,
    }
    await cache_set("dashboard_summary", json.dumps(data), 30)
    return ok_response(data)

# ─── Replay ──────────────────────────────────────────────────────────────────

@app.post("/api/v1/replay")
@limiter.limit(lambda: f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def replay_storm(request: Request, body: ReplayRequest, auth: dict = Depends(require_role("admin"))):
    log.info("Replay requested for date=%s industries=%s", body.date, body.industries)
    event_id = str(uuid.uuid4())
    async with state.db.acquire() as conn:
        await conn.execute(
            """INSERT INTO storm_events (id, alert_id, raw_payload, g_scale, s_scale, r_scale, kp_index, status, created_at)
               VALUES ($1, $2, $3, 4, 0, 1, 8.3, 'classifying', NOW())""",
            event_id,
            hashlib.sha256(body.date.encode()).hexdigest(),
            json.dumps({"replay_date": body.date, "industries": body.industries}),
        )
    await ws_manager.broadcast_all(make_ws_event("storm.detected", {"event_id": event_id, "g_scale": 4, "kp_index": 8.3, "eta_min": 45}))
    return JSONResponse(
        status_code=202,
        content={"data": {"storm_event_id": event_id, "status": "processing", "message": f"Replaying storm from {body.date}"}},
    )

# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...), industries: str = Query("aviation,grid")):
    key_hash = hash_api_key(token)
    if key_hash not in API_KEYS_CACHE:
        await ws.close(code=4001, reason="Unauthorized")
        return
    ind_list = [i.strip() for i in industries.split(",") if i.strip()]
    await ws_manager.connect(ws, ind_list)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws, ind_list)

# ─── Redis Pub/Sub Bridge ────────────────────────────────────────────────────

async def redis_pubsub_bridge():
    if not state.redis:
        return
    pubsub = state.redis.pubsub()
    await pubsub.subscribe("heliops:events")
    log.info("Redis pub/sub bridge started")
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event = json.loads(message["data"])
                await ws_manager.broadcast_all(event)
            except json.JSONDecodeError:
                log.warning("Invalid pub/sub message: %s", message["data"])
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("heliops:events")

@app.on_event("startup")
async def start_pubsub_bridge():
    asyncio.create_task(redis_pubsub_bridge())

# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL,
    )
