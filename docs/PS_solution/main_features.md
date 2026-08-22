# HelioOps — The Round 2 Solution

**FAR AWAY 2026 · Round 2 · Challenge #1001 — Progressive Disclosure: Conflict Check**
**Team Fantastic 4 (U9NWQ583)**

> Extend the MVP with a capability related to showing detail gradually rather than all at
> once. Specifically, detect conflicts early and present them before the user commits to
> an action. The scope should be substantial enough for 24-hour work without requiring a
> full rebuild.

---

## 0 · How to read this document

This is the **feature specification of the Round 2 submission** — the parts of HelioOps
that exist because of Challenge #1001, and nothing else. Everything the MVP already did
in Round 1 (CV detection, ML impact, four RAG agents, the deterministic verifier, the
five-stage pipeline, the deployment) is *context* here, not content. Where a Round 1
capability appears below, it is because Round 2 changed how and when it discloses itself.

Two tiers, and the distinction is deliberate:

| Tier | Meaning | Test applied |
|---|---|---|
| **A — Core** | This feature *is* the answer to the brief. Delete it and the submission does not exist. | Does it detect a conflict, or gate a commitment, or rank disclosure? |
| **B — Correlated** | This feature applies the same two principles — *disclose gradually*, *surface disagreement* — to another surface of the product. | Does it show a summary first and evidence on demand, or show two sources disagreeing? |

