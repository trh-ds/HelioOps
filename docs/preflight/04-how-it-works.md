# 4 — How it works

*Technical. Assumes you can read Python and JavaScript.*

---

## 4.1 Shape of the change

One module, one route, one helper, one component, one pure decision layer.
Nothing in the pipeline itself was modified.

```
backend/preflight.py             NEW    ~430 lines - the entire check
backend/middleware.py            +3     peek_rate_limit()
backend/app.py                   +40    GET route, lifespan warm-up
backend/tests/test_preflight.py  NEW    35 tests, 8 classes

frontend/src/preflight.js        NEW    47 lines - gateDecision(), pure
frontend/src/Dashboard.jsx       +130   PreflightPanel + the requestRun gate
frontend/src/api.js              +1     getPreflight()
frontend/src/data.test.mjs       +44    node asserts over gateDecision()
frontend/src/dashboard.css       +45    panel styling
```

`backend/data/cached/donki/*.json` (44 KB, two files) were committed so the
conflict rules have real data to run against on a clean checkout — see
[chapter 7](07-what-went-wrong-first.md).

## 4.2 The endpoint

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

It mirrors `POST /api/detect/{storm_id}` deliberately — same regex validation,
same 404 for a well-formed-but-unknown id — **minus every mutating call**. The
comment naming what was removed is load-bearing: the obvious "improvement" to
this handler is to make it consistent with its sibling by adding the rate-limit
check back, and that would silently break the feature.

## 4.3 Response schema

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
      "detail": "The committed reference for this storm says 2200 km/s; ..."
    }
  ]
}
```

**`id`** is stable and machine-readable. Tests assert on ids, never on prose,
so wording can be improved without touching a test.

**`severity`** is one of three, and each has a precise meaning:

| Severity | Means | Who produces it |
|---|---|---|
| `block` | The run **will be rejected right now** | Only the rate limiter |
| `warn` | The run will succeed but the result is compromised in a specific way | Stub replay, reachable conflicts, degraded health, no key, low quota |
| `info` | Worth knowing, will not change what you decide | Missing optional caches, demoted conflicts, small mismatches |

The discipline that keeps this useful: **`warn` is reserved for things that
change the meaning of the output.** A missing cache the run will simply
re-fetch is `info`. A source that disagrees with another source *and can reach
the result* is `warn`. The moment `warn` starts covering "something is slightly
unusual", the pills stop carrying information.

**`ready`** is `not any(severity == "block")`. It is advisory only — the
frontend never uses it to disable anything.

**`estimated_duration_s`** is the running mean of observed pipeline durations
from `backend.health._requester_metrics`, defaulting to 70 when nothing has run
yet.

## 4.4 Execution order — and why it is this order

```python
async def run_preflight(storm_id, base_dir=None):
    cfg  = STORM_CONFIGS[storm_id]
    base = Path(base_dir) if base_dir else BACKEND_DIR

    findings = list(await _quota_findings(storm_id))                  # 1
    cache_findings, stub, cme, flare, l1 = _cache_findings(cfg, base) # 2
    findings += cache_findings
    stub_replay = any(f["id"] == "cv_stub_replay" for f in cache_findings)
    findings += _conflict_findings(stub, cme, flare, l1, stub_replay) # 3
    findings += _system_findings()                                    # 4

    return {
        "storm_id": storm_id,
        "ready": not any(f["severity"] == "block" for f in findings),
        "estimated_duration_s": _estimate_duration(),
        "findings": findings,
    }
