# Environment Variables

## Backend (.env)

```
# ─── Required ──────────────────────────────────────────────

# PostgreSQL (Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:password@db.project-ref.supabase.co:5432/postgres

# Redis (Redis Cloud Free Tier)
REDIS_URL=redis://default:password@redis-12345.c300.us-east1-4.gce.cloud.redislabs.com:6379

# ─── API Keys ──────────────────────────────────────────────

# Default admin API key (SHA-256 hash seeded in migration)
# Generate: echo -n "sk_heliops_dev_key_here" | sha256sum
API_KEY_ADMIN_HASH=dev_admin_key_hash_placeholder

# Teammate provides these:
GROQ_API_KEY=gsk_your_groq_key_here
OPENAI_API_KEY=sk-your-openai-key-for-embeddings

# ─── Notifications (Mocked — Optional) ─────────────────────

SENDGRID_API_KEY=SG.your_sendgrid_key_here
SENDGRID_FROM_EMAIL=heliops@zylonlabs.com

SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_ALERTS_CHANNEL=#heliops-alerts

# ─── Infrastructure ────────────────────────────────────────

# FastAPI
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info

# Sentry (optional)
SENTRY_DSN=

# CORS — comma-separated origins
CORS_ORIGINS=http://localhost:3000,https://heliops.vercel.app

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_AUTH_PER_MINUTE=10
```

## Backend (.env.example — safe to commit)

```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db
REDIS_URL=redis://default:password@host:6379

API_KEY_ADMIN_HASH=changeme
GROQ_API_KEY=
OPENAI_API_KEY=

SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
SLACK_BOT_TOKEN=
SLACK_ALERTS_CHANNEL=

HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info
SENTRY_DSN=
CORS_ORIGINS=http://localhost:3000
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_AUTH_PER_MINUTE=10
```

## Frontend (Teammates — for reference)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_API_KEY=sk_heliops_dev_key_here
```

## Notes

- `DATABASE_URL` uses `+asyncpg` driver for async SQLAlchemy
- `REDIS_URL` format: `redis://[[username]:[password]]@host:port[/db]`
- `API_KEY_ADMIN_HASH` is the SHA-256 of the raw admin key — never store raw keys
- SendGrid, Slack, Sentry are optional — system runs with mocks if absent
- CORS origins must include both frontend dev URL and production URL
