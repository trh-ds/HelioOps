# How to Deploy the Backend — HelioOps → Hugging Face Spaces

Free CPU Basic: 2 vCPU, 16 GB RAM, no credit card. Runs the unslimmed torch image
as-is. Cost: $0/month.

For the wider picture — frontend, DNS, latency budget, platform comparison — see
[`DEPLOYMENT.md`](./DEPLOYMENT.md). This file is only the backend procedure.

---

## What you need first

- [ ] HF account
- [ ] `GROQ_API_KEY`
- [ ] `.env` confirmed untracked — `git ls-files | grep -c '^\.env$'` must print `0`.
      **A Space repo is public by default. Pushing `.env` leaks your Groq key.**

---

## Step 1 — Create the Space

<https://huggingface.co/new-space>

| Field | Value |
|---|---|
| Owner | your account |
| Space name | `helioops` |
| License | your choice |
| SDK | **Docker** → *Blank* |
| Hardware | CPU basic (free) |
| Visibility | Public (or Private — free tier allows both) |

Your API lands at `https://<user>-helioops.hf.space`.

---

## Step 2 — The two root files (already committed)

Both exist in the repo; nothing to author. Just know why they matter, because HF
builds `Dockerfile` **at the repo root** — `deployment/Dockerfile.backend` is not
picked up (different name, different path). Keep the two in step when you edit either.

- **`Dockerfile`** — three lines are load-bearing, not style:
  - `COPY --chown=user` — ChromaDB opens `chroma.sqlite3` read-write (sqlite WAL).
    Without it UID 1000 cannot write the WAL. See *Troubleshooting → silent RAG failure*.
  - the embedder bake **after** `USER user` — as root it caches to `/root/.cache`,
    unreadable at runtime, costing a silent ~90s re-download on first request.
  - `.dockerignore` keeps `backend/ml/data/` (the synthetic training set and its
    EDA plots), `backend/ml/0*.py`, `backend/tests/`, `frontend/dist` and the
    ~40 MB of source PDFs out. Serving reads `backend/ml/checkpoints/` (470 KB)
    and `backend/data/chroma_db/` (21 MB) and nothing else from those trees.

  Do **not** "fix" permissions with `RUN chown -R` afterwards; that duplicates every
  file into a new layer and bloats the image.

- **`README.md` front matter** — the YAML block at the top *is* the Space config
  (`sdk: docker`, `app_port: 7860`). `app_port` must match the port in the `CMD`.

---

## Step 3 — Set the secrets

Space → **Settings** → *Variables and secrets*. Both are injected as runtime
environment variables.

| Name | Value |
|---|---|
| `GROQ_API_KEY` | your key |
| `HELIOOPS_CORS_ORIGINS` | *optional* — only to add an origin, e.g. a Vercel preview |

`GROQ_API_KEY` is the only one you must set.

**Use exactly these names.**

- `GROQ_API_KEY`, **not** `HELIOOPS_GROQ_API_KEY`. `backend/genai/llm.py` reads
  `os.getenv("GROQ_API_KEY")` directly; the prefixed `settings.GROQ_API_KEY` field is
  always empty and its "not set" warning is spurious.
- `HELIOOPS_CORS_ORIGINS` is parsed as JSON by pydantic-settings (`list[str]`) and
  **replaces** the default list, it does not extend it — so if you set it, include
  every origin, production ones too. The production origins are already defaults in
  `backend/config.py`, so you normally leave this unset. It gates CORS **and** the
  `/ws/stream` origin check — an unlisted origin gets close code 4003, which looks
  like a backend fault rather than a CORS error.
- Do **not** set `HELIOOPS_CHROMA_PERSIST_PATH`. Unset, it resolves to the DB baked
  into the image. A relative value resolves against the repo root; getting that
  wrong makes Chroma *create* an empty DB and every advisory goes ungrounded with
  no error anywhere. Pinned by `backend/tests/test_runtime_paths.py`.

---

## Step 4 — Push

```bash
git remote add space https://huggingface.co/spaces/<user>/helioops
git push space main
```

Authenticate with an HF **access token** (write scope) as the password, not your
account password.

The build takes ~10–15 min — torch dominates. Watch the Space's *Logs → Build* tab.
Subsequent pushes reuse layer cache and are much faster unless
`backend/requirements.txt` changed.

