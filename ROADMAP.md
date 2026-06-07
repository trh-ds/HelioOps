# HelioOps

AI-native space weather intelligence platform. Translates real-time NOAA solar alerts into industry-specific operational advisories for aviation, power grid, telecom, and maritime companies.

## Overview

HelioOps ingests public NOAA SWPC data every 5 minutes, classifies storm events, routes impact assessments to domain-specific LLM agents, and delivers actionable advisories to operations teams in under 3 minutes.

**Current Phase**: Phase 0 — Hackathon MVP (48 hours)

**Team Roles**:
- **Web/Infra (Us)**: FastAPI backend, PostgreSQL, Redis, WebSockets, REST APIs, CRM, notifications, Docker, deployment
- **ML/AI (Teammates)**: NOAA poller, LangGraph agent pipeline, LLM inference (Groq), ChromaDB RAG, storm classification
- **Frontend (Teammates)**: Next.js dashboard, WebSocket client, UI components

---

## Wave 1 — Architecture (BLOCKING — DONE)

- [x] ROADMAP.md
- [x] API_CONTRACTS.md
- [x] DATA_MODELS.md
- [x] TECH_STACK.md
- [x] ENV.md

---

## Wave 2 — Parallel Build

### Sub-Agent A: Backend API & Infrastructure
**Scope**: FastAPI app, REST endpoints, WebSockets, API key auth, CRM tickets, notification service, caching layer, rate limiting, structured logging, health checks

### Sub-Agent B: DevOps & Scaling
**Scope**: Dockerfile, docker-compose, Docker Compose for Redis, Docker Compose for local development, CI/CD pipeline scaffolding, deployment configuration for Oracle Cloud / Railway

### Sub-Agent C: AI Pipeline Interfaces
**Scope**: NOAA poller skeleton, event ingestion hooks, WebSocket event publishing helpers, ChromaDB integration stubs, Groq client stub — clear interfaces for teammates to fill

| Sub-Agent | Assignment | Status |
|-----------|-----------|--------|
| backend-api | FastAPI REST + WS + Auth + CRM + Notifications | PENDING |
| devops | Docker + CI/CD + Deployment Config | PENDING |
| ai-pipeline | Skeleton interfaces for teammates | PENDING |

---

## Wave 3 — Verification

- [ ] Start services locally
- [ ] Run three-tier test protocol
- [ ] VERIFICATION_REPORT.md
- [ ] Fix CRITICALs

---

## Wave 4 — DevOps

- [ ] Dockerfile for backend (multi-stage)
- [ ] docker-compose.yml (Redis + backend)
- [ ] docker-compose.prod.yml
- [ ] CI/CD pipeline
- [ ] Deployment README

---

## Known Unknowns

- Exact Supabase region / connection string
- Groq API key (teammate provides)
- Oracle Cloud instance setup details
- Frontend deployment URL (Vercel/other)
- SendGrid API key (for production notifications)

## Out of Scope

- NOAA poller trigger logic (teammates)
- LangGraph agent graph definition (teammates)
- LLM prompt engineering (teammates)
- ChromaDB knowledge base population (teammates)
- Next.js frontend implementation (teammates — but we provide WebSocket + API contracts)
- Fine-tuning / custom models
- Phase 2+ features (multi-tenant, white-label, SMS)