Anything failing both tests is out of scope and is listed explicitly in [§9](#9--boundaries--what-is-not-claimed-as-round-2-work).

Every claim in this document was verified against the working tree on **2026-08-23** by
reading the source and by executing the code. Line references are `file:line` against the
current `main`. Numbers that were *measured* say so.

---

## 1 · The brief, decomposed

The sentence hides three separable requirements. Each one is independently satisfiable
and independently failable, so each is tracked separately throughout this document.

| # | Requirement | Literal wording | Where it is discharged |
|---|---|---|---|
| **R1** | Show detail **gradually** | *"showing detail gradually rather than all at once"* | [A4 · The disclosure ladder](#a4--the-disclosure-ladder) |
| **R2** | Detect conflicts **early** | *"detect conflicts early"* | [A2 · The cross-source conflict engine](#a2--the-cross-source-conflict-engine) |
| **R3** | Present them **before the commit** | *"before the user commits to an action"* | [A1 · The pre-flight run gate](#a1--the-pre-flight-run-gate) |
| **R4** | Substantial, but **not a rebuild** | *"substantial enough for 24-hour work without requiring a full rebuild"* | [§7 · Traceability](#7--traceability-matrix) and [A6](#a6--the-read-only-observation-guarantee) |

**R2 and R3 are not the same requirement.** A system can detect a conflict perfectly and
report it after the fact — that is a log line, and it is what the MVP already had. A
system can gate an action perfectly and have nothing worth saying — that is a cookie
banner. The brief demands both at once, and the failure mode of doing only one is
different in each direction. Both failure modes were hit and corrected during
implementation; see [A2.6](#a26--what-went-wrong-and-how-it-was-caught) and
[A4.5](#a45--the-first-version-was-wrong-and-why).

### 1.1 What "conflict" means in this system

Not a merge conflict, and not an error. **A conflict is two independent data sources
describing the same physical event in ways that cannot both be true.**

Both files exist. Both parse. Every number in each is well-formed and plausible. Neither
is detectable by validating one file — the disagreement only exists in the relationship
between them.

> Two witnesses to the same accident. One says the car was doing 30, the other says 80.
> Neither statement is malformed and neither witness is obviously lying — but you now
> know something neither statement contains: **one of them is wrong, and you should find
> out which before you act on either.**

This is the distinction that separates a conflict rule from a validation rule:

| | Validation | Conflict detection |
|---|---|---|
| Question asked | *Is this number well-formed?* | *Can these two well-formed numbers both be true?* |
| Inputs needed | One | Two, plus a physical tolerance |
| Failure it catches | Corrupt, missing, malformed | Internally valid data describing a different event |
| Where HelioOps had it before Round 2 | Everywhere | Nowhere |

---

## 2 · What the MVP did, and the two failures the brief names

The Round 1 MVP (through commit `232ea94`, 2026-06-14) had one button that mattered. You
selected a storm, pressed **Run**, and five stages executed in sequence: CV detection →
ML impact → four agentic advisories → deterministic verifier → delivery.

### 2.1 The commitment

That click costs, and the cost was invisible at the moment of paying it:

| Cost | Measure |
|---|---|
| **Wall time** | 65–80 s, dominated by four parallel LLM reasoning passes |
| **Money / quota** | Metered Groq tokens against a fixed per-minute budget |
| **Lockout** | One run per storm per 30 s (`middleware.py:64`) — the second press is refused with a 429 |
| **Reversibility** | None. There was no stop control in the MVP |

A confirmation step in front of a cheap reversible action is friction — it is why
*"are you sure?"* on deleting one email is universally hated. In front of an expensive,
effectively irreversible one, it is the difference between finding out before and finding
out after.

### 2.2 Failure one — the system could not tell you it had degraded

HelioOps is built on a rule its own project memory states out loud:

> Every external client is cache-first: cache hit → disk, miss → fetch + write, network
> failure → stale cache → hardcoded fallback dict. **Never raise to the caller.**

This is a *good* rule. It is why the repo can be cloned on conference wifi and produce a
working demo. Nothing in the pipeline hard-fails.

But a system that never fails is a system that never *tells you* it failed. Every
degradation was one line in a log file nobody reads during a demo:

```
WARNING  No preprocessed PNGs in data/cached/lasco/2024-05 — falling back to stub
WARNING  L1 fetch produced no usable reading - using fallback defaults
WARNING  DONKI returned no CME in window - using stub speed
```

The operator saw a confident, complete advisory either way.

| What silently happened | What the operator saw | Why it matters |
|---|---|---|
| No preprocessed imagery on disk | A normal advisory | The detector never looked at this storm. It replayed a stored answer. |
| L1 solar-wind cache unreadable | A normal advisory | Severity was computed from 400 km/s / Bz 0 placeholders, not measurements |
| Knowledge base empty | An advisory with no citations | The agents were writing ungrounded prose |
| Token budget exhausted | A *very slow* run | Quota exhaustion does not raise — it **stalls**, silently, for up to a minute |
| Rate limiter still cooling | An error, *after* the click | You spent the click to learn you could not spend the click |
| ML checkpoints missing | Impact numbers | Conservative defaults, presented identically to real predictions |

**The failure mode was not "it breaks". It was "it lies by omission."**

### 2.3 Failure two — nothing compared the sources against each other

HelioOps reads four independent descriptions of the same storm:

| Source | What it measures | Serves historical dates? |
|---|---|---|
| **Committed stub** | The hand-checked reference description of this event | n/a — local |
| **NASA DONKI** | Human-reviewed CME speed, angular width, ballistic arrival | **Yes** |
| **GOES XRS** | Soft X-ray flux → flare class → R-scale | **No** — real-time endpoint only |
| **DSCOVR L1** | Solar wind speed and Bz ~1 h upstream of Earth | **No** — real-time endpoint only |

Each was validated *on its own*: is the file there, does it parse, does it contain a
number. **Nothing checked whether they agreed with each other.** Two real examples, both
present in this repository today:

- The reference record for the May 2024 storm says the CME left the Sun at **2200 km/s**.
  NASA's own analysis of the same event measures **1332 km/s**. Both files are valid.
  They disagree by **65%**.
- The solar-wind files *named* for 2024 storms contain data from whatever day they were
  downloaded, because the NOAA endpoint they came from serves only the last few days and
  ignores the date you ask for. Every field parses. Every number is real. **None of it is
  about the storm.**

### 2.4 The map from failures to the brief

The two halves of the brief map exactly onto the two failures above, which is why this
challenge fitted this MVP without a rebuild:

```
"detect conflicts early"          ->  compare the four sources against each other,
                                      and do it BEFORE the eighty seconds
"showing detail gradually"        ->  the answer to "what is wrong" is a paragraph of
                                      physics; the answer to "should I press Run" is
                                      one sentence. Show the sentence. Keep the
                                      paragraph one deliberate click away.
```

And the scope constraint was satisfiable because **everything needed already existed**.
The pipeline already knew where every cache file lived. The ingestion layer already had a
parser for each. The health system already knew what was degraded. Nothing had to be
built; something had to be **read without running it**.

That is the whole idea: **a dry run.**

---

## 3 · The solution in one screen

```
   Operator selects a storm and clicks [ Run live ] or [ Run batch ]
        |
        |  Dashboard.jsx:566  requestRun()  — the direct call to the runner is gone
        v
   GET /api/preflight/{storm_id}                                    ~0.31 s, measured
        |   app.py:271 -> preflight.run_preflight()
        |
        +-- 1. QUOTA + LOCKOUT   peek_rate_limit() · Groq TPM headroom      (no writes)
        +-- 2. CACHE PREDICTION  stat every source · parse only if present  (no fetches)
        +-- 3. CONFLICT RULES    6 cross-source physics rules on the parsed values
        +-- 4. SYSTEM HEALTH     TTL-cached dependency probe
        |
        v
   { storm_id, ready, estimated_duration_s, findings[ {id,severity,title,detail} ] }
        |
        |  preflight.js:30  gateDecision()  — pure: sorts, counts, picks the headline
        v
   +--------------------------------------------------------------------+
   |  PRE-FLIGHT   [1 warn] [3 info]                        est ~70s    |  <- L1b  scan
   |                                                                    |
   |  Results will replay canned data, not this storm's imagery.        |  <- L1   decide
   |                                                                    |
   |  [ Start run ]   [ Cancel ]                                        |
   |                                                                    |
   |  > show all 4 findings                                             |  <- L2   evidence
   +--------------------------------------------------------------------+
        |                                    |
        | Start run                          | Cancel
        v                                    v
   the 65–80 s pipeline runs            nothing happens; prior results stay on screen
```

The gate is **not a modal**. It renders inside the RUN CONTROL panel, above the stream,
and Cancel simply removes it (`Dashboard.jsx:430-432`, `:725`).

---

## 4 · Feature index

| ID | Feature | Tier | Serves | Primary location |
|---|---|:--:|:--:|---|
| **A1** | [The pre-flight run gate](#a1--the-pre-flight-run-gate) | A | R3 | `Dashboard.jsx:566-594`, `app.py:271` |
| **A2** | [The cross-source conflict engine](#a2--the-cross-source-conflict-engine) | A | R2 | `preflight.py:240-351` |
| **A3** | [The relevance layer — veto and demotion](#a3--the-relevance-layer--veto-and-demotion) | A | R2 | `preflight.py:68-93`, `:339-351` |
| **A4** | [The disclosure ladder](#a4--the-disclosure-ladder) | A | R1 | `preflight.js:30-47`, `Dashboard.jsx:299-356` |
| **A5** | [Fallback and system-state prediction](#a5--fallback-and-system-state-prediction) | A | R2, R3 | `preflight.py:98-227`, `:376-429` |
| **A6** | [The read-only observation guarantee](#a6--the-read-only-observation-guarantee) | A | R3, R4 | `preflight.py:1-18`, `middleware.py:79` |
| **A7** | [Advisory, never blocking](#a7--advisory-never-blocking) | A | R3 | `Dashboard.jsx:329-336`, `:582-585` |
| **B1** | [The five-layer console rail](#b1--the-five-layer-console-rail) | B | R1 | `Dashboard.jsx:623-647`, `panels.jsx` |
| **B2** | [The verifier surface — proposed vs enforced](#b2--the-verifier-surface--proposed-vs-enforced) | B | R1, R2 | `panels.jsx:282-355`, `verifier.py` |
| **B3** | [The provenance chain, gaps rendered as gaps](#b3--the-provenance-chain-gaps-rendered-as-gaps) | B | R1 | `console.js:36-67`, `panels.jsx:359-412` |
| **B4** | [Quantile interval bars](#b4--quantile-interval-bars) | B | R1 | `console.js:80-104`, `panels.jsx:184-271` |
| **B5** | [Citation deep-links to the cited page](#b5--citation-deep-links-to-the-cited-page) | B | R1 | `citation.js`, `app.py:245` |
| **B6** | [The live stream and the Stop control](#b6--the-live-stream-and-the-stop-control) | B | R1, R3 | `Dashboard.jsx:97-130`, `:561-564` |

---

# TIER A — the features that *are* the solution

## A1 · The pre-flight run gate

### A1.1 What it is

Every Run in HelioOps now travels through a three-phase transition instead of firing
immediately:

```
preflight  ->  confirmation  ->  execute
```

There is no path around it. Both runners — `Run live (WebSocket)` and
`Run batch (REST)` — call the same `requestRun`, and the chosen runner is carried
*through* the gate state so confirming starts the one you asked for
(`Dashboard.jsx:414`, `:417`, `:554-557`).

This is the feature that discharges **R3 — present conflicts before the user commits.**

### A1.2 The endpoint

`GET /api/preflight/{storm_id}` — `backend/app.py:271-287`.

```python
@app.get("/api/preflight/{storm_id}")
async def preflight_storm(storm_id: str):
    # Same gates as detect_storm, minus everything that mutates: no
    # check_rate_limit (it records on read), no record_* counters.
    if not validate_storm_id(storm_id):
        raise HTTPException(400, f"Invalid storm_id format: {storm_id}")
    available = _available_storms()
    if storm_id not in available:
        raise HTTPException(404, f"Unknown storm_id '{storm_id}'. Available: {available}")
    from backend.preflight import run_preflight
    return await run_preflight(storm_id)
```

It **deliberately mirrors** `POST /api/detect/{storm_id}` (`app.py:170-217`): the same
`^\d{4}-\d{2}-G[1-5]$` regex validation, the same 400 for a malformed id, the same 404
for a well-formed-but-unknown one — **minus every mutating call**.

The comment naming what was removed is load-bearing. The obvious "improvement" to this
handler is to make it symmetric with its sibling by adding `check_rate_limit` back — and
that single line would silently destroy the feature. See [A6.3](#a63--invariant-2--peek-do-not-check).

### A1.3 The response contract

```json
{
  "storm_id": "2024-05-G5",
  "ready": true,
  "estimated_duration_s": 70,
  "findings": [
    {
      "id": "stub_donki_speed_mismatch",
      "severity": "info",
      "title": "Reference CME speed is 65% off the DONKI record",
      "detail": "The committed reference for this storm says 2200 km/s; DONKI's CME analysis measures 1332 km/s. DONKI's own analyses spread by 10-20%, so a gap this wide means the reference severity and the observational record are not describing the same event speed. Detection is replaying the stub for this run, so this source is never read and the disagreement cannot affect the output."
    }
  ]
}
```

| Field | Meaning | Contract note |
|---|---|---|
| `id` | Stable, machine-readable finding identifier | **Tests assert on ids, never on prose**, so wording can be improved without touching a test |
| `severity` | `block` \| `warn` \| `info` | Exactly three. See the discipline below |
| `title` | The consequence, in one sentence | This becomes the headline when it is the most severe finding |
| `detail` | Full reasoning including the physics and the numbers | Never truncated in the UI |
| `ready` | `not any(severity == "block")` (`preflight.py:456`) | **Advisory only** — the frontend never uses it to disable anything |
| `estimated_duration_s` | Running mean of observed pipeline durations, default 70 (`preflight.py:432-434`) | Sourced from `health._requester_metrics["pipeline_duration_seconds"]` |

**The severity discipline is what keeps the pills meaningful:**

| Severity | Means | Produced by |
|---|---|---|
| `block` | The run **will be rejected right now** | The rate limiter, and only the rate limiter |
| `warn` | The run will succeed, but the result is compromised **in a specific named way** | Stub replay, reachable conflicts, degraded health, no API key, low quota, wrong-epoch cache |
| `info` | Worth knowing; will not change your decision | Missing optional caches, demoted conflicts, small mismatches |

> **`warn` is reserved for things that change the meaning of the output.** A missing cache
> the run will simply re-fetch is `info`. A source that disagrees with another source
> *and can reach the result* is `warn`. The moment `warn` starts covering "something is
> slightly unusual", the pills stop carrying information.

### A1.4 Execution order, and why it is this order

`preflight.py:439-459`:

```python
async def run_preflight(storm_id, base_dir=None):
    cfg  = STORM_CONFIGS[storm_id]
    base = Path(base_dir) if base_dir else BACKEND_DIR

    findings  = list(await _quota_findings(storm_id))                  # 1
    cache_findings, stub, cme, flare, l1 = _cache_findings(cfg, base)  # 2
    findings += cache_findings
    stub_replay = any(f["id"] == "cv_stub_replay" for f in cache_findings)
    findings += _conflict_findings(stub, cme, flare, l1, stub_replay)  # 3
    findings += _system_findings()                                     # 4

    return {
        "storm_id": storm_id,
        "ready": not any(f["severity"] == "block" for f in findings),
        "estimated_duration_s": _estimate_duration(),
        "findings": findings,
    }
```

The order is not cosmetic:

1. **Quota first** — it is the only source of `block` and needs no disk access.
2. **Caches second** — this stage is what *produces* `cme`, `flare` and `l1`, the parsed
   values the conflict rules consume. It also decides which of them are trustworthy
   enough to hand on at all (see [A3](#a3--the-relevance-layer--veto-and-demotion)).
3. **Conflicts third**, taking those values plus the `stub_replay` flag.
4. **System health last**, because it is the expensive one and is TTL-cached.

`base_dir` mirrors `detect()`'s own parameter so the entire check can be pointed at a
`tmp_path` in tests without patching a single module-level constant — which is what makes
the read-only proof in [A6.2](#a62--invariant-1--stat-before-parse) possible.

### A1.5 The frontend gate

`Dashboard.jsx:566-588` — `requestRun` replaces the direct call to the runner:

```js
const requestRun = useCallback(runner => {
  if (!stormId || busy || gate) return
  setGate({ phase: 'loading', runner })
  getPreflight(stormId)
    .then(data => {
      const decision = gateDecision(data)
      if (decision.action === 'run') { setGate(null); startRunner(runner) }
      else setGate({ phase: 'confirm', runner, decision })
    })
    .catch(() => { setGate(null); startRunner(runner) })   // never break the demo
}, [stormId, busy, gate, startRunner])
```

Gate state is a three-state machine held in one variable (`Dashboard.jsx:459-460`):

| State | Value | UI |
|---|---|---|
| Idle | `null` | Run buttons enabled |
| Checking | `{phase:'loading', runner}` | *"checking cached inputs, conflicts and quota…"* (`:300-307`) |
| Deciding | `{phase:'confirm', runner, decision}` | The full panel; all run buttons and the storm selector disabled (`:369`, `:414`, `:417`) |

`confirmGate` (`:590-594`) clears the gate and starts the carried runner. Cancel
(`:725`) clears the gate and starts nothing.

### A1.6 Pre-commitment context, beyond the findings

Two smaller elements share the RUN CONTROL panel and exist for the same reason — telling
you what you are about to commit to, before you commit:

- **The panel lede** (`Dashboard.jsx:392-396`) states the price of the click in the same
  place as the button: *"A run is a 65–80 s commitment — the reasoning pass dominates —
  so every run passes a pre-flight check first, and the check never blocks the run."*
- **The storm selector shows prior runs** (`StormRow`, `:363-384`). `/api/storms` returns
  a `completed` map — `completed_at`, `advisory_count`, `verified_count`, `error_count`
  per storm (`app.py:297-306`) — which the MVP fetched and discarded. It now renders, so
  a storm that already has results is visually distinct from one that has never run, and
  *"no run this session"* is stated rather than implied by blankness.

### A1.7 Why a gate at all — and the alternative

**The alternative:** run immediately, and report which fallbacks fired in the result.
Cheaper: no new endpoint, no new interaction.

**Why the gate wins — cost asymmetry:**

| | Cost |
|---|---|
| The pre-flight check | **0.31 s measured**, no quota, no side effects |
| The commitment it guards | 65–80 s, metered tokens, 30 s lockout |

The post-hoc alternative also has a subtler failure. By the time the result is on screen,
the operator is reading advisories. A note saying *"detection replayed canned data"*
competes for attention with the thing they came for, and loses.

**Where the alternative would genuinely be better:** if the run were 3 seconds and free,
the gate would be pure friction and should be deleted.

### A1.8 Verification

| Check | Result |
|---|---|
| `test_schema_and_ready_on_real_repo` — runs the real entry point against the real repo, asserts the exact key set and that every finding matches the four-key shape | pass |
| `test_rate_limited_blocks` — seeds `_pipeline_calls`, asserts `ready is False` and the only `block` is `rate_limited` | pass |
| Live `uvicorn`: 400 on a malformed storm id, 404 on a well-formed unknown one, correct results for both storms | verified |
| Repeated preflight calls consume no rate-limit slot | pinned by `TestPeekRateLimit` |

---

## A2 · The cross-source conflict engine

`backend/preflight.py:240-351` · **This is the heart of "detect conflicts early".**

### A2.1 The principle, and why the tolerance is the hard part

Every rule needs **two sources** and a **physical tolerance**. The tolerance is the
important half and the easy half to get wrong: set it too tight and the panel cries wolf
on ordinary measurement spread; set it too loose and it never fires.

Every threshold in the module therefore carries a comment naming the real-world quantity
it was derived from (`preflight.py:35-40`):

```python
DEFAULT_DURATION_S    = 70
TPM_LOW_THRESHOLD     = 4000   # ~one full advisory pass
STALE_EPOCH_DAYS      = 7      # beyond this a cache cannot describe the storm
STUB_DONKI_SPEED_TOL  = 0.25   # DONKI's own analyses spread 10-20%; beyond that is disagreement
ARRIVAL_TOL_H         = 12.0   # ballistic arrival estimates carry ~10h MAE
HEALTH_TTL_S          = 30     # health probe loads models + counts Chroma; don't repeat it
```

**None of these is a round number chosen because it looked sensible.** Each is the
published error bar of the thing being compared, plus headroom. That property is what
makes them tunable later: a named constant with a stated derivation can be moved when
real data says otherwise; a magic number cannot.

### A2.2 The rule catalogue

Six cross-source rules. Each is a physical statement about what two independent
measurements are allowed to say about the same event.

---

#### `stub_donki_speed_mismatch` — warn

**Compares** the committed reference CME speed against NASA's measured speed.
**Fires when** `abs(ref - obs) / obs > 0.25` (`preflight.py:251`).

**The physics.** DONKI publishes multiple independent analyses of the same CME, by
different analysts using different coronagraph pairs. Those analyses routinely spread by
**10–20%** against each other. A gap inside 20% is the normal disagreement of the method
and means nothing. A gap beyond 25% is larger than the method's own spread — which means
the two files are not describing the same event speed.

**On this repository, measured today:**

| Storm | Reference | DONKI | Drift | Fires? |
|---|---|---|---|---|
| `2024-10-G4` | 1480 km/s | 1323 km/s | **11.9%** | no — inside analysis spread |
| `2024-05-G5` | 2200 km/s | 1332 km/s | **65.2%** | **yes** |

**This is the one rule that runs on a clean checkout, and it is why the two storms produce
different panels.** Without it the gate says the same three things about every storm
forever, which is exactly how a warning becomes wallpaper.

---

#### `stub_donki_arrival_mismatch` — warn

**Compares** the reference arrival time against DONKI's ballistic estimate.
**Fires when** the gap exceeds 12 h (`preflight.py:267`).

**The physics.** A ballistic arrival estimate propagates the CME at constant speed from
the coronagraph to Earth. It ignores drag, so it carries roughly **10 hours of mean
absolute error** against real arrivals. Twelve hours is that error bar plus a small
margin: below it, a gap is the model's known inaccuracy; above it, the two sources are
describing different events.

Currently silent on both storms — G4 is 1.8 h apart, G5 is 7.6 h. Both inside the
ballistic error bar, **correctly**.

---

#### `speed_disagreement` — warn

**Compares** CME launch speed (DONKI) against solar wind speed at L1 (DSCOVR).
**Fires when** `l1 > cme * 1.10`, or `l1 < cme * 0.30` (`preflight.py:279`, `:287`).

**The physics.** A CME leaves the Sun fast and is dragged toward the ambient solar wind
speed on the way out. Two bounds follow:

- **Arriving faster than it launched is unphysical.** Nothing accelerates a CME between
  the Sun and L1. The 10% margin is measurement error, not a real allowance.
- **Losing 70% of its speed exceeds any plausible drag model.** Real events decelerate;
  they do not fall off a cliff. Below 30% of launch speed, the two files are almost
  certainly about different events.

The two bounds are **asymmetric on purpose, because the physics is asymmetric**:
deceleration is expected and unbounded-ish, acceleration is not allowed at all.

---

#### `arrival_eta_mismatch` — warn

**Compares** DONKI's ballistic arrival against the arrival implied by the L1 measurement
(`measured_at + eta_minutes`).
**Fires when** they are more than 12 h apart (`preflight.py:302`).

Same 10 h-MAE reasoning applied to a different pair. **Skipped entirely if either
timestamp fails to parse** (`_parse_ts` returns `None`, `:232-237`) — a missing input is
never treated as a disagreement.

---

#### `bz_northward_strong_g` — warn

**Compares** the reference G-scale against the measured Bz sign at L1.
**Fires when** `stub.scales.G >= 3` and `l1.bz_nt >= 0` (`preflight.py:312`).

**The physics — the most fundamental relationship in the whole system.** Geomagnetic
storms are driven by *magnetic reconnection* between the arriving interplanetary field
and Earth's, and reconnection requires the arriving field to point **southward**
(negative Bz). Northward Bz does not drive strong geomagnetic storms. **It is not a
matter of degree — it is the mechanism.**

A cached L1 file showing positive Bz alongside a G3-or-worse severity is therefore a
contradiction at the level of the underlying physics, not a discrepancy in a number. The
finding also names the downstream consequence: `fuse()` weights Bz at 0.2 of the
detection confidence and will drop that term.

---

#### `flare_r_mismatch` — warn *or* info

**Compares** the reference R-scale against the flare class the GOES cache actually
classifies to (`preflight.py:321-337`).
**Fires when:**

- `stub.scales.R >= 2` **and** `flare.r_scale == 0` → **warn**
- otherwise `abs(stub_r - flare_r) >= 2` → **info**

**The physics.** The R-scale is defined *directly* from peak soft X-ray flux — it is a
lookup, not a model. So "the reference says R3 but the flux record classifies below
M-class" is not two estimates differing; **it is a severity with no evidence behind it in
the file that is supposed to contain the evidence.**

The two-tier severity is deliberate: complete absence of a flare behind a real R-scale is
a `warn`; being two levels off is a discrepancy worth stating but not worth changing your
decision over, so `info`.

---

### A2.3 The same parsers the real run uses

The conflict rules never see raw JSON. They consume values produced by the **production
ingestion parsers**, invoked from `_cache_findings` (`preflight.py:98-227`):

| Value | Produced by | Same function the pipeline calls? |
|---|---|---|
| `cme` | `select_best_cme()` + `cme_to_fields()` | Yes — `detect.py:159-162` |
| `flare` | `fetch_and_classify_flare()` | Yes — `detect.py:191-192` |
| `l1` | `fetch_l1_wind()` | Yes — `detect.py:194` |
| `stub` | the committed `cv/stubs/storm_event_*.json` | Yes — `detect.py:134`, `:168` |

**The alternative** was to write light-weight readers inside `preflight.py`: faster, no
import of the CV layer, no risk of a parser side effect.

**Why reuse wins.** A prediction that uses different code than the thing it predicts can
disagree with it, and every such disagreement is a bug that only appears in production.
Reusing the four production parsers makes an entire class of *"the check said fine but it
wasn't"* **structurally impossible.**

The cost is exactly the trap in [A6](#a6--the-read-only-observation-guarantee): those
parsers fetch and write when the file is absent. That cost is paid once, by the
stat-before-parse invariant, and pinned by a test. **Paying a known cost once beats
accepting an unbounded class of divergence bugs forever.**

### A2.4 Guard discipline

Every rule is guarded on the presence of both its inputs — `if cme and l1:`,
`if flare is not None:`, `if l1 and stub_g >= 3 and ...`. A rule with a missing input is
**skipped**, never fired.

This matters more than it looks. A conflict detector that treats "I could not read one
side" as "the two sides disagree" produces its loudest output on its least reliable data,
which is the precise inverse of what a diagnostic should do.

### A2.5 The self-consistency guard

`test_stubs_are_internally_consistent` (`test_preflight.py:173-180`) is the test that
protects the panel from crying wolf about the repository's own reference data:

```python
def test_stubs_are_internally_consistent(self):
    # The rules must be silent on the committed stubs' own values —
    # otherwise every fresh checkout warns about its own reference data.
    for storm_id, cfg in STORM_CONFIGS.items():
        stub = json.loads((BACKEND_DIR / cfg["stub_path"]).read_text())
        f = _conflict_findings(stub, stub["cme"], stub["flare"], stub["l1_solar_wind"])
        assert f == [], f"{storm_id} stub fired {_ids(f)}"
```

Each committed stub is fed its *own* values as if they had come from three independent
sources, and every rule must stay silent. A stub that contradicts itself would make the
panel warn about the shipped reference data on every clone — noise indistinguishable from
signal, arriving on day one.

It also **pins the thresholds against real data**: nobody can tighten
`STUB_DONKI_SPEED_TOL` past the point where the shipped stubs trip it without this test
failing.

### A2.6 What went wrong, and how it was caught

**Version one of this engine shipped with all four of its rules unreachable on a fresh
clone**, and the tests were green.

Commit `2ea377a` (16:06) delivered the module, the route, the panel, and 25 passing tests
including a full `TestConflictRules` class. Every one of those tests called
`_conflict_findings()` directly with **fabricated dictionaries**. They proved the rules
computed correctly *given inputs*. Nothing proved the inputs ever arrived.

They did not. Every cross-source rule needed at least two of the DONKI, flare and L1
caches, and **none of those caches were committed**. On a fresh clone the code path was:

```
cache file does not exist
  -> emit "cache missing" (info)
  -> leave the parsed value as None
  -> every conflict rule guarded by `if cme and l1:` is skipped
```

The panel worked perfectly and said nothing — the same four findings, for both storms,
forever.

**The root cause, found while fixing it:** NOAA's `rtsw` (solar wind) and `xrays` (GOES
flux) endpoints are **real-time only. They take no date parameter.** You cannot ask them
for October 2024. So `backend/data/cached/l1/2024-10-11.json` does not contain October
2024 data — it contains whatever was current on the day someone ran the prefetch script.
**The filename is a label, not a description.**

That discovery also explained a *pre-existing* mystery nobody had connected: the flare
classifier had been reporting C-class (R0, no radio blackout) for two X-class storms. The
classifier was never broken. It searches for the peak flux within ±6 h of the storm
timestamp, and nothing in the file falls inside that window because the file is from a
different month. The peak search finds nothing and correctly reports nothing.

**The fix** (`a18490b`, 16:53 — 47 minutes later):

1. **Commit the DONKI caches** (44 KB, 20 and 24 real 2024 records). DONKI is the one
   source that serves historical dates, making stub-vs-DONKI the comparison that runs on
   a clean checkout — and introducing the new `stub_donki_speed_mismatch` rule.
2. **Add the `*_cache_stale_epoch` rules** and gitignore `l1/` + `xrs/`, with the
   reasoning and the regeneration commands *in the ignore file*.
3. **Demote conflicts under stub replay** ([A3.2](#a32--the-stub-replay-demotion)).
4. **Correct the false "never writes" docstring** and the 9.7 s behind it ([A6.5](#a65--the-fourth-one--admitting-what-is-not-read-only)).
5. **Rebuild the disclosure layer** ([A4.5](#a45--the-first-version-was-wrong-and-why)).
6. **Extract `gateDecision()`** into its own pure module.

**The three lessons, stated plainly:**

> **A feature is not shipped until it can fire on a clean checkout.** "It works on my
> machine" had a specific mechanism here: uncommitted data files.
>
> **Passing tests can measure the wrong thing.** Twenty-five green tests described a
> calculator that was correct and unreachable. Ask of any suite: *does anything here prove
> the code runs in production, or only that it computes correctly when called?*
>
> **A comment that overstates a guarantee is a liability.** The fix was not only to make
> "never writes" true — it was to scope the claim precisely enough that it stays true.

### A2.7 Why L1 and XRS are gitignored and DONKI is committed

```gitignore
# rtsw (L1) and xrays (GOES) are REAL-TIME endpoints with no date parameter, so
# these snapshots hold the day they were fetched, not the 2024 storm they are
# named for - ~8MB that preflight can only ever report as unusable.
backend/data/cached/l1/
backend/data/cached/xrs/
```

Committing 8 MB of data whose only possible use is to trigger a *"this data is unusable"*
finding would be storing noise. Committing 44 KB of DONKI records that make a real
conflict rule fire on a clean checkout is storing **signal**.

The ignore file also carries the regeneration commands, so the decision is reversible by
anyone who reads it.

---

## A3 · The relevance layer — veto and demotion

Two mechanisms whose **only job is to stop the conflict engine from producing findings**.
They are the least visible part of the solution and the part that most separates a
conflict detector from an alarm generator.

### A3.1 The stale-epoch veto

`preflight.py:68-93`, invoked at `:205-226`.

```python
# Epoch check LAST, so it can veto sources the rules would otherwise use.
```

If a file named `2024-10-11.json` actually contains data from the day it was downloaded,
**every physics rule above will fire — and every one of those findings will be true and
useless.** *"The solar wind speed contradicts the CME launch speed"* is a correct
statement about two files that describe different months. It diagnoses an instrument
disagreement when the actual fault is a date range. **A wrong answer stated well, which
is worse than no answer.**

So `_stale_epoch` runs **last**, compares the first `time_tag` in the cache against the
storm date, and when the gap exceeds `STALE_EPOCH_DAYS = 7` it does two things:

1. **Emits a `warn`** explaining that the cache is from the wrong dates, naming the gap in
   days, and stating *why* the endpoint cannot serve the date you want.
2. **Sets the parsed value back to `None`** (`preflight.py:215`, `:225`) — withholding
   that source from every cross-source rule.

The finding text says this out loud:

> Cross-source physics checks against this source are skipped — running them would report
> a date-range error dressed up as a disagreement between instruments.

**This is the most under-appreciated rule in the module.** It is the only one whose job is
to prevent other rules from producing findings. *A conflict detector that cannot recognise
its own inputs as invalid will manufacture conflicts out of bad data — and it will
manufacture them in the exact confident register it uses for real ones.*

It is pinned by `test_stale_source_is_withheld_from_the_rules` (`test_preflight.py:248-262`),
which asserts **both** halves: the finding appears **and** `l1 is None` / `flare is None`.
That second assertion protects a behaviour that is easy to lose in a refactor — the
finding stays visible, so the code still *looks* correct after the `None` assignment is
deleted.

### A3.2 The stub-replay demotion

`preflight.py:339-351`.

```python
# detect() returns the stub wholesale at detect.py:133 when no frames
# exist, so it never reads these sources. Reporting them as warnings would
# inflate the count and flip the button for something that cannot change
# the result. Keep them visible, drop them to info, say why.
if stub_replay:
    for f in findings:
        f["severity"] = "info"
        f["detail"] += (
            " Detection is replaying the stub for this run, so this source "
            "is never read and the disagreement cannot affect the output."
        )
```

**The situation.** When no preprocessed frames exist, `detect()` returns the committed
stub wholesale at `detect.py:133-134` — *before* reading DONKI, flare or L1 at all. A
disagreement between those sources is still **true** (the files really do contradict each
other, and you would want to know before fixing the data), but it **cannot affect this
run's output**.

**Three options, and why the third:**

| Option | Problem |
|---|---|
| Leave it `warn` | An amber pill for something with no path to the result. Erodes what `warn` means. |
| Drop the finding | Suppressing true information because it is currently inert. It never comes back. |
| **Demote and explain** | **Chosen.** |

Three properties, all deliberate:

- The finding is **not hidden**. Suppressing true information because it is currently
  inert is how you lose it permanently.
- It is **demoted, not deleted**, so the severity pill keeps meaning *"this can change
  what you get"*.
- The reason is **appended to the detail**, so the demotion explains itself rather than
  looking like an inconsistency between the pill and the prose.

This is why the G5 panel on a clean checkout shows the 65% speed mismatch as `info` rather
than `warn` — the honest answer, given that nothing on this checkout will read that file.

Pinned by `TestStubReplayDemotion` (`test_preflight.py:302-320`), which asserts **both**
the severity drop *and* the appended explanation:

```python
def test_demoted_and_annotated_under_stub_replay(self):
    f = self._fired(True)[0]
    assert f["severity"] == "info"
    assert "never read" in f["detail"]
```

*A demotion without its reason is an inconsistency between the pill and the prose, and
this asserts that never ships.*

### A3.3 Why this layer is the differentiator

> **Findings are honest about their own relevance.** The difference between a conflict
> detector and an alarm generator is entirely here: one asks *"do these disagree?"*, the
> other also asks *"and can that disagreement reach the output the user is about to
> buy?"*

---

## A4 · The disclosure ladder

**This is the feature that discharges R1 — show detail gradually.**

### A4.1 Progressive disclosure, defined precisely

Progressive disclosure is an interface principle: **show the smallest thing that lets
someone decide, and put everything else one deliberate action away.**

The failure modes are symmetrical and both common:

| Failure | Example | Consequence |
|---|---|---|
| **Too little** | *"3 warnings."* | A number is a tally, not information. You cannot decide from it, so you must expand — which means the top layer bought you nothing. |
| **Too much** | The full evidence up front | Everything visible, nothing legible. People learn to click past it. This is how cookie banners became invisible. |

What makes it work is that **the top layer must be decision-shaped**: it answers the
question the user is actually holding, in the form they need. Here the question is
*"should I press Run?"*, so the top layer is a sentence about **consequence**.

### A4.2 The three layers as built

`Dashboard.jsx:299-356`.

---

**Layer 1 — the sentence.** (`Dashboard.jsx:327`, styled `dashboard.css:364-372`)

One line of plain English, taken from the **most severe finding**, describing the
*consequence* rather than the fact:

> Results will replay canned data, not this storm's imagery.

It is coloured by severity — `tone-ok` green / `tone-warn` amber / `tone-bad` red — and
set at 14 px, **larger than the pills above it, deliberately**. The CSS carries the
reasoning:

```css
/* Layer 1: the sentence that decides the click. Sized above the pills on
   purpose — the tally is scannable, this is what it means. */
```

When there is genuinely nothing to say, the sentence **says so rather than disappearing**
(`preflight.js:12`):

> Cached inputs look consistent - nothing to flag.

---

**Layer 1b — the pills and the estimate.** (`Dashboard.jsx:313-325`)

`1 warn` · `3 info` · `est ~70s`, rendered in `SEVERITIES` order so the worst count is
leftmost. This is the **scan layer**: how much is there, how bad, and how long will this
take. A `clear` pill renders when `findings.length === 0`.

Counts belong *here*, next to the sentence — **never instead of it**.

---

**Layer 2 — the evidence.** (`Dashboard.jsx:338-353`)

Behind a native `<details>` element: `> show all 4 findings`. Each entry carries a
severity pill, the title, and the **full, untruncated** `detail` paragraph including the
physics and the numbers.

**This is the layer that makes the top layer trustworthy.** If the sentence surprises you,
the argument is one click away.

---

### A4.3 The headline is correct by construction

`frontend/src/preflight.js:30-47` — the entire decision layer, a pure function:

```js
export function gateDecision(data) {
  if (!data || !Array.isArray(data.findings)) return { action: 'run' }

  const findings = [...data.findings].sort((a, b) => rank(a.severity) - rank(b.severity))
  const at = sev => findings.filter(f => f.severity === sev).length
  const counts = { block: at('block'), warn: at('warn'), info: at('info') }
  const top = findings[0]

  return {
    action: 'confirm',
    findings, counts,
    serious: counts.block + counts.warn,
    estimate: data.estimated_duration_s ?? null,
    headline: top ? top.title : CLEAN_HEADLINE,
    tone:     top ? toneOf(top.severity) : 'ok',
  }
}
```

**The sort is most-severe-first and the headline is always `findings[0]`.** That single
line is the entire mechanism by which layer 1 states the worst thing. It is not
hand-ordered and it is not curated — **it is a sorted function, so the headline is the
most severe finding by construction rather than by editorial care.**

Two details worth naming:

- **`rank()` sends unknown severities to the end** (`preflight.js:15-18`):

  ```js
  const rank = sev => {
    const i = SEVERITIES.indexOf(sev)
    return i === -1 ? SEVERITIES.length : i
  }
  ```

  A naive `indexOf` returns `-1`, which sorts an unrecognised severity to the **front**
  and makes it the headline. If the backend ever adds a fourth severity, this shows it
  last; the naive version would have promoted it above `block`. Asserted at
  `data.test.mjs:53-60`.

- **The `[...data.findings]` copy** — the sort does not mutate the response object.

### A4.4 Why the decision layer is a separate pure module

**The alternative:** keep it inside `Dashboard.jsx`, where it is used.

**Why it moved out.** It is the *only* branching logic in the gate — severity sort,
headline selection, counts, the fall-through to `{action:'run'}`. In its own module with
no React and no DOM, it is assertable from `src/data.test.mjs` with plain node asserts, in
a frontend that has **three runtime dependencies** (React, ReactDOM, Three.js) and no test
framework at all.

Adding vitest and jsdom to cover twenty lines of sorting would have cost more than the
feature. The `npm test` script is literally `node src/data.test.mjs`.

> **The general principle: push the decisions out of the component and into a function,
> then test the function.** What remains in the component is rendering, which is the part
> least worth unit-testing anyway.

The same reasoning produced `citation.js` and `console.js`, which is why [B3](#b3--the-provenance-chain-gaps-rendered-as-gaps),
[B4](#b4--quantile-interval-bars) and [B5](#b5--citation-deep-links-to-the-cited-page) are
testable at all.

### A4.5 The first version was wrong, and why

**Version one's layer 1 was `3 warnings, 1 info`.** A count.

**Why it was replaced.** A count is a tally, not information. It tells you *how much there
is to read*, not what any of it means, so it cannot decide the click — which means you
must expand, which means the top layer bought you nothing. It also treats all warnings as
fungible when they are not: one *"detection will replay canned data"* matters more than
three missing optional caches.

The counts did not disappear. They **moved next to the sentence as pills**, where a tally
is exactly the right shape. **Scan layer and decide layer, in that order, both visible.**

### A4.6 One button label

**Version one had `Run`, `Run anyway`, and `Cancel`. The current version has `Start run`
and `Cancel`** (`Dashboard.jsx:330`, `:333`).

Two labels for one behaviour is not a choice, it is ambiguity. Both buttons ran the
pipeline; the only thing distinguishing them was how bad the findings were — which the
panel had already said in words directly above. Presenting it twice implied a difference
in what would happen, and there was none.

**One label, always the same word. The severity lives entirely in the sentence and the
pills, where it can be stated precisely.**

> ⚠ Several older documents (`README.md:494`, `PRODUCT_BRIEF.md:100`,
> `TECHNICAL_DEEP_DIVE.md:288`) still describe the `Run anyway` label. **The tree says
> `Start run`.** See [§12](#12--corrections-to-older-documents).

### A4.7 What is deliberately *not* in the panel

| Not built | Why |
|---|---|
| **Auto-fix** ("fetch the missing cache", "clear the rate limit") | Every one of those is a write, and the entire value of the check is that it is read-only ([A6](#a6--the-read-only-observation-guarantee)) |
| **"Don't show this again"** | A finding worth showing once is worth showing again. Suppression is how warnings die |
| **Hard blocking** | [A7](#a7--advisory-never-blocking) |
| **Spinner theatre** | The check is sub-second after warm-up, so the loading state is one line of text and usually invisible |

### A4.8 Verification

`frontend/src/data.test.mjs:20-62`, executed via `npm test` — **verified passing on this
tree**:

```
ok — data.test.mjs
ok — preflight gate decision
ok — citationUrl
ok — console panels
```

| Assertion | Line |
|---|---|
| `gateDecision(null \| undefined \| {})` → `{action:'run'}` — the never-break-the-demo path | `:25-27` |
| Headline is the most severe finding regardless of the order the API sent them in | `:39` |
| `tone` follows the top finding's severity | `:40` |
| `serious` counts `block + warn` only | `:41` |
| Per-severity counts | `:42` |
| Findings sorted most-severe-first | `:43` |
| Clean state produces a real sentence, not a blank | `:47-51` |
| **An unrecognised severity sorts last and does not hijack the headline** | `:53-60` |

---

## A5 · Fallback and system-state prediction

The non-conflict half of the findings: **which of the MVP's silent degradations will fire
on this specific run.** This is the direct answer to [§2.2](#22--failure-one--the-system-could-not-tell-you-it-had-degraded).

### A5.1 Cache prediction — `_cache_findings`

`preflight.py:98-227`. Three passes over four sources, in a fixed order.

**Pass 1 — existence.** `Path.exists()` for each cache, and a glob for the imagery. Every
absent cache produces an `info` finding **naming what the run will fall back to**:

| Finding id | Severity | Predicts |
|---|---|---|
| `cv_stub_replay` | **warn** | No preprocessed frames under `{png_dir}/png` + `/diff` → `detect()` returns the stub `StormEvent` wholesale, and **the DONKI, flare, L1 and alert caches will not even be read** |
| `donki_cache_missing` | info | Live DONKI fetch will be attempted; on failure, stub speed/width |
| `donki_no_match` | info | Cache exists but holds no CME inside the storm window |
| `flare_cache_missing` | info | Live GOES fetch attempted; on failure, no flare detected (R0) |
| `l1_cache_missing` | info | Live DSCOVR fetch attempted; on failure, **400 km/s / Bz 0 placeholders** |
| `l1_fallback_data` | **warn** | The file exists and parses, but `fetch_l1_wind` returned `source == "DSCOVR (fallback defaults)"` |
| `alert_cache_missing` | info | The run proceeds with an empty alert text block |

`l1_fallback_data` deserves its own note. The file exists, it parses, and the numbers you
get back are 400 km/s and Bz 0 — **invented placeholders that look exactly like
measurements.** Catching this is the difference between *"no data"* and *"data that is
secretly not data."*

**Pass 2 — parse, only if the file exists.** The production parsers, each wrapped in
`try/except` so an unreadable cache is a *finding*, never a 500.

**Pass 3 — the epoch veto**, last, so it can withhold sources from the rules
([A3.1](#a31--the-stale-epoch-veto)).

### A5.2 Quota and lockout — `_quota_findings`

`preflight.py:388-429`. The only source of `block`, and the only finding that answers
*"can I even run right now?"*

```python
wait = peek_rate_limit(storm_id)
if wait > 0:
    findings.append(_finding(
        "rate_limited", "block",
        "Rate limited - the run will be rejected right now",
        f"One pipeline run per storm per 30s: wait {wait:.0f}s before "
        "running this storm again, or the request returns 429.",
    ))
```

It returns **the wait in seconds**, not a boolean — so the operator is told *"wait 22 s"*
rather than *"not allowed"*.

Then Groq quota, in two tiers:

| Finding | Condition | Detail |
|---|---|---|
| `no_groq_key` | `GROQ_API_KEYS == [""]` | Advisory generation will fail; the run falls back to template advisories. **Returns early** — headroom on no key is meaningless |
| `groq_tpm_low` | Summed headroom `< TPM_LOW_THRESHOLD` (4000, ≈ one full advisory pass) | *"The run will not fail - it will **STALL** waiting for the rolling window to clear. (Process-local accounting; other clients are invisible.)"* |

**Both halves of that wording matter.** Exhausted quota does not raise, it *queues*, which
is why *"the run failed"* would be the wrong warning. And a second process using the same
key is invisible here — **stating that in the finding is cheaper and more honest than
pretending to a certainty the mechanism cannot deliver.**

Why it never asks the provider: [A6.4](#a64--invariant-3--never-probe-the-provider).

### A5.3 System health — `_system_findings`

`preflight.py:376-385`. One `warn` per failing dependency check, each mapped to its
**consequence for this run** rather than its name (`preflight.py:42-47`):

```python
_CHECK_CONSEQUENCE = {
    "detection":      "Detection layer unavailable - the run will fail.",
    "ml_models":      "ML checkpoints missing - impact prediction falls back to defaults.",
    "genai_module":   "GenAI layer broken - advisory generation will fail.",
    "knowledge_base": "Knowledge base empty - advisories will be ungrounded (no citations).",
}
```

*"Health check 'knowledge_base' is degraded"* is a fact. *"Advisories will be ungrounded
(no citations)"* is a consequence. **The panel states consequences, because that is what
decides a click.**

### A5.4 Duration estimate

`preflight.py:432-434`:

```python
def _estimate_duration() -> int:
    durations = _requester_metrics.get("pipeline_duration_seconds") or []
    return round(sum(durations) / len(durations)) if durations else DEFAULT_DURATION_S
```

The running mean of *observed* pipeline durations from the Prometheus requester metrics,
defaulting to 70 s when nothing has run yet. Honest about what it measures — and honest
about what it does not; see [§10.4](#104--the-duration-estimate-ignores-the-main-cause-of-slowness).

---

## A6 · The read-only observation guarantee

**The part of the solution that is genuinely hard, and the part easiest to break by
accident later.**

### A6.1 Why "read-only" is not free here

A pre-flight check has one job: **describe the state the run will find.** The moment it
*changes* that state, it stops describing and starts interfering. It becomes a thermometer
that warms the water.

The problem is that this codebase is built out of components which, **by deliberate
design, write on read**. Not one of them is a bug. Each is a correct answer to a different
question, and each becomes a trap the moment something read-only calls it.

| Component | Behaves correctly for | Trap for a read-only caller |
|---|---|---|
| Ingestion clients | The pipeline, which wants the data | Absence triggers a **fetch and a write** |
| `check_rate_limit()` | `POST /api/detect`, which is about to run | **Asking consumes the slot** |
| Provider quota API | A client that wants to use quota | **Checking spends what it measures** |
| `health_collector` | A `/health` endpoint called rarely | **Loads six models and rewrites the vector store** |

> **The general lesson: adding an observer to a system is not a read-only operation by
> default.** It is read-only only if every function it touches happens to be — and in a
> codebase built on cache-first clients and mutation-on-read counters, most of them are
> not. **The work of building a pre-flight check is not writing the rules. It is finding
> the four places where looking changes the thing.**

### A6.2 Invariant 1 — stat before parse

**The trap.** `fetch_l1_wind(path)` does not mean *"read this file"*. It means *"get me L1
wind, using this file if it happens to be there"*. A missing file is not an error to that
function — it is a cue to go to the network. And it `mkdir`s its cache directory **on
entry**, so it writes even before it fetches.

So the naive implementation of "check what the L1 cache contains":

```python
l1 = fetch_l1_wind(str(l1_path))     # WRONG
```

…creates a directory, hits NOAA, writes a cache file, and reports on data that **did not
exist until you asked**. On every Run click. And it would look like it worked.

**The invariant.** Every cache file is `stat`-ed, and the parser is called only when the
file already exists (`preflight.py:172-196`):

```python
if not l1_path.exists():
    findings.append(_finding("l1_cache_missing", "info", ...))
else:
    l1 = fetch_l1_wind(str(l1_path))
```

**Absence is a finding, never a fetch.** The module docstring states it as a hard
constraint (`preflight.py:8-11`):

> Hard rule for the STORM CACHES: never fetch, never write, never mkdir. Every cache file
> is stat'ed before any parser touches it, because the ingestion clients are
> cache-first-then-NETWORK and create directories on entry.

**How it is held.** `test_read_only_no_mkdir_no_fetch` (`test_preflight.py:94-100`) points
the whole check at an empty `tmp_path` and asserts nothing was created:

```python
def test_read_only_no_mkdir_no_fetch(self, tmp_path):
    _seed_stub(tmp_path)
    before = set(tmp_path.rglob("*"))
    _cache_findings(CFG, tmp_path)
    assert set(tmp_path.rglob("*")) == before
```

**No mocks. No patched network layer. No assertion about which functions were called.** If
anything fetched, `mkdir`'d or wrote, a file exists and the test fails.

This is the strongest test in the suite because it verifies the **property** rather than an
implementation of it. A future refactor that swaps parsers, reorders the passes, or adds a
fifth source still has to keep the directory empty.

### A6.3 Invariant 2 — peek, do not check

**The trap.** `middleware.py:67-76`:

```python
def check_rate_limit(storm_id: str) -> bool:
    now = time.time()
    last = _pipeline_calls.get(storm_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _pipeline_calls[storm_id] = now      # <-- records on read
    return True
```

The name says *check*. The body **records the call it is checking**. That is correct for
its actual caller — `POST /api/detect` asks once, immediately before running, and the
recording is what makes the limit work.

But it means **asking whether you may run is indistinguishable from running**. A
pre-flight check calling `check_rate_limit()` would consume the run slot it was reporting
on. The user would see *"you may run"*, press Start, and get a 429 — **caused entirely by
the check that told them they could.**

Worse: it would have looked correct in casual testing. The first click works, and the
failure only appears on the second click within thirty seconds.

**The invariant** — a non-mutating twin, `middleware.py:79-81`:

```python
def peek_rate_limit(storm_id: str) -> float:
    """Seconds until the next run is allowed. 0 = allowed now. Does not record."""
    return max(0.0, RATE_LIMIT_SECONDS - (time.time() - _pipeline_calls.get(storm_id, 0)))
```

It also returns something **more useful than a boolean** — the wait in seconds — which is
what the `block` finding puts in front of the user.

**How it is held.** `TestPeekRateLimit` (`test_preflight.py:53-74`), three tests: fresh
storm returns 0, a recent run returns a wait inside the window, and
`test_peek_does_not_mutate` asserts `_pipeline_calls` is byte-identical after a peek.

### A6.4 Invariant 3 — never probe the provider

**The trap.** *"Is there enough token budget left?"* has an obvious implementation: ask
the API. **The obvious implementation spends tokens, on every Run click, to check whether
there are tokens.**

> A check that consumes the resource it protects is not a check. It is a leak with a user
> interface.

**The invariant** (`preflight.py:412-417`) — read this process's own accounting instead:

```python
# Never probe the Groq API itself: that spends the quota this check
# protects. Headroom is this process's own TPM accounting - a soft signal.
from backend.genai.llm import _bucket_for
total = sum([await _bucket_for(GROQ_MODEL, key).headroom() for key in GROQ_API_KEYS])
```

And then — the part that makes it *honest* rather than merely cheap — **the limitation is
stated in the finding itself**: *"(Process-local accounting; other clients are
invisible.)"*

**A soft signal presented as a soft signal is useful. The same signal presented as
authoritative is a liability the first time someone else is using the key.**

### A6.5 The fourth one — admitting what is *not* read-only

Version one's docstring claimed the module never writes. **It was false**, and the way it
was false is instructive.

`_system_findings()` calls `health_collector.run()`. That is not a status-flag lookup — it
**loads all six LightGBM checkpoints** and **counts every ChromaDB collection**. And
ChromaDB rewrites its own segment files on a pure read: **11 git-tracked files touched per
call**, including `chroma.sqlite3`.

So the module that promised to change nothing was dirtying eleven tracked files and
burning **~9.7 seconds** on every click of the button whose entire purpose was to save the
user eighty.

Two things were wrong, and both were fixed:

**The behaviour** — TTL cache plus lifespan warm-up (`preflight.py:359-373`,
`app.py:69-90`):

```python
HEALTH_TTL_S = 30

def health_snapshot(force: bool = False) -> dict:
    global _health_cache
    now = time.time()
    if not force and _health_cache and now - _health_cache[0] < HEALTH_TTL_S:
        return _health_cache[1]
    checks = health_collector.run()
    _health_cache = (now, checks)
    return checks
```

```python
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from backend.preflight import health_snapshot
    try:
        await asyncio.to_thread(health_snapshot, True)
    except Exception as exc:   # a warm-up must never stop the app from serving
        log.warning("preflight health warm-up skipped: %s", exc)
```

`asyncio.to_thread` matters: `health_collector.run()` is synchronous and blocking, and
calling it directly in the lifespan would stall the event loop for ten seconds during
startup.

**Measured first click after this change: 0.31 s.** (Down from 9.7 s.)

**The claim** — the docstring now scopes its promise precisely (`preflight.py:12-17`):

> That is a claim about the storm caches only, not whole-module purity. `_system_findings()`
> calls the health collector, which loads the six ML checkpoints and counts every Chroma
> collection - and Chroma rewrites its own segment files even on a pure read.

**The lesson is the second fix, not the first.** A comment that overstates a guarantee is
worse than no comment: the next person reads *"never writes"*, trusts it, and builds on a
property that does not hold. A precisely scoped claim — *"read-only for the storm caches,
not overall, and here is exactly why"* — is one that stays true and can be relied on.

`TestHealthSnapshot` (`test_preflight.py:323-356`) pins both the TTL reuse and that
`force=True` bypasses it.

### A6.6 What must never be "fixed"

Four regressions that would each be **silent** — the code would still look correct:

| Regression | Consequence |
|---|---|
| Adding `check_rate_limit()` back to the preflight handler "for consistency with `detect_storm`" | **The most likely future regression.** It makes the two handlers look symmetric and destroys the feature |
| Restoring a per-call `health_collector.run()` | Puts back both ~9.7 s and the writes, on every click |
| Removing the `None` assignment after a stale-epoch finding | The finding stays visible, so the code looks right — but the vetoed source flows back into the physics rules |
| Reordering `_cache_findings` so the epoch check is not last | It can no longer veto sources the rules already consumed |

The first two are carried as standing warnings in `AGENTS.md:191-193`; all four are in
`docs/preflight/11-open-issues.md §11.7`.

---

## A7 · Advisory, never blocking

### A7.1 The behaviour

**Even a `block` finding leaves `Start run` enabled** (`Dashboard.jsx:330`). The rate
limiter means the run *will* be rejected with a 429 — the panel says so in words, and lets
you do it anyway.

**And if the pre-flight check itself fails for any reason, the gate silently disappears
and the run starts directly** (`Dashboard.jsx:582-585`):

```js
.catch(() => {
  setGate(null)
  startRunner(runner)
})
```

The same fall-through exists one layer down, inside the pure function: `gateDecision`
returns `{action:'run'}` for `null`, `undefined`, or any response without a `findings`
array (`preflight.js:31`). **Two independent layers both fail open.**

### A7.2 Why — two separate arguments

**The alternative:** refuse to run when there is a `block` finding. It is the
safer-*sounding* choice, and in a regulated production system it might be right.

**Product argument.** This is a demo tool built for a live presentation. A gate that fails
closed means a bug in a diagnostic can cost the entire demo. **The failure mode of
blocking is strictly worse than the failure mode of warning.**

**Principled argument.** The operator has context the check does not. *"Rate limited, wait
22 s"* is information; deciding on their behalf that they may not proceed is not safety,
it is presumption. **The check's job is to inform the commitment, not to own it.**

> **A diagnostic that can break the thing it diagnoses is worse than no diagnostic.**

### A7.3 The clean seam

The whole feature is **additive**. Delete `preflight.py`, the route, and the gate, and the
product returns to *exactly* its prior behaviour. Nothing in the pipeline was modified:

- **No new pipeline stage**, no schema change, no new WebSocket event — which mattered,
  because `TestStreamEventContract` pins `pipeline.complete` as the last event of a run.
- **No new dependency**, backend or frontend.
- **One new module, one new route, one new helper, one new component, one new pure
  function.**
- **Two data files committed** (44 KB) and two directories gitignored.

**That is what "without a full rebuild" is really asking for — not a line count, but a
clean seam.**

---

# TIER B — features perfectly correlated with the topic

These are not the answer to the brief. They are the **same two principles applied to the
rest of the product**, and they are what makes the Round 2 submission read as a coherent
design position rather than one bolted-on panel.

## B1 · The five-layer console rail

`Dashboard.jsx:623-647`, `:651-686`; panels in `panels.jsx`.

### What it is

The console is a left rail of ten entries, one per pipeline layer plus the operational
surfaces, and **one panel visible at a time**:

| Rail entry | Layer | Badge |
|---|---|---|
| Run control | — | — |
| Detection | L1 | `G5` when detected |
| Impact (ML) | L2 | `±` when a prediction exists |
| Pipeline stream | — | live event count |
| Advisories | L3 | advisory count |
| Verifier | L4 | correction count, amber when non-zero |
| Provenance | L5 | trace count |
| Knowledge base | RAG | — |
| Ask an agent | RAG | — |
| System health | — | red dot when degraded |

### Why it is correlated with the PS

**The rail is the summary layer and the panel is the detail layer.** The badge is the
tally, the panel is the evidence — the same shape as the pre-flight panel's pills and
`<details>`, applied to an entire console.

Before the Round 2 rebuild (`df3f221`), the console was one scrolling page that **opened at
Layer 3** and showed three of the five pipeline layers not at all, despite their data
already arriving in `PipelineResult`:

- `cv_event` was fetched and dropped, so CV detection had no UI at all
- `impact_prediction` rendered as `JSON.stringify` in a `<pre>`
- `provenance_traces` — **the most-repeated claim in the entire project** — was never
  rendered anywhere

That is the *"too much, all at once"* failure mode of §A4.1, in its purest form: a single
page carrying everything, so nothing was legible and the most important layers were
invisible.

### Two details worth naming

**An absent panel says *why* it is absent** (`panels.jsx:21-25`, and every panel's empty
state). *"Nothing rendered"* and *"the layer did not run"* look identical otherwise, and
only one of them is a bug. So:

> Layer 1 has not run. Detection output appears here once a storm is replayed — nine
> deterministic threshold steps over the coronagraph frames, fused with the NASA physics
> feeds. No model weights, no RNG.

**Live hydration** (`Dashboard.jsx:519-522`). Layers 1 and 2 finish within the first
couple of seconds of a 70-second run. Without hydration their panels sat empty for the
remaining ~68 s of a run that had *already computed them*. The stream's
`pipeline.stage / completed` events now populate `live.cv_event` and
`live.impact_prediction` immediately, and the persisted result overwrites them at the end
(`:600-601`). **Disclosure follows availability, not completion.**

---

## B2 · The verifier surface — proposed vs enforced

`backend/genai/verifier.py`, surfaced at `panels.jsx:282-355` and `Dashboard.jsx:236-254`,
`:72-77`.

### Why it is correlated with the PS

**This is a conflict check with the same shape as A2, one layer downstream.** Two sources
describe what an operator should do: the language model, and the authoritative rulebook.
When they disagree, the disagreement is **surfaced with both sides visible** instead of
being silently resolved.

| | Pre-flight conflict engine (A2) | Verifier (B2) |
|---|---|---|
| Sources compared | Two data feeds | Model output vs rulebook constant |
| Tolerance | A published physical error bar | An exact allowlist |
| When | Before the commitment | During the run |
| On disagreement | Reports it, changes nothing | **Rewrites the value**, records both sides |
| Disclosed as | Finding in the gate panel | Correction row + live stream event |

The rule tables are hard constants, not model outputs (`verifier.py:32-75`): ICAO NAT HF
bands `{3, 5, 8, 11, 17}` MHz, reroute latitude thresholds `{G3: 78°N, G4: 70°N, G5: 60°N}`,
NERC TPL-007-4 Appendix B GIC step keywords, and the GMDSS distress/DSC frequency set.

### The four disclosure depths

The same finding is available at four increasing depths — a textbook progressive
disclosure ladder:

1. **Rail badge** — `Verifier · 2`, amber (`Dashboard.jsx:629`)
2. **Pill on the advisory card** — `verifier: passed_with_corrections` (`Dashboard.jsx:215-219`)
3. **Corrections box on the card** — `field` · proposed → corrected to · reason
   (`Dashboard.jsx:236-247`)
4. **The full verifier table** — every check across every advisory, with a
   `Proposed / Enforced / Reason` column set and blocked rows highlighted
   (`panels.jsx:326-352`)

Plus a **fifth, in time**: blocked checks stream live as they happen
(`Dashboard.jsx:74-77`), rendered as
`hf_band: 21 REJECTED → corrected to 5` rather than a blank row.

### Two honesty details

**`not_applicable` is not `passed`** (`verifier.py:314-322`, `panels.jsx:319-324`):

> No rule in the engine covers these advisories, so nothing was checked. That is reported
> as `not_applicable` rather than as a pass — *"every check succeeded"* and *"there were no
> checks"* are different claims.

**Passed checks are named, not just counted** (`Dashboard.jsx:249-254`). When nothing was
corrected, the card lists *which fields* were checked, so silence is legible as *"checked
and fine"* rather than *"not checked"*.

---

## B3 · The provenance chain, gaps rendered as gaps

`console.js:36-67` (pure), `panels.jsx:359-412` (render).

### Why it is correlated with the PS

Two reasons.

**Progressive disclosure of an audit trail.** The summary is a pill — `6/6 steps` — and the
evidence is the chain beneath it: every step with its `ref`, its confidence, and its CI
level where one exists.

**A gap is a finding, not an omission.** `chainSteps()` normalises whatever the backend
sent into the six canonical steps — `raw_data → detection → impact → retrieval → verifier
→ output` — and **a missing step still occupies its slot**, rendered `is-missing` with
*"not recorded"*:

```js
/**
 * A missing step is rendered as missing rather than skipped — "5 of 6" is a
 * finding, and a chain that silently drops a link looks complete when it isn't.
 * Steps the backend emits outside the canonical six are appended rather than
 * discarded, so a future 7th step is visible the day it ships.
 */
```

That is the same instinct as [A3](#a3--the-relevance-layer--veto-and-demotion): **the
absence of evidence is itself information, and hiding it produces a display that looks
complete and is not.** The completeness pill turns amber the moment `present !== total`
(`panels.jsx:389`).

An unknown seventh step is **appended rather than discarded**, so a future backend change
is visible on the day it ships instead of silently vanishing.

Asserted at `data.test.mjs:95-115`: canonical order regardless of arrival order, gaps
occupying their slot, `null`/`{}` not throwing, and an extra step surfacing without
counting toward `present`.

---

## B4 · Quantile interval bars

`console.js:80-104` (pure geometry), `panels.jsx:184-271` (render).

### Why it is correlated with the PS

**A median alone is a guess presented as a fact; the band is what makes it a forecast an
operator can act on.** This is disclosure of *uncertainty* — showing the reader how much to
trust the number at the same moment they read it, rather than in a footnote.

It is also a three-layer ladder in miniature:

1. **The headline** — `12.8 m`, with a `95% CI` marker beside the label
2. **The band** — a CSS bar showing q0.025 / q0.500 / q0.975 with the bounds anchored to
   the band's own edges
3. **The raw model output** — behind a `<details>` labelled *"raw model output"*
   (`panels.jsx:265-268`)

Before Round 2 this entire block was `<pre>{JSON.stringify(prediction, null, 2)}</pre>` —
the project's most defensible ML claim rendered as an unstyled blob.

### Two correctness details, both asserted

**`typeof`, not `Number()`** (`console.js:82-84`). `Number(null)` and `Number('')` are both
`0`, so a missing quantile would coerce into a bar drawn at a **real, measured zero**. The
function returns `null` instead, and the panel renders *"No interval — the model returned
nothing usable for this metric."*

**The three values are sorted, not trusted** (`console.js:86`). `inference.py` already
enforces monotonicity, but **quantile crossing is a real failure mode of independently
trained quantile models**, and a crossed pair must not invert the bar. Asserted at
`data.test.mjs:122-125`.

The bounds are anchored to the band rather than spread across the track, because a bound
printed at the far edge of the axis reads as the axis maximum — which for a 0–1 probability
is a different number entirely (`panels.jsx:206-215`).

---

## B5 · Citation deep-links to the cited page

`frontend/src/citation.js`, `backend/app.py:245-268`, rendered at `Dashboard.jsx:140-161`.

### Why it is correlated with the PS

**It is the deepest rung of the disclosure ladder the product has.** Advisory summary →
numbered action → its citation → **the actual page of the actual regulatory PDF**. Four
layers, each one deliberate click.

A citation that is a bare filename in a `<span>` asks the reader to take the grounding on
trust. A citation that opens `nat_doc_007_2025.pdf` at page 42 lets them check it in one
click — which is the difference between claiming an audit trail and shipping one.

### How it works, with no new dependency

`source_ref` now carries a page (`"nat_doc_007_2025.pdf p.42"`). `citationPath()` parses
the filename and page and returns `/api/kb/source/{file}#page=42`. **Chrome's and Firefox's
built-in PDF viewers honour `#page=N` natively**, so a plain `<a>` is the entire feature —
no PDF.js, no new dependency in a frontend with three.

The blocker was upstream, not in the UI: `chunk_document()` joined every page with `"\n\n"`
before chunking, so **the page number was destroyed at ingest time** and no frontend work
could have recovered it. Ingest now chunks page by page and carries the number through to
Chroma.

### Three safety properties

- **A ref naming no document stays plain text** rather than becoming a dead link
  (`citation.js:27`, `Dashboard.jsx:143-149`). A bare regulation code like *"ICAO NAT Doc
  007"* is not a file.
- **Path traversal is structurally impossible** (`app.py:220-239`). The filename is only
  ever a **key into an allowlist** globbed from `DATA_DIR` at startup — never part of a
  filesystem path. Same posture as `validate_storm_id`: decide against a known-good set
  rather than try to sanitise attacker-controlled input.
- **The knowledge-base panel lists every citable document** (`panels.jsx:416-456`), so a
  live link is distinguishable from a dead one *before* you click it.

The parsing lives outside `api.js` for the same reason `gateDecision` does — `api.js` reads
`import.meta.env`, which only vite defines. Asserted at `data.test.mjs:64-88`.

---

## B6 · The live stream and the Stop control

`Dashboard.jsx:97-130` (stream), `:561-564` and `:423-427`, `:695-702` (stop).

### Why it is correlated with the PS

**Progressive disclosure in time.** Once the commitment is made, the run discloses itself
stage by stage — retrieval, generation, each deterministic check — instead of going dark
for 70 seconds and dumping everything at the end.

Three properties earn it a place here:

**Structured events are composed, not blanked** (`Dashboard.jsx:72-87`). `verifier.check`
and `advisory.verified` carry no `message` field — they are structured — and they are the
two most interesting lines in a run. A blocked check renders as
`hf_band: 21 REJECTED → corrected to 5` rather than an empty row.

**Elapsed clocks, not wall time** (`console.js:114-118`, rendered `:120`). *"Where did the
80 seconds go"* is the question a reviewer actually asks, and a wall clock makes you do the
subtraction yourself. Negative values clamp to `0:00` rather than rendering `-0:03`.

**The Stop control** (`Dashboard.jsx:423-427`, `:695-702`). The source comment states the
connection to the PS directly:

```jsx
{/* The whole pre-flight feature exists because 80s is expensive to
    commit to. Not being able to stop it once started was the same
    problem one step later. */}
```

It is reachable from **every** panel, not just the one you started from — a run auto-opens
the stream, and that is exactly where you are standing when you decide eighty seconds was
a mistake.

**The stream is narrated to screen readers** via `role="log" aria-live="polite"`
(`Dashboard.jsx:115`) — without it, an 80-second run is 80 seconds of silence.

---

# 7 · Traceability matrix

Every requirement in the brief, the feature that discharges it, and the artefact that
proves it.

| Req | Discharged by | Mechanism | Proof |
|---|---|---|---|
| **R1** Show detail gradually | A4 | Three layers: consequence sentence → severity pills + estimate → `<details>` evidence. Headline is `findings[0]` of a severity sort — correct **by construction** | `data.test.mjs:29-51`; `dashboard.css:364-372` |
| **R1** (extended) | B1, B2, B3, B4, B5, B6 | The same summary-then-evidence shape on the console rail, the verifier, provenance, uncertainty, citations, and the run stream | `data.test.mjs:90-145` |
| **R2** Detect conflicts early | A2 | Six cross-source physics rules with tolerances derived from published error bars, run **before** the pipeline, using the **production parsers** | `TestConflictRules` (11), `TestStubDonkiRules` (5), `test_stubs_are_internally_consistent` |
| **R2** (precision) | A3 | Stale-epoch veto withholds wrong-epoch sources; stub-replay demotion drops unreachable conflicts to `info` and says why | `TestStaleEpoch` (5), `TestStubReplayDemotion` (2) |
| **R2** (breadth) | A5 | Seven fallback-prediction findings + quota + lockout + per-dependency health, each stated as a **consequence** | `TestCacheFindings` (4), `test_rate_limited_blocks` |
| **R3** Before the commit | A1 | `preflight → confirm → execute`; no runner can bypass it; 0.31 s measured against a 65–80 s commitment | `test_schema_and_ready_on_real_repo`; live `uvicorn` verification |
| **R3** (trust) | A6 | Four observer-effect traps closed: stat-before-parse, `peek_rate_limit`, never probe the provider, TTL-cached health | `test_read_only_no_mkdir_no_fetch`, `TestPeekRateLimit` (3), `TestHealthSnapshot` (2) |
| **R3** (posture) | A7 | Never hard-blocks; fails open at two independent layers | `Dashboard.jsx:582-585`; `data.test.mjs:25-27` |
| **R4** Substantial, not a rebuild | A7.3 | One module, one route, one helper, one component, one pure function. **No new dependency. No pipeline change. No schema change.** Clean seam: delete it and the product reverts exactly | `git show --stat a18490b`, `2ea377a` |

---

# 8 · Evidence

## 8.1 Live output, executed on this tree

`asyncio.run(run_preflight(storm_id))` against the working tree, 2026-08-23:

**`2024-10-G4`** — `ready: true`, `estimated_duration_s: 70`, 3 findings

| Severity | id | Title |
|---|---|---|
| **WARN** | `cv_stub_replay` | Results will replay canned data, not this storm's imagery |
| INFO | `flare_cache_missing` | GOES XRS flare cache missing |
| INFO | `l1_cache_missing` | DSCOVR L1 solar wind cache missing |

**`2024-05-G5`** — `ready: true`, `estimated_duration_s: 70`, 4 findings

| Severity | id | Title |
|---|---|---|
| **WARN** | `cv_stub_replay` | Results will replay canned data, not this storm's imagery |
| INFO | `flare_cache_missing` | GOES XRS flare cache missing |
| INFO | `l1_cache_missing` | DSCOVR L1 solar wind cache missing |
| INFO | `stub_donki_speed_mismatch` | **Reference CME speed is 65% off the DONKI record** |

**The two storms differ, and that is the single most important property of the panel.**
A gate that says the same thing every time is a cookie banner: people learn the shape and
click past it without reading. The G5's extra line is what proves the check is looking at
*this storm* rather than reciting a template.

The full detail behind that G5 line, verbatim from the live response:

> The committed reference for this storm says 2200 km/s; DONKI's CME analysis measures
> 1332 km/s. DONKI's own analyses spread by 10-20%, so a gap this wide means the reference
> severity and the observational record are not describing the same event speed.
> **Detection is replaying the stub for this run, so this source is never read and the
> disagreement cannot affect the output.**

That last sentence is appended automatically. **It is the panel demoting its own finding**
— see [A3.2](#a32--the-stub-replay-demotion).

Note also what is *absent*: no `donki_cache_missing` (the DONKI caches are committed), no
`alert_cache_missing`, no health findings, no quota findings. The check is reporting the
true state of this tree, not a fixed template.

## 8.2 Test suites, executed on this tree

**`backend/tests/` — 308 passed in 96.12 s** (whole backend suite, no failures, no skips).

**`backend/tests/test_preflight.py` — 35 passed in 36.45 s.**

| Class | Tests | Pins |
|---|:--:|---|
| `TestPeekRateLimit` | 3 | The peek is non-mutating |
| `TestCacheFindings` | 4 | Existence prediction, and the read-only guarantee |
| `TestConflictRules` | 11 | Each rule fires above threshold, is silent below, skips missing inputs; stubs are self-consistent |
| `TestRunPreflight` | 2 | End-to-end schema against the **real repository**, and block behaviour |
| `TestStaleEpoch` | 5 | The wrong-epoch veto, **including withholding the source** |
| `TestStubDonkiRules` | 5 | The rule that fires on a clean checkout, against committed data |
| `TestStubReplayDemotion` | 2 | `warn → info` **and** the appended explanation |
| `TestHealthSnapshot` | 2 | TTL caching, and that `force` bypasses it |

Every class saves and restores its own global state (`_pipeline_calls`, `_health_cache`),
so the suite is order-independent despite touching module-level caches.

**`frontend` — `npm test` (`node src/data.test.mjs`) passing:**

```
ok — data.test.mjs
ok — preflight gate decision
ok — citationUrl
ok — console panels
```

## 8.3 The test property that matters most

The suite's own blind spot is documented rather than hidden. Version one had **25 passing
tests covering the conflict rules, and every conflict rule was unreachable on a fresh
clone** ([A2.6](#a26--what-went-wrong-and-how-it-was-caught)).

> **Unit tests verify a function against inputs you supply. They cannot verify that
> anything supplies those inputs in production. A function tested only against fabricated
> inputs has been tested as a calculator, not as a feature.**

What closed it: `test_schema_and_ready_on_real_repo` runs the **real entry point against
the real repository** with no `tmp_path`, no fixtures and no fabricated inputs; and
`TestStubDonkiRules` runs against the **committed** DONKI caches rather than dictionaries
written in the test file. The suite passes **with and without** the gitignored `l1/` and
`xrs/` caches — which is what makes it meaningful both on a developer machine that has
them and on a fresh clone that does not.

Three questions worth asking of any data-dependent test suite:

1. Does anything run the **real entry point** against the **real repository**?
2. **Would the suite still pass if the feature were inert?** For version one, the answer
   was yes — and that is the whole failure in one sentence.
3. Does it pass on a **clean clone**, not on a machine that has been developing the
   feature for three hours?

## 8.4 Timeline

One afternoon, 2026-08-22 IST. **66 minutes from plan to corrected feature.**

| Time | Commit | What happened |
|---|---|---|
| 15:47 | `5ab726e` | **The plan.** 155 lines: schema, findings catalogue, the conflict rules with thresholds, and **all three read-only constraints identified before any code was written** |
| 16:06 | `2ea377a` | **Version one.** `preflight.py` (~317 lines), the route, `peek_rate_limit()`, the gate. 270 tests, 25 new. Verified live |
| ~16:10 | — | **Review.** *"What does this return on a machine that has just cloned the repository?"* Answer: the same four findings, both storms, forever |
| 16:53 | `a18490b` | **The fix.** `+1581 / -42` across 11 files. DONKI caches committed, stale-epoch rules, stub-replay demotion, the false docstring corrected and the 9.7 s behind it removed, disclosure rebuilt, `gateDecision()` extracted. 284 tests, 35 in `test_preflight` |
| 17:42 | `6e040e5` | Plan file rewritten into the next block of work; the pre-flight task closed |
| 2026-08-22 | `9b19b85` | `docs/preflight/` — 13 files, ~2160 lines, the complete feature record including the unflattering parts |
| 2026-08-23 | `df3f221` | The console rebuilt as a sidebar-navigated panel layout — [B1](#b1--the-five-layer-console-rail) through [B4](#b4--quantile-interval-bars) |

**What the shape of that timeline says.** Two commits, 47 minutes apart, and the second is
larger than the first. That is not a sign the first was careless — it was planned well,
tested, and verified live. **It is a sign that the review asked a different question than
the tests did.** The tests asked *"does this compute correctly?"*. The review asked *"does
this ever run?"*. Both questions are necessary. Only one of them was automated.

---

# 9 · Boundaries — what is *not* claimed as Round 2 work

Stated explicitly so the submission's scope is unambiguous, and so nothing here is
mistaken for a Round 2 capability.

**Round 1 MVP, unchanged in substance:**

| Capability | Why it is not Round 2 |
|---|---|
| The five-stage pipeline (CV → ML → agents → verifier → delivery) | Pre-existing. Round 2 changed **when and how** its layers disclose ([B1](#b1--the-five-layer-console-rail)), not what they do |
| The deterministic CME detector, DONKI/GOES/DSCOVR fusion | Pre-existing. Round 2 **reads** its caches without running it |
| The six LightGBM quantile models | Pre-existing. Round 2 gave the intervals a shape ([B4](#b4--quantile-interval-bars)) |
| The four RAG industry agents and the ten guardrail layers | Pre-existing |
| The verifier rule tables themselves | Pre-existing. Round 2 gave them a dedicated panel ([B2](#b2--the-verifier-surface--proposed-vs-enforced)) |
| Rate limiting, security headers, input validation, CORS, WS origin checks | Pre-existing. Round 2 added the **non-mutating twin** of one function |
| Prometheus metrics, three-tier health checks | Pre-existing. Round 2 **consumes** them ([A5.3](#a53--system-health--_system_findings), [A5.4](#a54--duration-estimate)) |

**In the Round 2 time window but not part of this solution:**

The backend `refactor(*)` series, the Next.js → Vite migration, the Railway deployment,
the CI ruff pin, and the README rewrite all landed on 2026-08-22/23. They are
infrastructure and delivery work. **They are not Challenge #1001 and are not claimed as
such.**

**Correlated but marginal, and therefore not given a Tier B entry:**

- **`AskBox`** (`AskBox.jsx`) — lives in a collapsed `<details>` at the foot of each
  advisory card and inherits the industry and advisory id from the card, so it never has
  to ask *"which agent?"*. Structurally it is one more disclosure rung, but the feature's
  purpose is conversation, not conflict or commitment.
- **Health polling and `degraded ≠ unreachable`** (`api.js:33`, `Dashboard.jsx:477-482`) —
  feeds [A5.3](#a53--system-health--_system_findings). A supporting fix, not a feature.

**Never built, and deliberately so:**

Auto-remediation from the panel, persistence of findings across sessions, alerting on
findings, and threading pre-flight findings *into* the run so the resulting advisory is
annotated with the degradations that were predicted. The last is the natural next feature
and was an explicit, user-confirmed scope decision in the plan:

> Scope decision (user-confirmed): **preflight only** — no provenance threading through
> `detect()`/`StormEvent`; that is the natural follow-up, deferred.

**Today the panel's knowledge is discarded the moment you press Start.**

---

# 10 · Known limits

Nothing here is hidden elsewhere in the pack. If a reviewer asks about coverage, volunteer
this before they find it.

## 10.1 Coverage is thinner than "six conflict rules" sounds

On a clean checkout, **exactly one rule can fire**.

| Rule | Needs | Fires on a fresh clone? |
|---|---|---|
| `stub_donki_speed_mismatch` | stub + DONKI | **Yes** |
| `stub_donki_arrival_mismatch` | stub + DONKI | Could — silent on both storms (1.8 h and 7.6 h, both inside the 12 h ballistic tolerance) |
| `speed_disagreement` | DONKI + L1 | No — L1 is gitignored and real-time only |
| `arrival_eta_mismatch` | DONKI + L1 | No — same |
| `bz_northward_strong_g` | stub + L1 | No — same |
| `flare_r_mismatch` | stub + GOES XRS | No — XRS is gitignored and real-time only |

This is handled *honestly* — the stale-epoch rules report the wrong-epoch condition rather
than dressing a date-range error up as a physics finding, which is the right behaviour. But
the accurate headline is: **one rule that fires on a clean checkout, one that could, and
four that need data a fresh clone cannot obtain from the upstream endpoints at all.**

## 10.2 Discriminating power is two storms and one signal

The panel differs between G4 and G5 by exactly one line — the 65%-vs-12% speed drift. That
single difference is doing all the work of proving the check reads *this storm* rather than
reciting a template.

It is enough to demonstrate the mechanism. **It is not enough to claim the check has been
exercised across a range of failure modes on real data.**

## 10.3 A live bug — `_stale_epoch` truncates asymmetrically

`preflight.py:82`:

```python
gap_days = abs((ts - storm_dt).days)
```

`timedelta.days` truncates toward negative infinity, so `abs()` of it gives a different
answer depending on the **sign** of the gap:

| Direction | `(ts - storm).days` | `abs(...)` | Fires? |
|---|---|---|---|
| Cache 7.5 days **after** the storm | `7` | 7 | no |
| Cache 7.5 days **before** the storm | `-8` | 8 | **yes** |

The same physical gap produces opposite verdicts. The fix is one line:

```python
gap_days = abs((ts - storm_dt).total_seconds()) / 86400.0
```

**Practical impact is small** — real wrong-epoch caches are months out, not seven and a
half days — but it is a correctness bug in the rule whose whole job is to prevent other
rules from producing wrong findings. It is listed rather than fixed silently because this
document is a record of the feature's real state.

## 10.4 The duration estimate ignores the main cause of slowness

`_estimate_duration()` is a running mean with a 70 s default. It does not incorporate the
one factor most likely to make the *next* run slow: exhausted token budget, which causes a
**stall** rather than a failure.

The panel does report low quota as a separate `warn` that explicitly says the run will
stall — but **the two are not connected**. The estimate still says *"est ~70s"* next to a
warning that it will not be 70 s. Folding quota state into the estimate is the obvious
improvement.

## 10.5 Quota headroom is process-local

A second process, a teammate's laptop, or a deployed instance sharing the same key is
**invisible** to the check. The finding says so in its own text, which is the right
mitigation, but the limitation is real: **the panel can report healthy headroom while the
key is in fact saturated by someone else.**

## 10.6 Health findings can be up to 30 seconds stale

`HEALTH_TTL_S = 30`. A dependency that degrades within that window will not appear until
the cache expires. A deliberate trade — the alternative is ~9.7 s and eleven rewritten
files per click — but a run started at second 29 of the TTL is being gated on information
from the beginning of it.

## 10.7 Pre-flight cannot be run without entering the gate flow

There is no *"check this storm"* button. Pre-flight runs only as a side effect of clicking
Run, so you cannot inspect conflicts without entering the confirmation flow and cancelling.
The endpoint is a plain `GET` and would support this in one button.

## 10.8 The rules are heuristics, not a constraint engine

Six hand-written physics rules with fixed tolerances — the right shape at this scale, and
**the thresholds are named constants with stated derivations precisely so they are tunable
when real data says otherwise.** But this is not a general constraint solver over the
storm's physical state, and it should not be described as one.

---

# 11 · File map

Everything the Round 2 solution consists of, and nothing else.

## Backend

| Path | Lines | Role |
|---|---:|---|
| `backend/preflight.py` | 459 | **The entire check** — cache prediction, six conflict rules, stale-epoch veto, stub-replay demotion, quota, health |
| `backend/app.py:271-287` | 17 | `GET /api/preflight/{storm_id}` — validation gates minus every mutating call |
| `backend/app.py:69-90` | 22 | Lifespan health warm-up, so no user pays the ~10 s cold probe |
| `backend/middleware.py:79-81` | 3 | `peek_rate_limit()` — the non-mutating twin of `check_rate_limit()` |
| `backend/tests/test_preflight.py` | 356 | 35 tests across 8 classes |
| `backend/data/cached/donki/*.json` | 44 KB | The two committed 2024 CME records the rules run against |
| `.gitignore` (`l1/`, `xrs/`) | — | The decision *not* to commit 8 MB of wrong-epoch data, with the reasoning and regeneration commands inline |

## Frontend

| Path | Lines | Role |
|---|---:|---|
| `frontend/src/preflight.js` | 47 | `gateDecision()` — the pure decision layer, the only branching logic in the gate |
| `frontend/src/Dashboard.jsx:288-356` | 69 | `PreflightPanel` — the three-layer panel |
| `frontend/src/Dashboard.jsx:566-594` | 29 | `requestRun` / `confirmGate` — the gate itself |
| `frontend/src/Dashboard.jsx:363-441` | 79 | `StormRow` + `RunPanel` — pre-commitment context and run controls |
| `frontend/src/api.js:44` | 1 | `getPreflight()` |
| `frontend/src/dashboard.css:345-388` | 44 | Panel styling, with the layer-1 sizing rationale in a comment |
| `frontend/src/data.test.mjs:20-62` | 43 | Node asserts over `gateDecision()` |

## Tier B surfaces

| Path | Lines | Role |
|---|---:|---|
| `frontend/src/panels.jsx` | 456 | Detection, Impact, Verifier, Provenance, Knowledge-base panels |
| `frontend/src/console.js` | 118 | `chainSteps()`, `intervalGeometry()`, `elapsed()` — pure, asserted |
| `frontend/src/citation.js` | 34 | `citationPath()` — pure, asserted |
| `backend/app.py:220-268` | 49 | KB source allowlist + `#page=N` inline serving |

## Documentation

| Path | Role |
|---|---|
| `docs/PS_solution/main_features.md` | **This document** — the Round 2 feature specification |
| `docs/preflight/` (13 files, ~2160 lines) | The full narrative record: the problem, fundamentals for a non-technical reader, the operator's view, internals, the conflict rules with the physics behind every threshold, the read-only invariants, what shipped broken, design decisions and roads not taken, testing and its blind spot, the commit timeline, open issues, glossary |
| `docs/dashboard_features.md` | Feature inventory and gap analysis of the console, written as *"the document a hostile reviewer would otherwise write for us"* |

---

# 12 · Corrections to older documents

Recorded because the tree is the authority, and a reviewer comparing our docs to our
console will find these.

| Document | Says | Tree says |
|---|---|---|
| `README.md:494`, `PRODUCT_BRIEF.md:100`, `TECHNICAL_DEEP_DIVE.md:288-289` | Buttons read `Run` / **`Run anyway`** / `Cancel` | **`Start run`** / `Cancel`. `Run anyway` was deliberately removed at `a18490b` — see [A4.6](#a46--one-button-label) |
| `README.md:475`, `TECHNICAL_DEEP_DIVE.md:249` | *"The four conflict rules"* | **Six** cross-source rules, plus two stale-epoch veto rules |
| `TECHNICAL_DEEP_DIVE.md:223` | `preflight.py` is *"~300 lines"* | **459 lines** |
| `TECHNICAL_DEEP_DIVE.md:993` | `test_preflight.py` has **25** tests | **35**, verified passing |
| `docs/preflight/09-testing.md §9.7` | *"307 passed / 1 skipped"*, with a noted `test_retrieval.py` chromadb flake | **308 passed, 0 skipped, 0 failures** on this tree — the flake did not reproduce |
| `docs/dashboard_features.md` T1-1/T1-2/T4-1, T2-1, T3-1, T3-4, T6-1 | Provenance, detection, ML intervals, the `completed` map, a stop control, health polling and card accessibility are all missing | **All shipped at `df3f221`.** That document was written at `9b19b85`, one commit earlier |

---

# 13 · Finding-id reference

Every id the endpoint can emit, in the order `run_preflight` produces them.

| id | Severity | Source | Meaning |
|---|:--:|---|---|
| `rate_limited` | block | quota | A run for this storm is inside the 30 s lockout; the detail names the remaining wait in seconds |
| `no_groq_key` | warn | quota | `GROQ_API_KEY` / `GROQ_API_KEYS` is empty; the run falls back to template advisories |
| `groq_tpm_low` | warn | quota | Process-local TPM headroom below 4000; the run will **stall**, not fail |
| `cv_stub_replay` | warn | cache | No preprocessed frames; `detect()` returns the stub wholesale and reads none of the other sources |
| `donki_cache_missing` | info | cache | Absent or unreadable; live fetch will be attempted, else stub speed/width |
| `donki_no_match` | info | cache | Present, but no CME record inside the storm window |
| `flare_cache_missing` | info | cache | Absent or unreadable; live fetch will be attempted, else R0 |
| `l1_cache_missing` | info | cache | Absent or unreadable; live fetch will be attempted, else 400 km/s / Bz 0 |
| `l1_fallback_data` | warn | cache | Present and parseable, but holds no usable reading — the placeholders **look like measurements** |
| `alert_cache_missing` | info | cache | The run proceeds with an empty alert text block |
| `l1_cache_stale_epoch` | warn | veto | The L1 cache is > 7 days from the storm date; **the source is withheld from every physics rule** |
| `flare_cache_stale_epoch` | warn | veto | Same for the GOES XRS cache |
| `stub_donki_speed_mismatch` | warn / info | conflict | Reference CME speed differs from DONKI's by > 25% |
| `stub_donki_arrival_mismatch` | warn / info | conflict | Reference arrival and DONKI's ballistic estimate are > 12 h apart |
| `speed_disagreement` | warn / info | conflict | L1 wind faster than launch (unphysical), or below 30% of launch (beyond plausible drag) |
| `arrival_eta_mismatch` | warn / info | conflict | DONKI's ballistic arrival and the L1-derived ETA are > 12 h apart |
| `bz_northward_strong_g` | warn / info | conflict | Northward Bz behind a G3+ severity — northward IMF does not drive strong storms |
| `flare_r_mismatch` | warn / info | conflict | No flare behind an R2+ scale (warn), or ≥ 2 R-levels off the reference (info) |
| `check_{name}_degraded` | warn | health | One per failing dependency check, stated as its **consequence for this run** |

**All six `conflict` rows are demoted `warn → info` when `cv_stub_replay` fires**, with the
reason appended to the detail — see [A3.2](#a32--the-stub-replay-demotion).

---

*Verified against `main` on 2026-08-23 by reading every referenced file and executing
`run_preflight()` for both storms, `pytest backend/tests/test_preflight.py` (35 passed),
and `npm test`. Every number that was measured says so; every limitation known at the time
of writing is in [§10](#10--known-limits).*
