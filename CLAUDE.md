# CLAUDE.md — how to work in this repo

**Read in this order, and stop when you have what you need. Do not re-explore the tree.**

1. [`AGENTS.md`](AGENTS.md) — project memory: current state, stack, commands, decisions log,
   gotchas, changelog. This is the single source of truth for *what is true today*.
2. The `architecture.md` of the layer you are touching — internals, contracts, failure modes.
3. [`README.md`](README.md) — the outside view: what the product does and the API surface.

Anything else under `docs/` is untracked reference material (history, Q&A, deep dives,
deployment runbooks). It is local-only and may be stale — never cite it as current truth,
and never add a new doc there expecting it to be committed.

## The four docs that are tracked

| Path | Purpose |
|---|---|
| `README.md` | product + pipeline overview, quickstart, API surface, maturity |
| `AGENTS.md` | project memory — the state of the repo *right now* |
| `CLAUDE.md` | this file — how to navigate and what not to break |
| `<layer>/architecture.md` | one per layer: `backend/`, `backend/cv/`, `backend/ml/`, `backend/genai/`, `backend/embeddings/`, `frontend/`, `deployment/` |

If you change behaviour, update the layer's `architecture.md` and AGENTS.md in the same pass.
Patch sections with an edit; never rewrite a whole doc.

## Non-negotiables

- **Paths**: import from `backend.paths`. Never resolve from cwd. Relative
  `HELIOOPS_CHROMA_PERSIST_PATH` values resolve against the **repo root**.
- **Layer boundary**: `backend/pipeline.py` reaches `cv`/`ml`/`genai` only through the four
  adapter singletons it owns. Nothing under `adapters/` may import `backend.pipeline` at
  module level.
- **One Groq call site**: `backend.genai.llm.complete_json`. Do not add an LLM client.
- **One Chroma client**: `backend.embeddings.collections.get_client()`. Two clients on the
  same directory corrupt reads under concurrency.
- **CV imports use the full stage path** (`backend.cv.storm_event_generator.detect`).
  No re-export shims.
- **Fallbacks log at WARNING and continue.** Only genuinely unrecoverable input raises.
  But a *retrieval* failure must be loud — a silent one ships an ungrounded advisory.
- **Severity clamps upward only.** The NOAA matrix in `genai/impact_router.py` is the floor.
- **ASCII in argparse help and `print()`** — the Windows console is cp1252 and `→`/`—` raise.
- Tests are plain pytest classes; the only fixtures are `tmp_path` and `unittest.mock.patch`.

## Before you claim it works

```bash
pytest backend/tests -q                  # 284 tests
ruff check backend/ --ignore=E501,F403,E402
cd frontend && npm test
```

`test_api_endpoints.py::test_valid_storm_id_returns_200_or_500_or_429` hits the **real** Groq
API — it is the only live-network test, and a saturated quota drags the suite to 9–12 min.
`test_retrieval.py` flakes ~1 full-suite run in 3 on a chromadb internal error; it passes
standalone and is not your change.

## Known-false assumptions to avoid re-deriving

- A fresh clone has **no cached FITS/PNGs** — `detect()` replays the committed stub.
- The advisory field is `sources_cited`, not `citations`.
- `/health/ready` returns **503 with the same JSON body** when degraded; parse it either way.
- `check_rate_limit()` mutates; read-only paths use `peek_rate_limit()`.
- HF Spaces builds the **root** `Dockerfile`, not `deployment/Dockerfile.backend`.
- The frontend API base is `VITE_API_URL`, inlined at build time.
