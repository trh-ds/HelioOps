# DEPLOYMENT — HelioOps

Target: **frontend on Vercel** at `heliops.dpdns.org`, **backend on Hugging Face Spaces**
(Docker SDK, free CPU Basic). Cost: $0/month.

---

## 0. Topology — what connects to what

```
                    DNS (NS delegation)
heliops.dpdns.org ──────────────────────► Vercel  ──► static Vite SPA (dist/)
                                                          │
                                    VITE_API_URL (baked at build time)
                                                          ▼
                                    https://<user>-helioops.hf.space
                                    ├── POST /api/detect/{storm_id}   (CORS)
                                    ├── GET  /api/storms|result|advisory
                                    └── WS   /ws/stream               (origin-checked)
                                                          │
                                                          ▼
                                                    Groq API (free tier)
```

**DNS does not connect the frontend to the backend.** DNS only points the domain at
Vercel. The frontend→backend link is two things:

1. `VITE_API_URL` inlined into the bundle at build time (Vite inlines `VITE_*` the
   same way Next inlines `NEXT_PUBLIC_*` — a runtime env var does nothing).
2. `HELIOOPS_CORS_ORIGINS` on the Space, which gates both CORS **and** the
   `/ws/stream` origin check (unlisted origin → close code 4003).

Free Spaces have no custom domain, so the API keeps its `*.hf.space` hostname.
That is fine — nobody types it, the bundle does.

---

## 1. Latency budget (against the actual code paths)

| Segment | Cost |
|---|---|
| Static SPA shell from Vercel edge | 20–50 ms |
| **`public/models/earth.glb` first load** | **8.8 MB — 1–3 s on broadband, far worse on mobile** |
| Browser (IN) → hf.space (AWS us-east-1) RTT | ~250–300 ms, +2 RTT TLS on first connect |
| CV stage (stub JSON) | ~1 ms |
| ML stage | ~200 ms first call (lazy `joblib.load`), ~10 ms after |
| Advisory stage — 4 agents **in parallel** | **~65–78 s** |
| Verification stage (deterministic, no LLM) | ~ms |
| **Total `/api/detect`** | **65–80 s, ~99 % Groq** |

Cross-region network is well under 1 % of total. It is not the bottleneck, and neither is host CPU.

> **Corrected 2026-08-22.** This budget previously said 8–15 s. Measured end to end against both
> anchor storms, warm, `/api/detect` takes **65–80 s** — the `gpt-oss-120b` reasoning pass dominates
> and chain-of-thought is billed against `max_tokens`. A pooled Groq key set is the only real lever:
> TPM is metered per `(key, model)`, so each extra key is a full extra budget and cuts wall time
> roughly linearly. It buys throughput, not accuracy.

### The three real latency risks

1. **48 h sleep cold start.** ~3 GB image + `_prewarm_embedder()` on the first
   pipeline call ⇒ 1–3 min for the first request after a sleep. Mitigations:
   (a) run the slimming diffs in §7, (b) hit the Space once before any demo,
   (c) an external cron pinging `/health/live` under 48 h keeps it awake.
2. **Groq free-tier rate limits.** One run = 4 concurrent `gpt-oss-120b` calls plus 4
   concurrent `gpt-oss-20b` self-checks. The two models are separate TPM buckets, which is
   why the self-check is on the smaller one. Two simultaneous users can still trip TPM;
   with all keys saturated the run does not fail, it waits.
   `self_check_hallucination()` swallows the exception and returns
   `"self-check skipped"` — the guardrail turns off with no error surfaced.
3. **Do NOT use a `vercel.json` rewrite** to proxy `/api/*`. It adds a hop, cannot
   carry the WebSocket, and splits REST and WS across two code paths. Call
   `hf.space` directly with CORS.

**Frontend-side, the bottleneck is not the API at all** — it is the 8.8 MB
`earth.glb` that `src/helio-globe.js` loads via `import.meta.env.BASE_URL`. Vercel
edge-caches it, but it dominates first paint and burns Hobby's 100 GB/month at
~11k cold loads. If first-load time matters, Draco-compress the mesh or lazy-load
the globe behind the hero. That is the single highest-leverage latency fix on the
frontend, and it is unrelated to hosting choice.

---

## 2. Prerequisites

- [ ] HF account, Space created (Docker SDK), `GROQ_API_KEY` in hand
- [ ] Vercel account linked to the GitHub repo
- [ ] DigitalPlat FreeDomain panel access for `heliops.dpdns.org`
- [ ] `.env` confirmed untracked (`git ls-files | grep -c '^\.env$'` → `0`).
      **The Space repo is public by default — pushing `.env` leaks the Groq key.**