```

The order is not cosmetic:

1. **Quota first**, because it is the only source of `block` and needs no disk.
2. **Caches second**, because this stage is what *produces* `cme`, `flare` and
   `l1` — the parsed values the conflict rules consume. It also decides which of
   them are trustworthy enough to hand on at all.
3. **Conflicts third**, taking those values plus the `stub_replay` flag.
4. **System health last**, because it is the expensive one and is TTL-cached.

The `base_dir` parameter mirrors `detect()`'s so tests can point the entire
check at a `tmp_path` without patching a single module-level constant.

## 4.5 `_cache_findings` — stat, then parse, then veto

Three passes over the four caches, in a fixed order:

1. **Existence.** `Path.exists()` and a glob for the imagery. Every absent cache
   produces an `info` finding naming what the run will fall back to.
2. **Parse — only if the file exists.** The real ingestion parsers are used:
   `select_best_cme` + `cme_to_fields`, `fetch_and_classify_flare`,
   `fetch_l1_wind`. Reusing them is what makes the prediction trustworthy: the
   check cannot disagree with the run about what a file contains, because it is
   the same code path. Each is wrapped in `try/except` — an unreadable cache is a
   finding, never a 500.
3. **Epoch veto, last.** `_stale_epoch()` compares the first timestamp in the
   file against the storm date. Beyond `STALE_EPOCH_DAYS` (7) the source is
   reported as wrong-epoch **and set back to `None`**, so the conflict rules
   never see it. Running physics against a file from the wrong month produces a
   confident finding about instruments disagreeing when the real problem is a
   date range — a wrong answer stated well, which is worse than no answer.

The ordering comment in the source says exactly this:

```python
# Epoch check LAST, so it can veto sources the rules would otherwise use.
```

## 4.6 The frontend gate

`requestRun` replaces the direct call to the runner:

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

Both runners — `Run live (WebSocket)` and `Run batch (REST)` — go through the
same gate, and `runner` is carried through the gate state so confirming starts
the one you asked for.

## 4.7 `gateDecision()` — a pure function, on purpose

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

This is the only branching logic in the gate, and it lives in its own module so
`src/data.test.mjs` can assert it with plain node asserts — no vitest, no jsdom,
no new dependency in a repo whose frontend has exactly three runtime deps.

Two details worth noting:

- The sort is **most severe first**, and the headline is always `findings[0]`.
  That is the entire mechanism by which layer 1 states the worst thing.
- `rank()` sends unknown severities to the *end*:
  ```js
  const rank = sev => {
    const i = SEVERITIES.indexOf(sev)
    return i === -1 ? SEVERITIES.length : i
  }
  ```
  A naive `indexOf` returns `-1`, which sorts an unrecognised severity to the
  front and makes it the headline. If the backend ever adds a fourth severity,
  the current code shows it last; the naive version would have promoted it above
  `block`.

## 4.8 The health cost, and the TTL cache

`_system_findings()` calls `health_collector.run()`, which loads six LightGBM
checkpoints and counts every Chroma collection. Cold, that is **~9.7 seconds** —
on a panel whose entire purpose is to save the user eighty.

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

and it is warmed once at startup so no user ever pays it:

```python
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from backend.preflight import health_snapshot
    try:
        await asyncio.to_thread(health_snapshot, True)
    except Exception as exc:   # a warm-up must never stop the app from serving
        log.warning("preflight health warm-up skipped: %s", exc)
```

Measured first click against a live server after this change: **0.31s**.

`asyncio.to_thread` matters — `health_collector.run()` is synchronous and
blocking, and calling it directly in the lifespan would stall the event loop for
ten seconds during startup.

## 4.9 Quota, without spending quota

```python
# Never probe the Groq API itself: that spends the quota this check
# protects. Headroom is this process's own TPM accounting - a soft signal.
from backend.genai.llm import _bucket_for
total = sum([await _bucket_for(GROQ_MODEL, key).headroom() for key in GROQ_API_KEYS])
if total < TPM_LOW_THRESHOLD:   # 4000, ~one full advisory pass
    ...
```

The obvious implementation of "is there quota left" is to ask the provider. The
obvious implementation is wrong: the request costs quota, so the check degrades
what it measures every time it runs — and it runs on every Run click.

Instead it reads this process's own token accounting. The finding is explicit
about what that means, including the limitation:

> The run will not fail - it will STALL waiting for the rolling window to clear.
> (Process-local accounting; other clients are invisible.)

Both halves matter. Exhausted quota does not raise, it *queues*, which is why
"the run failed" would be the wrong warning. And a second process using the same
key is invisible here — stating that in the finding is cheaper and more honest
than pretending to a certainty the mechanism cannot deliver.

---

Next: [The conflict rules](05-the-conflict-rules.md).
