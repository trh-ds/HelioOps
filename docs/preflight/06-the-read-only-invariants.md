# 6 — The read-only invariants

*The part of the feature that is genuinely hard, and the part that is easiest to
break by accident later.*

---

## 6.1 Why "read-only" is not free here

A pre-flight check has one job: describe the state the run will find. The moment
it *changes* that state, it stops describing and starts interfering. It becomes
a thermometer that warms the water.

The problem is that this codebase is built out of components which, by
deliberate design, write on read. Not one of them is a bug. Each is a correct
answer to a different question, and each becomes a trap the moment something
read-only calls it.

Three of them are load-bearing enough to be invariants. A fourth is an honesty
requirement about the parts that could not be made read-only at all.

---

## 6.2 Invariant 1 — stat before parse

**The trap.** Every external client in HelioOps follows the project's stated
convention:

> cache hit → disk, miss → **fetch + write**, network failure → stale cache →
> hardcoded fallback

That means `fetch_l1_wind(path)` does not mean "read this file". It means "get
me L1 wind, using this file if it happens to be there". A missing file is not an
error to that function — it is a cue to go to the network. And `fetch_l1_wind`
`mkdir`s its cache directory on entry, so it writes even before it fetches.

So the naive implementation of "check what the L1 cache contains":

```python
l1 = fetch_l1_wind(str(l1_path))     # WRONG
```

...creates a directory, hits NOAA, writes a cache file, and reports on data that
did not exist until you asked. On every Run click. And it would look like it
worked.

**The invariant.** Every cache file is `stat`-ed, and the parser is only called
when the file already exists:

```python
if not l1_path.exists():
    findings.append(_finding("l1_cache_missing", "info", ...))
else:
    l1 = fetch_l1_wind(str(l1_path))
```

Absence is a *finding*, never a fetch. The module docstring states the rule as a
hard constraint:

> Hard rule for the STORM CACHES: never fetch, never write, never mkdir. Every
> cache file is `stat`ed before any parser touches it, because the ingestion
> clients are cache-first-then-NETWORK and create directories on entry.

**How it is held.** `test_read_only_no_mkdir_no_fetch` points the whole check at
an empty `tmp_path` and asserts that nothing was created:

```python
def test_read_only_no_mkdir_no_fetch(self, tmp_path):
    ...
    assert not any(tmp_path.rglob("*"))
```

An empty directory that stays empty. That is the entire assertion, and it is
worth more than a mock.

---

## 6.3 Invariant 2 — peek, do not check

**The trap.** The rate limiter:

```python
def check_rate_limit(storm_id: str) -> bool:
    now = time.time()
    last = _pipeline_calls.get(storm_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _pipeline_calls[storm_id] = now      # <-- records on read
    return True
```

The name says "check". The body **records the call it is checking**. That is
correct for its actual caller — `POST /api/detect` asks once, immediately
before running, and the recording is what makes the limit work.

But it means *asking whether you may run* is indistinguishable from *running*.
A pre-flight check that called `check_rate_limit()` would consume the run slot
it was reporting on. The user would see "you may run", press Start, and get a
429 — caused entirely by the check that told them they could.

Worse, it would have looked correct in casual testing: the first click works,
and the failure only appears on the second within thirty seconds.

**The invariant.** A non-mutating twin:

```python
def peek_rate_limit(storm_id: str) -> float:
    """Seconds until the next run is allowed. 0 = allowed now. Does not record."""
    return max(0.0, RATE_LIMIT_SECONDS - (time.time() - _pipeline_calls.get(storm_id, 0)))
```

It also returns something more useful than a boolean — the *wait in seconds* —
which is what the `block` finding puts in front of the user:

> One pipeline run per storm per 30s: wait 22s before running this storm again,
> or the request returns 429.

**How it is held.** `test_peek_does_not_mutate` calls `peek_rate_limit` twice
and asserts the second call returns the same answer, and that a subsequent
`check_rate_limit` still succeeds. The project memory carries the rule too:

> `check_rate_limit()` MUTATES on read (records the call). Preflight and
> anything else read-only must use `peek_rate_limit()` instead.

---

## 6.4 Invariant 3 — never probe the provider

**The trap.** "Is there enough token budget left?" has an obvious
implementation: ask the API. The obvious implementation spends tokens, on every
Run click, to check whether there are tokens.

A check that consumes the resource it protects is not a check. It is a leak with
a user interface.

**The invariant.** Read the process's own accounting instead:

```python
# Never probe the Groq API itself: that spends the quota this check
# protects. Headroom is this process's own TPM accounting - a soft signal.
from backend.genai.llm import _bucket_for
total = sum([await _bucket_for(GROQ_MODEL, key).headroom() for key in GROQ_API_KEYS])
```

And then — the part that makes it honest rather than merely cheap — **state the
limitation in the finding itself**:

> (Process-local accounting; other clients are invisible.)

A soft signal presented as a soft signal is useful. The same signal presented as
authoritative is a liability the first time someone else is using the key.

---

## 6.5 The fourth one: admitting what is *not* read-only

The first version's docstring claimed the module never writes. It was false, and
the way it was false is instructive.

`_system_findings()` calls `health_collector.run()`. That is not a status flag
lookup — it **loads all six LightGBM checkpoints** and **counts every ChromaDB
collection**. And ChromaDB rewrites its own segment files on a pure read: 11
git-tracked files touched per call, including `chroma.sqlite3`.

So the module that promised to change nothing was dirtying eleven tracked files
and burning ~9.7 seconds on every click of the button whose purpose was to save
the user eighty.

Two things were wrong, and both were fixed:

- **The behaviour.** TTL-cached at 30 s, warmed once in the lifespan handler.
  Live first click after the fix: **0.31s**.
- **The claim.** The docstring now scopes its promise precisely:

```
Hard rule for the STORM CACHES: never fetch, never write, never mkdir. ...

That is a claim about the storm caches only, not whole-module purity.
_system_findings() calls the health collector, which loads the six ML
checkpoints and counts every Chroma collection - and Chroma rewrites its own
segment files even on a pure read.
```

**The lesson is the second fix, not the first.** A comment that overstates a
guarantee is worse than no comment: the next person reads "never writes", trusts
it, and builds on a property that does not hold. A precisely scoped claim —
*"read-only for the storm caches, not overall, and here is exactly why"* — is
one that stays true and can be relied on.

The project memory now carries a standing warning against regressing it:

> Never restore a per-call `health_collector.run()` — that puts both the latency
> and the writes back on every click.

---

## 6.6 The pattern behind all four

Every one of these is the same shape: **the observer effect.**

| Component | Behaves correctly for | Trap for a read-only caller |
|---|---|---|
| Ingestion clients | The pipeline, which wants the data | Absence triggers a fetch and a write |
| `check_rate_limit` | `POST /api/detect`, which is about to run | Asking consumes the slot |
| Provider quota API | A client that wants to use quota | Checking spends what it measures |
| `health_collector` | A `/health` endpoint called rarely | Loads models and rewrites the vector store |

None of these is a bug. Each is a component behaving correctly for its intended
caller, becoming wrong the moment a *diagnostic* becomes the caller.

Which is the general lesson: **adding an observer to a system is not a
read-only operation by default.** It is read-only only if every function it
touches happens to be, and in a codebase built on cache-first clients and
mutation-on-read counters, most of them are not. The work of building a
pre-flight check is not writing the rules. It is finding the four places where
looking changes the thing.

---

Next: [What went wrong the first time](07-what-went-wrong-first.md).
