# API Contracts

## Base Information

- **Base URL (Dev)**: `http://localhost:8000`
- **Base URL (Prod)**: As deployed
- **Auth**: `X-HelioOps-Key` header — SHA-256 hashed API key
- **All timestamps**: ISO 8601 UTC
- **Content-Type**: `application/json`
- **Error format**: `{ "error": { "code": "STRING_CODE", "message": "Human-readable message" } }`

---

## Authentication

All endpoints require `X-HelioOps-Key` header unless marked `Auth: None`.

**Roles**: `admin`, `operator`, `viewer`

| Header | Value |
|--------|-------|
| `X-HelioOps-Key` | `sk_heliops_...` (32-char hex string) |

**Error 401**:
```json
{ "error": { "code": "UNAUTHORIZED", "message": "Missing or invalid API key" } }
```

**Error 403**:
```json
{ "error": { "code": "FORBIDDEN", "message": "Insufficient role. Required: operator" } }
```

---

## Health

### GET /health
**Auth**: None

**Response 200**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "connected",
  "redis": "connected",
  "uptime_seconds": 1234
}
```

---

## Storms

### GET /api/v1/storms
**Auth**: API key (`viewer+`)
**Query params**: `page` (int, default 1), `per_page` (int, default 20), `status` (string, optional)

**Response 200**:
```json
{
  "data": [
    {
      "id": "uuid",
      "g_scale": 4,
      "s_scale": 0,
      "r_scale": 0,
      "kp_index": 8.3,
      "eta_minutes": 45,
      "peak_window_start": "2026-06-08T06:00:00Z",
      "peak_window_end": "2026-06-08T18:00:00Z",
      "status": "delivered",
      "advisory_count": 3,
      "created_at": "2026-06-08T05:15:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3
  }
}
```

### GET /api/v1/storms/{id}
**Auth**: API key (`viewer+`)

**Response 200**:
```json
{
  "data": {
    "id": "uuid",
    "alert_id": "sha256_hash",
    "raw_payload": "Full NOAA alert text...",
    "g_scale": 4,
    "s_scale": 0,
    "r_scale": 0,
    "kp_index": 8.3,
    "eta_minutes": 45,
    "peak_window_start": "2026-06-08T06:00:00Z",
    "peak_window_end": "2026-06-08T18:00:00Z",
    "status": "delivered",
    "advisories": [
      {
        "id": "uuid",
        "industry": "aviation",
        "severity": "CRITICAL",
        "status": "approved",
        "crm_ticket_id": "uuid"
      }
    ],
    "created_at": "2026-06-08T05:15:00Z",
    "resolved_at": "2026-06-08T19:00:00Z"
  }
}
```

**Response 404**:
```json
{ "error": { "code": "NOT_FOUND", "message": "Storm event not found" } }
```

---

## Advisories

### GET /api/v1/advisories
**Auth**: API key (`viewer+`)
**Query params**: `page`, `per_page`, `industry` (optional: aviation|grid|telecom|maritime), `status` (optional), `storm_event_id` (optional)

**Response 200**:
```json
{
  "data": [
    {
      "id": "uuid",
      "storm_event_id": "uuid",
      "industry": "aviation",
      "severity": "CRITICAL",
      "status": "pending_review",
      "confidence": 0.91,
      "crm_ticket_id": "uuid",
      "action_items": [
        "Re-route all flights above 78N",
        "Switch HF to 8825 kHz backup"
      ],
      "timing_window": "2026-06-08T06:00Z/18:00Z",
      "affected_routes": ["NAT Track A", "Polar 1"],
      "created_at": "2026-06-08T05:20:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 15, "total_pages": 1 }
}
```

### POST /api/v1/advisories/{id}/approve
**Auth**: API key (`operator+`)

**Request**:
```json
{
  "operator_name": "Jane Doe",
  "notes": "All action items verified against ICAO NAT Doc 007"
}
```

**Response 200**:
```json
{
  "data": {
    "id": "uuid",
    "status": "approved",
    "approved_by": "Jane Doe",
    "approved_at": "2026-06-08T05:25:00Z",
    "crm_ticket_id": "uuid"
  }
}
```

**Response 409** (already actioned):
```json
{ "error": { "code": "ALREADY_ACTIONED", "message": "Advisory already approved/rejected" } }
```

### POST /api/v1/advisories/{id}/reject
**Auth**: API key (`operator+`)

**Request**:
```json
{
  "operator_name": "Jane Doe",
  "reason": "Storm subsiding faster than predicted — no action needed"
}
```

**Response 200**:
```json
{
  "data": {
    "id": "uuid",
    "status": "rejected",
    "approved_by": "Jane Doe",
    "approved_at": "2026-06-08T05:25:00Z",
    "outcome": "storm_subsided"
  }
}
```

---

## Dashboard

### GET /api/v1/dashboard/summary
**Auth**: API key (`viewer+`)

**Response 200**:
```json
{
  "data": {
    "current_storm_status": "critical",
    "current_g_scale": 4,
    "current_kp_index": 8.3,
    "active_storms": 1,
    "active_advisories": 3,
    "advisories_by_status": {
      "pending_review": 2,
      "approved": 1,
      "dispatched": 0
    },
    "last_checked": "2026-06-08T05:15:00Z"
  }
}
```

---

## Replay

### POST /api/v1/replay
**Auth**: API key (`admin`)

**Request**:
```json
{
  "date": "2024-05-10",
  "industries": ["aviation", "grid"]
}
```

**Response 202**:
```json
{
  "data": {
    "storm_event_id": "uuid",
    "status": "processing",
    "message": "Replaying storm from 2024-05-10"
  }
}
```

---

## WebSocket — /ws/stream

**Auth**: Query param `token` (API key value)

**Connection**: `ws://localhost:8000/ws/stream?token=sk_heliops_...`

### Server → Client Events

**storm.detected**:
```json
{ "type": "storm.detected", "payload": { "event_id": "uuid", "g_scale": 4, "kp_index": 8.3, "eta_min": 45 } }
```

**agent.thinking** (streamed per-token):
```json
{ "type": "agent.thinking", "payload": { "industry": "aviation", "token": "Based", "cumulative_text": "Based on G4 severity..." } }
```

**advisory.ready**:
```json
{ "type": "advisory.ready", "payload": { "advisory_id": "uuid", "industry": "aviation", "severity": "CRITICAL", "action_items": ["Re-route all flights above 78N"] } }
```

**advisory.dispatched**:
```json
{ "type": "advisory.dispatched", "payload": { "advisory_id": "uuid", "channels": ["email", "slack"], "ticket_id": "uuid" } }
```

**storm.resolved**:
```json
{ "type": "storm.resolved", "payload": { "event_id": "uuid", "duration_min": 780 } }
```

### Client → Server Events

None in v1. Clients subscribe per-industry via query param: `/ws/stream?token=...&industries=aviation,grid`

---

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| UNAUTHORIZED | 401 | Missing or invalid API key |
| FORBIDDEN | 403 | Valid key but insufficient role |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 422 | Request body/params invalid |
| ALREADY_ACTIONED | 409 | Advisory already approved/rejected |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server error |

**Validation Error Response (422)**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "fields": { "operator_name": "Field required" }
  }
}
```
