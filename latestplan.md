# HelioOps — next block of work

Seven items, ordered so each one unblocks the next. Phases 1-3 are cleanup and
infrastructure; 4-6 are the new operator features; 7 closes the loop on docs.

Decisions taken with the owner (2026-08-22): backend goes to **HF Spaces**;
docs collapse to **5 files**; critical alerts go out over **SMTP from the
heliops.dpdns.org domain**.

---

## Phase 1 — Make CI green (~1h)

**CI has been red on every push since 2026-08-22** (runs 32562493728 through
32570304422). Only the `Lint` step fails, and because it fails first the backend
`Test` step and the whole `images` job have not run since. Nobody has seen a CI
test result in seven commits.

Root cause is version drift, not code: `backend/requirements-dev.txt` pins
`ruff>=0.4` and there is **no ruff config anywhere in the repo**, so CI installs
whatever ruff is newest and inherits its default rule set. That set has widened
(I001 44x, UP045 53x, BLE001 42x, plus RUF/UP/S110/SIM — 195 findings). Local
ruff 0.14.10 reports `All checks passed!` on the same tree. Verified: adding an
explicit select reproduces the clean result on any version.

1. New `ruff.toml` at the repo root — the fix that survives the next ruff release:
   ```toml
   [lint]
   select = ["E4", "E7", "E9", "F"]   # ruff's classic default, stated explicitly
   ignore = ["E501", "F403", "E402"]
   ```
2. `backend/requirements-dev.txt` — `ruff>=0.4` becomes `ruff==0.14.10`, so local
   and CI run the identical binary. Belt and braces; the config is the real fix.
3. `.github/workflows/ci.yml` — Lint step drops the flags: `ruff check backend/`.
4. **The Test step is untested.** Once lint passes it runs for the first time in
   seven commits, and `test_api_endpoints.py::test_valid_storm_id_returns_200_or_500_or_429`
   fires the REAL pipeline at the REAL Groq API. With CI's placeholder
   `GROQ_API_KEY: test-key` that is the 9-12 min drag already recorded in
   AGENTS.md, and `_pick_key()`'s unbounded `while True` can park it indefinitely.
   Guard it at the source:
   ```python
   @pytest.mark.skipif(
       not os.getenv("GROQ_API_KEY", "").startswith("gsk_"),
       reason="live Groq call - needs a real key",
   )
   ```
   One decorator, no pytest.ini, no marker registration.
5. Bump the deprecated action runtimes while the file is open: `checkout@v5`,
   `setup-python@v6`, `setup-node@v5` (annotation on every run today).

**Verify:** `ruff check backend/` clean locally, `pytest backend/tests -q` green,
then push and `gh run watch` until all three jobs — including `images`, which
builds the root Dockerfile HF Spaces actually uses — go green. This phase is not
done until a run is green end to end, not until lint passes.

---

## Phase 2 — Backend on HF Spaces (~2h, mostly waiting on builds)

Groundwork is already committed: root `Dockerfile`, README front matter,
production CORS origins as defaults in `config.py`, `/health/ready` covering the
KB. What is left is the push and the wiring.