---

## Step 5 — Verify

```bash
API=https://<user>-helioops.hf.space

curl -s $API/health/ready
curl -s $API/api/storms
curl -s -X POST $API/api/detect/2024-10-G4 | head -c 400
```

`/api/detect` returns in **65–80 s** (measured locally, both anchor storms, warm).
The four agents fan out in parallel, so this is one agent's latency plus its
self-check, not four sequential calls — Groq's `gpt-oss-120b` reasoning pass
dominates it. HF's CPU barely matters here; the wall clock is Groq's.
Add 1–3 min on the first request after the Space has slept.

### The check that actually matters

A permissions failure on ChromaDB does not raise — `retrieve_chunks()` catches it and
returns `[]`, and the agents then generate from an empty context. The advisories still
look confident and well-formed. Two ways to prove retrieval is alive:

```bash
# 1. Readiness now covers it. knowledge_base is false unless all five
#    collections hold chunks; the endpoint 503s and reports which layer is down.
curl -s $API/health/ready
# {"status":"ready","checks":{"detection":true,"ml_models":true,
#  "genai_module":true,"knowledge_base":true},"version":"0.1.0"}

# 2. End to end — the field is `sources_cited`, not `citations`.
curl -s -X POST $API/api/detect/2024-10-G4 > out.json
python -c "import json;d=json.load(open('out.json'));print([(a['industry'],len(a['sources_cited'])) for a in d['advisories']])"
# [('aviation', 2), ('grid', 2), ('maritime', 2), ('telecom', 2)]
```

Cited sources are PDF filenames from `backend/data/*/`. All zeros means the RAG layer
is dead and every advisory is ungrounded. Do not demo until this passes.

## Troubleshooting, most likely first

**Advisories have empty `sources_cited` (silent RAG failure).**
`/health/ready` will say `knowledge_base: false`. Two causes, both silent:
- Missing `COPY --chown=user`. UID 1000 can't write `chroma.sqlite3`'s WAL, Chroma
  raises, `retrieve_chunks()` swallows it. Nothing is logged.
- `HELIOOPS_CHROMA_PERSIST_PATH` set to a relative value that does not resolve to
  the baked-in DB. Chroma *creates* whatever path it is given, so every collection
  comes back empty and looks like a working-but-unhelpful KB. Unset the variable.

**First request after a couple of quiet days takes 1–3 minutes.**
Expected. Free Spaces sleep after ~48 h idle; the wake pulls a ~3 GB image and
`_prewarm_embedder()` loads the model. Mitigate by hitting the Space before a demo,
cron-pinging `/health/live` under 48 h, or running the slimming diffs in
`DEPLOYMENT.md` §7.

**Every Groq call fails.** Secret named `HELIOOPS_GROQ_API_KEY` instead of
`GROQ_API_KEY`.

**WebSocket closes immediately with 4003.** The frontend origin isn't in
`HELIOOPS_CORS_ORIGINS`. Preview deployments have their own origin.

**`/api/result/{id}` 404s after a restart.** Expected. `InMemoryResultRepository`
holds results in process memory and Space disk is ephemeral (`/data` needs paid
storage). Re-run `/api/detect`, or move persistence to an HF Dataset repo or Supabase.

**~90 s added to every cold start.** The embedder bake ran as root and cached to an
unreadable path. Confirm the `RUN python -c ...` line sits *after* `USER user` and
`HF_HOME` is set.

**Build fails on an import at startup.** `backend/requirements.txt` is serving-only by
design; `requirements-dev.txt` (pytest, sunpy, optuna, sklearn) must **not** be
installed in the image. If something at import time needs a dev dep, that import
belongs inside a function.

---

## What this deployment does not give you

| Limit | Consequence |
|---|---|
| Sleeps after 48 h idle | 1–3 min cold start on the next request |
| Ephemeral disk | results lost on restart |
| No custom domain on free tier | API stays on `*.hf.space` (fine — only the frontend bundle references it) |
| Groq free-tier TPM | one run = 4 concurrent `gpt-oss-120b` advisories + 4 concurrent `gpt-oss-20b` self-checks; simultaneous demos can throttle |
| Single process, no queue | `/api/detect` is rate-limited to one run per storm per 30 s, in-process |