---

## Phase 1 — Backend on HF Spaces

HF builds a `Dockerfile` **at the repo root**. `deployment/Dockerfile.backend` is
not picked up. Add two root files.

### 1.1 `Dockerfile` (repo root)

```dockerfile
FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONPATH=/home/user/app \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

COPY --chown=user backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
COPY --chown=user backend/ backend/

# Bake the embedder AFTER `USER user`. As root it caches to /root/.cache, which
# UID 1000 cannot read at runtime -> silent ~90s re-download on first request.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

`COPY --chown=user` is **mandatory**, not cosmetic — see §6.1.

### 1.2 `README.md` front matter (repo root)

The YAML block *is* the Space config. Prepend to the existing README:

```yaml
---
title: HelioOps API
emoji: 🌞
colorFrom: orange
colorTo: red
sdk: docker
app_port: 7860
---
```

### 1.3 Space secrets (Settings tab, injected at runtime)

| Name | Value | Why this exact name |
|---|---|---|
| `GROQ_API_KEY` | your key | `genai/llm.py` reads `os.getenv` directly. **Not** `HELIOOPS_GROQ_API_KEY` — the prefixed settings field is the spurious one. |
| `HELIOOPS_CORS_ORIGINS` | `["https://heliops.dpdns.org","https://<project>.vercel.app"]` | pydantic-settings parses `list[str]` as JSON. Gates CORS **and** the WS origin check. Include the `*.vercel.app` preview origin or previews break. |

### 1.4 Push

```bash
git remote add space https://huggingface.co/spaces/<user>/helioops
git push space main
```

Build takes ~10–15 min (torch). Watch the Space's build logs.

### 1.5 Verify before touching the frontend

```bash
API=https://<user>-helioops.hf.space
curl -s $API/health/ready
curl -s $API/api/storms
curl -s -X POST $API/api/detect/2024-10-G4 | head -c 400   # expect 65-80s
```

Then confirm the RAG layer is actually alive — a silent Chroma permission failure
returns advisories that look fine but are ungrounded:

```bash
curl -s -X POST $API/api/detect/2024-10-G4 | grep -c '"citations"'   # must be > 0
```

---

## Phase 2 — DNS

DigitalPlat delegates **nameservers only**; it has no A/CNAME editor.

**Option A — Vercel nameservers (recommended, fewest moving parts).**

1. Vercel → Project → Settings → Domains → add `heliops.dpdns.org`
2. Copy `ns1.vercel-dns.com` / `ns2.vercel-dns.com`
3. Paste into the DigitalPlat panel; wait for propagation
4. Vercel issues the cert automatically

**Option B — Cloudflare nameservers.** Only worth it if you later want
`api.heliops.dpdns.org`, which on a free Space requires a Cloudflare Worker that
rewrites the `Host` header to `<user>-helioops.hf.space`. Then `heliops` is a
DNS-only `CNAME → cname.vercel-dns.com` (Vercel issues the cert) and `api` is
proxied through the Worker. Skip until you need it.

Verify: `dig +short NS heliops.dpdns.org`, then `curl -sI https://heliops.dpdns.org`.

---

## Phase 3 — Frontend on Vercel

`frontend/src/` is currently a **static marketing site** (Home/About/Problem/
Industries, copy hardcoded in `data.js`). It makes **no API calls** and reads no
`VITE_` variables. Phase 3a ships it as-is; 3b is the build work to connect it.

### 3a — Deploy the site as it stands

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite (auto-detected) |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Env var | `VITE_API_URL = https://<user>-helioops.hf.space` |

Hobby tier: 100 GB bandwidth/month, free SSL, custom domain included.
Caveat: Vercel Hobby is non-commercial per their ToS.

### 3b — Actually wire it to the backend (new work)

1. Read the base URL once: `const API = import.meta.env.VITE_API_URL`
2. REST: `POST ${API}/api/detect/${stormId}` — set a client timeout **above 120 s**;
   the happy path is 65–80 s. Note `_pick_key()` waits for TPM budget in an unbounded
   `while True`, so with every key parked the request can stall for minutes with no
   error — a client-side timeout is the only bound that exists today.
3. WS: `new WebSocket(API.replace('https', 'wss') + '/ws/stream')`.
   The server validates `Origin` against `HELIOOPS_CORS_ORIGINS`.