1. Create the Space (Docker SDK, free CPU tier — 16 GB, which the
   torch + chroma image needs; Render's 512 MB free tier would OOM).
2. Secrets: `GROQ_API_KEY` (or `GROQ_API_KEYS`), plus any `HELIOOPS_*` overrides.
   Phase 6 adds the SMTP secrets here too.
3. `git push` the Space remote; watch the build. `.dockerignore` already excludes
   `backend/ml/0*.py` — do not rename those files (the exclude is a numeric glob).
4. Verify against the live URL: `/health` 200, `/health/ready` reporting
   `knowledge_base: true` (an empty Chroma is the failure that has shipped
   before and it is silent), `/api/storms`, `/api/preflight/2024-10-G4`, then one
   full `/api/detect/2024-10-G4` measured end to end.
5. Point the frontend at it: set `VITE_API_URL` in the Vercel project's build env
   and redeploy. It is inlined at **build** time — setting it as a runtime var
   does nothing, and leaving it empty makes Vercel's catch-all rewrite answer
   `/api/*` with index.html and a 200.
6. Add the real Space origin to the CORS defaults in `config.py`. The env var
   REPLACES the list rather than extending it, so a partial secret silently 403s
   the WebSocket and reads as a backend fault.
7. Confirm `/ws/stream` works cross-origin from the deployed frontend — REST
   passing does not imply the WebSocket does.

---

## Phase 3 — Collapse 16 markdown files to 5 (~4h)

Today: 16 tracked `.md`, ~7,900 lines, with README / context.md / PRODUCT_BRIEF /
TECHNICAL_DEEP_DIVE all re-telling the same architecture at four different
lengths, and two Q&A docs that overlap.

**Nothing is deleted before its surviving facts are folded into a keeper.**

Keep (5):

| file | becomes |
|---|---|
| `README.md` | entry point — unchanged role, refreshed in Phase 7 |
| `AGENTS.md` | project memory (protocol) — absorbs the two historical snapshots as Archived Summary paragraphs |
| `docs/ARCHITECTURE.md` | new: `TECHNICAL_DEEP_DIVE.md` + `backend/genai/ARCHITECTURE.md` + the open-work sections of `IMPROVEMENTS.md` |
| `docs/QNA.md` | new: `docs/qna.md` + `docs/CV_ML_QNA.md`, deduped, one glossary |
| `docs/DEPLOYMENT.md` | absorbs `HOW_TO_DEPLOY_BACKEND.md`, rewritten around the URL that actually exists after Phase 2 |

Delete after folding: `context.md`, `docs/PRODUCT_BRIEF.md`,
`docs/TECHNICAL_DEEP_DIVE.md`, `docs/CV_ML_QNA.md`, `docs/qna.md`,
`docs/HOW_TO_DEPLOY_BACKEND.md`, `backend/genai/ARCHITECTURE.md`,
`backend/genai/IMPROVEMENTS.md`, `REFACTOR_MAP.md`, `HELIOOPS_TEST_REPORT.md`,
and this file once executed.

`REFACTOR_MAP.md` and `HELIOOPS_TEST_REPORT.md` are a change record and a dated
snapshot — editing them to match today destroys their only value, so each gets a
one-paragraph summary in `AGENTS.md` and the full text stays in git history.

Keep `backend/data/{maritime,telecom}/SOURCES.md` where they are: those document
the PDFs they sit next to, which is the right place for provenance.

Also drop the stray untracked repo-root `data/` directory — a leftover of the
cwd-relative path bug, since fixed (everything resolves from `backend.paths`).
Confirm with a grep for `"data/` outside `backend/` before removing.

---

## Phase 4 — Citations that open the source at the cited spot (~6h)

Today `source_ref` is a bare filename in a `<span>` (`Dashboard.jsx:147`). The
blocker is upstream: `chunk_document()` (`chunker.py:86-97`) does
`"\n\n".join(pages)` before chunking, so **the page number is destroyed at ingest
time**. No amount of frontend work recovers it.

1. **`backend/embeddings/chunker.py`** — chunk page by page and carry the number:
   ```python
   chunks = []
   for n, page in enumerate(load_pdf(path), 1):
       for c in chunk_text(page, chunk_size, overlap, source=source):
           c["page"] = n
           chunks.append(c)
   ```
   Chunks stop spanning page boundaries. That is a fair trade — a citation that
   straddles two pages cannot point at one anyway.
2. Re-run `python -m backend.embeddings.rebuild_kb` (~2 min) and re-verify the
   918-chunk corpus. Chunk count will shift; update it wherever it is quoted.
3. **`backend/genai/retriever.py:112`** — chunk header gains the page, so the
   model cites what it read: `[CHUNK: id | Source: nat_doc_007_2025.pdf p.42 | ...]`.
4. **`backend/genai/guardrails.py`** — `citation_matches()` must treat
   `file.pdf p.42` as naming `file.pdf`. Its word-overlap fallback probably
   already does, but that is an accident, not a guarantee: strip a trailing
   ` p.<n>` before matching and pin it with a test. Getting this wrong flags
   every advisory `CITATION_GAP` and drags confidence down through
   `CITATION_PENALTY`.
5. **`backend/app.py`** — `GET /api/kb/source/{filename}`, `FileResponse` with
   `Content-Disposition: inline`. Resolve against an allowlist built by globbing
   `DATA_DIR` at startup, not by joining user input onto a path — same class of
   boundary as `validate_storm_id`. Anything not in the set is a 404.
6. **Frontend** — `act-cite` becomes an anchor:
   `${BASE}/api/kb/source/${file}#page=${n}`, `target="_blank"`. Chrome's and
   Firefox's built-in PDF viewers honour `#page=N` natively; no PDF.js, no new
   dependency. `.txt` sources get the same link minus the fragment. Missing page
   falls back to page 1 — still the right document.
7. **UX** — the anchor keeps the existing `.act-cite` styling plus an underline
   on hover and a title of `open <file> at page <n>`. No new layout, no modal,
   no in-page viewer to maintain.

**Tests:** path traversal 400/404s; a real filename 200s with the right
content-type; `citation_matches("x.pdf p.4", "x.pdf")` is True.

---

## Phase 5 — Per-agent operator chatbot (~8h)

"Specialized in each one" is the requirement, so the chat is **scoped to one
agent and its advisory**, not a global assistant that has to guess context.

**Placement.** Inside `AdvisoryCard`, a collapsed `<details>` at the foot of the
card: *"Ask the aviation agent about this advisory"*. Reasons: it inherits the
industry and the advisory the operator is looking at with no extra UI; it reuses
the `<details>` idiom the card already uses twice (generation notes, preflight
findings); and it adds nothing to the two-column grid, which is already dense.
A floating widget would have to ask "which agent?" as its first question — the
worst possible first question. Before any run, one storm-scoped ask box sits
under the ADVISORIES empty state so the console is not dead on arrival.

**Backend** — `backend/genai/ask.py` (~60 lines) + `backend/genai/prompts/ask.py`:

```
POST /api/ask  {industry, question, advisory_id?}
  -> retrieve_chunks(INDUSTRY_KB_MAP[industry], question, RAG_TOP_K)   # existing
  -> repository.get_advisory(advisory_id) for the advisory context     # existing
  -> complete_json(ASK_SYSTEM, ..., model=GROQ_CHECKER_MODEL)          # existing
  -> {"answer": str, "sources_cited": [str]}
```

- Runs on `GROQ_CHECKER_MODEL` (gpt-oss-20b). Groq meters TPM per (key, model),
  so chat draws on a **different bucket** and can never starve an advisory run.
  This is the whole reason not to reuse `GROQ_MODEL`.
- Rate limit: a second dict beside `_pipeline_calls` in `middleware.py`, ~5s,
  keyed per client. An operator holding down send should not burn the quota the
  pipeline needs.
- Answers cite sources, so they render through the Phase 4 link component and
  the operator can open the page the answer came from. Do Phase 4 first.
- The prompt must permit "I don't know" — an operator asking a question outside
  the KB deserves that answer, not a confident invention. Same posture as the
  rest of the guardrail layer.

**Frontend** — `ask()` in `api.js`, an `<AskBox>` component (~60 lines): textarea,
send button, answer with citation links, thinking state, error line. Enter sends,
Shift+Enter newlines. History is per-card and in-memory only; no persistence.

**Tests:** unknown industry 400s; a mocked `complete_json` returns the parsed
shape; the rate limiter rejects the second call inside the window.

---

## Phase 6 — Email on critical findings (~4h)

Note on tooling: nodemailer is a Node library and this backend is Python, so it
would mean standing up a second runtime to send an email. Python's stdlib
`smtplib` + `email.message` is the same twenty lines with nothing added. The
part of your setup that actually matters is the **domain** — heliops.dpdns.org
gives the alert a real `From:` and, with SPF/DKIM records at the relay, one that
does not land in spam. That works identically from Python.

1. **Relay** — Resend (free 3k/mo, SMTP endpoint, DKIM is three DNS records) or
   Brevo (300/day). Only env values differ between them; no code change.
2. **DNS on heliops.dpdns.org** — SPF TXT, DKIM CNAMEs from the relay, optional
   DMARC. Sender: `alerts@heliops.dpdns.org`.
3. **`backend/alerts.py`** (~40 lines) — `send_critical_alert(storm_id, result)`:
   fires when any advisory is `CRITICAL` **or** carries `requires_human`.
   Subject: `[HelioOps] CRITICAL - 2024-10-G4 - grid, aviation`. Body: severity,
   Kp, the action items, and a link back to the console.
4. **Config** — `HELIOOPS_SMTP_HOST/PORT/USER/PASSWORD`, `HELIOOPS_ALERT_FROM`,
   `HELIOOPS_ALERT_TO`. Unset means **no-op with a debug log**: fresh clones and
   CI must never attempt an outbound connection.
5. **Wiring** — called from `backend/pipeline.py` once the result is assembled,
   inside `asyncio.to_thread` (smtplib blocks) and wrapped so a mail failure is
   logged and never fails the run. A dead SMTP host must not break the pipeline.
6. **Dedup** — no re-send for the same storm inside 15 min; the `_pipeline_calls`
   timestamp-dict idiom already in `middleware.py` covers it.
7. **UX** — the console shows a `mail sent` / `mail not configured` pill next to
   the verifier pills, so the operator can see whether the alert went out
   instead of assuming. Silent alerting is worse than no alerting.

**Tests:** unset env sends nothing and opens no socket (assert `smtplib.SMTP` is
never constructed); a mocked SMTP gets the right recipients and subject; a
non-critical result sends nothing; an SMTP exception does not propagate.

---

## Phase 7 — README (~2h)

Last, so it describes what is actually there. Updates: the live Space URL and
the deployed console link; the new endpoints (`/api/ask`, `/api/kb/source/...`);
the chatbot and clickable citations in the feature list; the alert email and its
env vars; the doc map pointing at the 5 surviving files; corrected chunk count
after the Phase 4 re-ingest; a green CI badge.

---

## Files touched

```
new:      ruff.toml
          backend/alerts.py, backend/genai/ask.py, backend/genai/prompts/ask.py
          backend/tests/test_alerts.py, backend/tests/test_ask.py
          docs/ARCHITECTURE.md, docs/QNA.md
          frontend/src/AskBox.jsx
edit:     .github/workflows/ci.yml, backend/requirements-dev.txt
          backend/app.py, backend/pipeline.py, backend/config.py, backend/middleware.py
          backend/embeddings/chunker.py, backend/genai/retriever.py, backend/genai/guardrails.py
          backend/tests/test_api_endpoints.py
          frontend/src/{api.js,Dashboard.jsx,dashboard.css}
          .env.example, README.md, AGENTS.md
delete:   context.md, REFACTOR_MAP.md, HELIOOPS_TEST_REPORT.md, latestplan.md
          docs/{PRODUCT_BRIEF,TECHNICAL_DEEP_DIVE,CV_ML_QNA,qna,HOW_TO_DEPLOY_BACKEND}.md
          backend/genai/{ARCHITECTURE,IMPROVEMENTS}.md
          repo-root data/ (untracked leftover)
```

## Risks

- **Phase 1 is the only one that can be verified today.** Everything after it is
  gated on a CI run nobody has seen since 2026-08-22 — the Test step may well
  surface something beyond the live-Groq test. Do not batch phase 1 with anything.
- **Phase 4 re-ingests the KB.** If page-per-chunk degrades retrieval quality,
  advisory grounding drops everywhere. Compare `compute_context_quality` on both
  storms before and after; keep the old chroma_db until the numbers match.
- **Phase 4's citation matcher** is the one change that can silently flag every
  advisory. Test it before touching the frontend.
- **Phases 5 and 6 both spend Groq/SMTP budget from inside the request path.**
  Both must degrade to a logged no-op, never to a failed run.
- `test_retrieval.py` flakes ~1 full-suite run in 3 on a chromadb internal error.
  Pre-existing; do not read it as a regression from any of this work.

## Deferred

- Streaming the chatbot answer token by token — the 20b model answers in a few
  seconds and a spinner covers it. Add it if the wait reads as a hang.
- Persisting chat history to Supabase. In-memory per card is enough for a
  console session; nothing here is a system of record.
- Slack/webhook alerts alongside email. Same trigger point, ten more lines, and
  worth it only once someone asks for a channel.
