# Tech Stack

## Technology Decisions with Rationale

### Backend API — FastAPI (Python 3.11)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Framework** | FastAPI | Async by default, native WebSocket support, auto-generated OpenAPI docs. Spec mandates it. |
| **Runtime** | Uvicorn + Gunicorn | Uvicorn for ASGI, Gunicorn for multi-worker process management in production. |
| **Validation** | Pydantic v2 | Built into FastAPI. Strict validation, JSON Schema generation, serialization. |
| **ORM** | SQLAlchemy 2.0 (async) | Mature, async support via asyncpg, Alembic for migrations. |
| **DB Driver** | asyncpg | Fastest PostgreSQL async driver for Python. |
| **Migrations** | Alembic | Industry standard for SQLAlchemy schema migrations. |
| **HTTP Client** | httpx | Async HTTP client for any outbound calls (NOAA, Groq). |
| **Scheduler** | APScheduler (AsyncIOScheduler) | 5-min NOAA polling. Async-native, embeds in FastAPI lifespan. |
| **WebSocket Pub/Sub** | redis-py + Redis 7 | Multi-worker safe pub/sub. Redis as message broker between workers. |
| **Caching** | Redis 7 | Response caching (5-min TTL), deduplication sets, session state. |
| **Auth** | API Key (SHA-256) | Stateless, simple for M2M. X-HelioOps-Key header. Role-based access. |
| **Rate Limiting** | slowapi | FastAPI-native rate limiter. Redis-backed for distributed counting. |
| **Logging** | structlog | Structured JSON logging. Ready for Grafana Cloud ingestion. |
| **Error Monitoring** | Sentry SDK | Wired but disabled until DSN provided. |
| **Email** | SendGrid SDK (mocked) | Transactional email. Free tier: 100 emails/day. |
| **Slack** | slack-bolt SDK (mocked) | Block Kit messages with interactive approve/reject buttons. |

### Databases & Storage

| Store | Service | Purpose |
|-------|---------|---------|
| **PostgreSQL** | Supabase Free Tier | Primary database — storms, advisories, tickets, feedback |
| **Redis** | Redis Cloud Free Tier | Cache, dedup set, pub/sub, rate limiter |
| **ChromaDB** | Local / Railway volume | Vector store for RAG (teammates own this) |

### Frontend (Teammates — Provided for context)

| Layer | Technology |
|-------|-----------|
| **Framework** | Next.js 14 (TypeScript, App Router) |
| **Styling** | Tailwind CSS |
| **Charts** | Recharts (Kp sparkline) |
| **WebSocket** | Native WebSocket API |
| **Deploy** | Vercel Free Tier |

### Infrastructure

| Component | Service | Cost |
|-----------|---------|------|
| **Backend Host** | Oracle Cloud Always Free (4 ARM vCPUs, 24GB RAM) | $0 |
| **Frontend Host** | Vercel Free Tier | $0 |
| **Database** | Supabase Free (500MB DB) | $0 |
| **Cache/Queue** | Redis Cloud Free (30MB) | $0 |
| **Email** | SendGrid Free (100/day) | $0 |
| **Container Registry** | Docker Hub (free) | $0 |
| **Source Control** | GitHub (free) | $0 |

### AI/ML (Teammates — Provided for context)

| Component | Technology |
|-----------|-----------|
| **LLM Inference** | Groq — Llama 3.3 70B |
| **Agent Framework** | LangGraph 0.2 |
| **Embeddings** | OpenAI text-embedding-3-small |
| **Vector Store** | ChromaDB |

## Architecture Diagram

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  NOAA    │────▶│ FastAPI  │────▶│Supabase  │
│  SWPC    │     │ Backend  │     │PostgreSQL│
└──────────┘     │          │     └──────────┘
                 │ ┌──────┐ │     ┌──────────┐
┌──────────┐     │ │Redis │ │────▶│RedisCloud│
│  Groq    │────▶│ │Client│ │     │  Free    │
│  LLM     │     │ └──────┘ │     └──────────┘
└──────────┘     │          │     ┌──────────┐
                 │ /ws/strm │────▶│ Frontend │
┌──────────┐     │          │     │ (Vercel) │
│ChromaDB  │◄────│ API End  │     └──────────┘
│(teammate)│     │  points  │
└──────────┘     └──────────┘
```
