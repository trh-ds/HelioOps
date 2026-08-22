# The Pre-Flight Story

How HelioOps went from a Run button that committed you to eighty seconds
blind, to a gate that tells you what is about to happen — and how it got that
wrong the first time and had to be fixed.

This folder is the complete record of one feature: the brief, the problem we
found, what we built, what broke, why the design is the way it is, and what is
still open. It is written twice over — once for someone who has never seen the
codebase, once for someone who will read `backend/preflight.py` next.

---

## The brief

> Extend the MVP with a capability related to showing detail gradually rather
> than all at once. Specifically, detect conflicts early and present them
> before the user commits to an action. The scope should be substantial enough
> for 24-hour work without requiring a full rebuild.

Three requirements hiding in one sentence:

| # | Requirement | Where it is answered |
|---|---|---|
| 1 | Show detail **gradually** | [03](03-what-the-operator-sees.md) — three layers, headline first |
| 2 | Detect conflicts **before the commit** | [05](05-the-conflict-rules.md) — cross-source physics rules |
| 3 | Substantial, but **not a rebuild** | [04](04-how-it-works.md) — one module, one route, one component |

---

## The one-paragraph version

The dashboard's Run button fired the full pipeline immediately: 65–80 seconds,
metered LLM quota spent, rate-limited to one run per storm per thirty seconds.
Every way the system could quietly degrade — replaying canned data instead of
real imagery, falling back to placeholder solar-wind numbers, running with an
empty knowledge base, stalling on an exhausted token budget — was a
`log.warning` the operator only discovered *after* committing. We added
`GET /api/preflight/{storm_id}`: a read-only dry run that predicts which
fallbacks will fire, cross-checks the cached data sources against each other
for physical contradictions, and reports quota and health — then gates every
Run behind a panel that states the single most important consequence in one
sentence, with the evidence folded behind a disclosure triangle. It never
blocks. The first version shipped with its headline capability unreachable and
had to be fixed. That fix is part of the story, not an embarrassment appended
to it.

---

## Read in this order

**If you have five minutes and no context**
1. [The problem we found](01-the-problem.md)
2. [Fundamentals — for a reader with no background](02-fundamentals.md)
3. [What the operator actually sees](03-what-the-operator-sees.md)

**If you are technical**
4. [How it works](04-how-it-works.md)
5. [The conflict rules, and the physics behind each one](05-the-conflict-rules.md)
6. [The read-only invariants](06-the-read-only-invariants.md)

**If you want the honest engineering account**
7. [What went wrong the first time](07-what-went-wrong-first.md)
8. [Design decisions, and the roads not taken](08-design-decisions.md)
9. [How it is tested, and the blind spot the tests had](09-testing.md)

**Reference**
10. [Timeline, commit by commit](10-timeline.md)
11. [Open issues and honest limits](11-open-issues.md)
12. [Glossary](12-glossary.md)

---

## Where the code lives

| Path | What it is |
|---|---|
| `backend/preflight.py` | The whole check — cache prediction, conflict rules, quota, health |
| `backend/app.py` | `GET /api/preflight/{storm_id}`, plus the startup health warm-up |
| `backend/middleware.py` | `peek_rate_limit()` — the non-mutating twin of `check_rate_limit()` |
| `backend/tests/test_preflight.py` | 35 tests across 8 classes |
| `frontend/src/preflight.js` | `gateDecision()` — the pure decision layer |
| `frontend/src/Dashboard.jsx` | `PreflightPanel` and the `requestRun` gate |
| `frontend/src/data.test.mjs` | Node asserts over `gateDecision()` |
| `backend/data/cached/donki/*.json` | The two committed 2024 CME records the rules run against |

---

## Authorship, stated plainly

The feature was implemented by Neal (commit `2ea377a`) and corrected after
review (commit `a18490b`, co-authored with Claude Fable 5). This documentation
pack was written afterwards from a full read of the code, the commits and the
live output — including the parts that are unflattering.
