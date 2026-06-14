# What We Built & Why

## The Problem

HelioOps was a working app, but it was built like a hackathon project. If the server crashed, nobody would know. If we wanted to add a database, we'd have to rewrite half the code. If we wanted to deploy it to the cloud, there was no way to do it. No tests could run automatically, no logs told you what went wrong, and there was no way to monitor if things were healthy.

## What We Did

### 1. Professional Logging

**What:** Replaced print-style logging with structured JSON logging using `structlog`.

**Why:** When something breaks at 2am, you need to search logs by storm ID, error type, or timestamp. JSON logs let you do that instantly. Plain text logs don't.

**Impact:** Every request now logs exactly what happened, when, and with what data. Debugging time goes from hours to minutes.

---

### 2. Health Checks & Metrics

**What:** Added four new endpoints:
- `/health` — "Is the server running?" (used by load balancers)
- `/health/ready` — "Are all dependencies working?" (checks ML models, detection, GenAI)
- `/health/live` — "Is the process alive?" (used by Kubernetes)
- `/metrics` — "How many requests? How fast? Any errors?" (Prometheus format)

**Why:** Without these, Kubernetes can't tell if your app is actually working or just sitting there frozen. Monitoring systems can't alert you when things slow down.

**Impact:** Automatic crash recovery (Kubernetes restarts unhealthy pods), real-time dashboards on request counts and latency, alerts when error rates spike.

---

### 3. Hexagonal Architecture (Ports & Adapters)

**What:** Split the backend into abstract interfaces ("ports") and concrete implementations ("adapters"). The core pipeline code now talks to interfaces, not directly to `cv.detect` or `ML_after_CV.inference`.

**Why:** If we want to swap the ML model for a different one, add a database, or mock things for testing, we just write a new adapter. No need to touch the pipeline code.

**Impact:** Adding a Postgres database later means writing one adapter class (~50 lines). Swapping the LLM provider means one adapter change. Testing becomes trivial — mock adapters instead of calling real APIs.

---

### 4. Environment Configuration

**What:** Created `backend/config.py` using Pydantic BaseSettings. All settings (port, log level, API keys, model paths) now come from environment variables with sensible defaults.

**Why:** Before, settings were hardcoded or scattered across files. In production, you need to change the port, reduce logging, or rotate API keys without changing code.

**Impact:** One `.env.example` file documents every setting. Deploying to staging vs production is just changing env vars — no code changes.

---

### 5. Docker Containers

**What:** Two Dockerfiles — one for the Python backend, one for the Next.js frontend. Plus a `docker-compose.yml` to run them together locally.

**Why:** "It works on my machine" is not a deployment strategy. Containers guarantee the app runs the same everywhere — dev laptop, staging server, production cloud.

**Impact:** Anyone can run `docker compose up` and have the entire app running in 60 seconds. No Python version conflicts, no missing dependencies, no "install these 15 things first."

---

### 6. CI Pipeline (GitHub Actions)

**What:** `.github/workflows/ci.yml` runs automatically on every push and PR: lint → test → build Docker images.

**Why:** Before, there was no automated testing. A bad commit could break production. Now, every PR is tested before it can be merged.

**Impact:** Bugs are caught in CI, not in production. No more "works on my machine."

---

### 7. Kubernetes Manifests

**What:** Complete deployment configs in `k8s/base/` — Deployment, Service, ConfigMap, Ingress, and ServiceMonitor for both backend and frontend.

**Why:** Kubernetes needs exact instructions on how many replicas to run, how much CPU/memory to give each, how to check health, and how to route traffic.

**Impact:** Deploy to any Kubernetes cluster with `kubectl apply -k k8s/`. Auto-scaling, auto-restart on crashes, and zero-downtime deployments come free.

---

### 8. Terraform Infrastructure

**What:** `infra/modules/` defines reusable VPC and EKS cluster modules. `infra/environments/` has staging and production configs.

**Why:** Creating cloud resources manually through a web console is error-prone and unrepeatable. Terraform makes infrastructure code — version controlled, reviewable, and repeatable.

**Impact:** Spin up an entire AWS cluster with `terraform apply`. Tear it down just as fast. No more "who created this instance?"

---

### 9. ArgoCD GitOps

**What:** `argocd/` contains Application manifests that automatically sync Kubernetes to whatever is in the Git repo.

**Why:** Without GitOps, deploying means someone runs `kubectl apply` manually. With ArgoCD, pushing to `main` automatically deploys to staging, and production deploys are reviewed and approved through Git.

**Impact:** Every deployment is tracked in Git. Rollback is `git revert`. No SSH into production servers.

---

### 10. Runbooks

**What:** Four operational playbooks in `runbooks/` — what to do when errors spike, when latency increases, when detection fails, and when the LLM provider goes down.

**Why:** When something breaks at 3am, you don't want to figure it out from scratch. Runbooks give step-by-step instructions: check this, run that command, escalate here.

**Impact:** Mean time to recovery drops from "we'll figure it out" to "follow the runbook."

---

### 11. Chaos Engineering

**What:** Three Chaos Mesh configs in `chaos/` — inject network latency, kill random pods, stress CPU. All run only in staging on schedules (weekly, every 72h, every 2 weeks).

**Why:** You don't know if your system handles failure until it actually fails. Chaos engineering safely breaks things in staging so you find weaknesses before they hit production.

**Impact:** Confidence that the system survives real outages. No surprises in production.

---

## Bottom Line

We turned HelioOps from "a project that runs on a laptop" into "a system that runs in production at scale." Every change follows the same principle: **make the system observable, resilient, and easy to change.**