4. Handle the event contract from `stream_full_pipeline`: `pipeline.stage`
   (detection / impact_prediction / adaptation / advisory_generation /
   verification), then a terminal `pipeline.complete`. `advisory_generation`
   re-emits genai's own `pipeline.complete` as a stage event — do not treat that
   one as terminal or the UI stops before verification.
5. **Cold-start UX:** on the first request after a sleep the Space takes 1–3 min.
   Show a "waking the backend" state rather than letting a spinner look hung.

**Changing `VITE_API_URL` requires a rebuild.** It is inlined at build time.

---

## Phase 4 — Post-deploy verification

- [ ] `https://heliops.dpdns.org` serves the SPA over valid TLS
- [ ] `curl $API/health/ready` → ready
- [ ] `POST /api/detect/2024-10-G4` returns in 65–80 s with a non-empty `cv_event`
- [ ] Advisories carry citations (RAG alive — see §1.5)
- [ ] `/ws/stream` connects **from the deployed origin**, not just localhost
- [ ] A wrong-origin WS connect is rejected with code 4003
- [ ] `GET /api/result/2024-10-G4` returns the persisted run
- [ ] Restart the Space; confirm `/api/result` now 404s (expected — §6.2)

---

## 5. Known limits of this deployment

| Limit | Effect | Fix |
|---|---|---|
| Space sleeps after 48 h idle | 1–3 min first request | ping cron, or slim (§7) |
| Ephemeral disk | `InMemoryResultRepository` lost on restart | HF Dataset repo, or Supabase free |
| No custom domain on free Space | API stays on `*.hf.space` | Cloudflare Worker (§2 Option B) or HF Pro |
| Groq free-tier TPM | concurrent demos degrade | stagger, or accept degraded guardrail |
| Single process, no queue | `/api/detect` rate-limited 30 s/storm in-process | fine for demo scale |

---

## 6. Failure modes, ranked by likelihood

**6.1 Chroma permission failure (most likely, and silent).**
`PersistentClient` opens `backend/data/chroma_db/chroma.sqlite3` **read-write**
(sqlite WAL). Without `COPY --chown=user`, UID 1000 cannot write it. Chroma raises,
`retrieve_chunks()` catches and returns `[]`, and all four agents generate from an
empty context. You get confident, well-formed, **ungrounded** advisories and no
error anywhere. Detect it with the citation check in §1.5. Do not fix with
`RUN chown -R` — that duplicates every file into a new layer.

**6.2 Results vanish after a restart.** Expected. Disk is ephemeral; `/data` needs
paid storage. Re-run `/api/detect`.

**6.3 Model re-download on every cold start.** The bake ran as root and cached to an
unreadable `/root/.cache`. Symptom: ~90 s added to the first request. Fix: bake
after `USER user` with `HF_HOME` set (already correct in §1.1).

**6.4 WS closes immediately with 4003.** Deployed origin missing from
`HELIOOPS_CORS_ORIGINS`. Remember the `*.vercel.app` preview origin.

**6.5 Groq calls all fail.** Secret named `HELIOOPS_GROQ_API_KEY` instead of
`GROQ_API_KEY`.

**6.6 (resolved)** An earlier read of the Chroma store showed `telecom_kb` at 0
chunks and `maritime_kb` at 2. The merge in `f967611` brought in the full corpus —
all five collections are now populated (aviation 242, maritime 214, telecom 195,
impact_matrix 166, grid 101; **918 total**). No action needed.

---

## 7. Optional: the slimming diffs

Not required on HF (16 GB RAM), but they cut the cold start from minutes to seconds
and unlock every 512 MB free tier (Northflank, Render) as a fallback host.

1. `sentence-transformers`/torch → ONNX `bge-small` via `fastembed`. Same vectors,
   ~130 MB instead of ~2.5 GB.
2. `chromadb` → a `kb.npz` of 918 × 384 float32 (1.4 MB) + `np.argsort(M @ q)`.
   ~15 lines; keep the `retrieve_chunks()` signature so nothing above it changes.
3. `opencv-python-headless` + `astropy` → `requirements-dev.txt`. The deployed
   container has no FITS (gitignored **and** `.dockerignore`d), so `detect()` always
   takes the stub path. Both imports are already lazy.
4. Pick one of lightgbm/xgboost — checkpoints are lightgbm `.pkl`; xgboost is the
   training path.

Result: ~400 MB image, ~250 MB RSS, ~3 s cold start.
