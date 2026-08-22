# 10 — Timeline, commit by commit

*One afternoon. 2026-08-22, IST.*

---

## The sequence

| Time | Commit | What happened |
|---|---|---|
| 15:47 | `5ab726e` | **The plan.** 155 lines: schema, findings catalogue, the four conflict rules with thresholds, and the read-only constraint identified *before* any code was written. |
| 16:06 | `2ea377a` | **Version one ships.** `backend/preflight.py` (~317 lines), the route, `peek_rate_limit()`, the Dashboard gate. 270 tests, 25 new. Verified live. |
| ~16:10 | — | **Review.** Clone-state check: what does this actually return on a fresh checkout? Answer: the same four "cache missing" findings, for both storms, forever. |
| 16:53 | `a18490b` | **The fix.** DONKI caches committed, stale-epoch rules, stub-replay demotion, the false docstring corrected and the 9.7s behind it removed, progressive disclosure rebuilt, `gateDecision()` extracted. 284 tests, 35 in `test_preflight`. |
| 17:42 | `6e040e5` | The plan file is rewritten into the *next* block of work. The pre-flight task is closed. |

Total elapsed from plan to corrected feature: **66 minutes.**

---

## 15:47 — The plan (`5ab726e`)

Worth reading in full, because the three hardest facts about the feature were
identified before any code existed:

> **Load-bearing rule: stat the cache file first, only parse when it exists** —
> the clients are cache-first-then-NETWORK and `fetch_l1_wind` mkdirs on entry.

> (`check_rate_limit` at middleware.py:67 mutates on read — preflight must never
> call it.)

> Never probe the Groq API itself — that burns the quota preflight protects.

All three of the [read-only invariants](06-the-read-only-invariants.md) are
there, correctly, in the plan. The engineering that mattered most was done
before the first line was typed.

The plan also carried an explicit scope decision:

> Scope decision (user-confirmed): **preflight only** — no provenance threading
> through `detect()`/`StormEvent`; that is the natural follow-up, deferred.

And a correct constraint about what must not change:

> No new deps, no new WS events (`TestStreamEventContract` pins
> "pipeline.complete is last").

What the plan did **not** anticipate: that the caches it depended on were not
committed, and that two of the three sources could never hold historical data at
all.

## 16:06 — Version one (`2ea377a`)

317 lines of `preflight.py`, 200 lines of tests, 119 lines of Dashboard changes.

Delivered:
- `GET /api/preflight/{storm_id}` with the full findings schema
- Cache-existence prediction for all four sources
- Four cross-source conflict rules
- `peek_rate_limit()`
- Quota and health findings
- The gate: preflight → panel → Run / Run anyway / Cancel
- Incidentally fixed a pre-existing bug where a degraded `503` from
  `/health/ready` rendered as "unreachable" with no check pills, because
  `getHealth` was routed through the throwing `json()` helper

The commit message ends by handing verification back:

> Remaining manual step for you: run backend + `npm run dev` and click through
> Run → panel → Cancel / Run anyway to see it in the browser.

## ~16:10 — The review

The question that produced the fix was not "is the code correct" — it was
**"what does this return on a machine that has just cloned the repository?"**

The answer: four `info` findings saying caches were missing, identical for both
storms, with every conflict rule skipped because its inputs were `None`.

Investigating why the caches could not simply be committed produced the root
cause — NOAA's `rtsw` and `xrays` endpoints are real-time only and take no date
parameter — which in turn explained a pre-existing mystery nobody had connected:
the flare classifier reporting C-class for two X-class storms.

## 16:53 — The fix (`a18490b`)

`+1581 / -42` across 11 files. Six changes, in order of how much they mattered:

1. **DONKI caches committed** (44 KB, 20 + 24 real 2024 records) and the new
   `stub_donki_speed_mismatch` rule. G5 fires at 65% drift; G4 stays silent at
   12%. The two storms now differ.
2. **`*_cache_stale_epoch` rules**, and `l1/` + `xrs/` gitignored with the
   reasoning and regeneration commands in the ignore file.
3. **Conflict demotion under stub replay** — `warn` → `info` with an appended
   explanation.
4. **The "never writes" docstring was false.** Fixed the claim and the ~9.7s of
   Chroma-rewriting behaviour behind it. TTL cache + lifespan warm-up; live first
   click 0.31s.
5. **Progressive disclosure rebuilt** — headline sentence instead of a warning
   count; one button label instead of two that did the same thing.
6. **`gateDecision()` extracted** to `frontend/src/preflight.js`, asserted in the
   node runner the repo already had.

## What the shape of this timeline says

Two commits, 47 minutes apart, and the second is larger than the first.

That is not a sign the first was careless — it was planned well, tested, and
verified live. It is a sign that **the review asked a different question than
the tests did.** The tests asked "does this compute correctly?". The review
asked "does this ever run?".

Both questions are necessary. Only one of them was automated.

---

Next: [Open issues](11-open-issues.md).
