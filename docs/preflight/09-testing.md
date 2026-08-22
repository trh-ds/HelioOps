# 9 — How it is tested, and the blind spot the tests had

*35 tests across 8 classes in `backend/tests/test_preflight.py`, plus node
asserts in `frontend/src/data.test.mjs`.*

---

## 9.1 The suite at a glance

| Class | Tests | What it pins |
|---|---|---|
| `TestPeekRateLimit` | 3 | The peek is non-mutating |
| `TestCacheFindings` | 4 | Existence prediction, and read-only behaviour |
| `TestConflictRules` | 11 | Each rule fires above threshold, is silent below, skips missing inputs |
| `TestRunPreflight` | 2 | End-to-end schema, and block behaviour |
| `TestStaleEpoch` | 5 | The wrong-epoch veto, including withholding the source |
| `TestStubDonkiRules` | 5 | The rule that fires on a clean checkout |
| `TestStubReplayDemotion` | 2 | `warn` → `info` and the appended explanation |
| `TestHealthSnapshot` | 2 | TTL caching, and that `force` bypasses it |

Everything sets up and tears down its own global state — `_pipeline_calls` is
saved and restored, `_health_cache` is nulled — so the suite is order-independent
despite touching module-level caches.

## 9.2 The four tests worth reading

### The read-only proof

```python
def test_read_only_no_mkdir_no_fetch(self, tmp_path):
    ...
    assert not any(tmp_path.rglob("*"))
```

Point the whole check at an empty directory; assert it is still empty. No mocks,
no patched network layer, no assertion about which functions were called. If
anything fetched, mkdir'd or wrote, a file exists and the test fails.

This is the strongest test in the suite because it verifies the *property*
rather than an implementation of it. A future refactor that swaps parsers,
reorders the passes, or adds a fifth source still has to keep the directory
empty.

### The internal-consistency guard

```python
def test_stubs_are_internally_consistent(self):
    # The rules must be silent on the committed stubs' own values —
    # otherwise every fresh checkout warns about its own reference data.
    for storm_id, cfg in STORM_CONFIGS.items():
        stub = json.loads((BACKEND_DIR / cfg["stub_path"]).read_text())
        f = _conflict_findings(stub, stub["cme"], stub["flare"], stub["l1_solar_wind"])
        assert f == [], f"{storm_id} stub fired {_ids(f)}"
```

Feed each committed stub its own values as if they came from three independent
sources, and assert every rule stays silent. A stub that contradicts itself would
make the panel warn about the repository's own reference data on every clone —
noise indistinguishable from signal, arriving on day one.

It also pins the thresholds against the real data: nobody can tighten
`STUB_DONKI_SPEED_TOL` past the point where the shipped stubs trip it without
this failing.

### The demotion test

```python
def test_demoted_and_annotated_under_stub_replay(self):
    f = self._fired(True)[0]
    assert f["severity"] == "info"
    assert "never read" in f["detail"]
```

Both halves. The severity dropped, *and* the explanation was appended — a
demotion without its reason is an inconsistency between the pill and the prose,
and this asserts that never ships.

### The stale-epoch withholding test

`test_stale_source_is_withheld_from_the_rules` is the one that pins the subtlest
behaviour in the module: a wrong-epoch source must not merely be *reported*, it
must be removed from the inputs so downstream physics rules cannot manufacture
findings out of it. That is a behaviour easy to lose in a refactor — the finding
is visible, so the code looks correct even after the `None` assignment is gone.

## 9.3 The frontend tests

`gateDecision()` lives in its own module precisely so it can be asserted with
plain node asserts, in a frontend with three runtime dependencies and no test
framework. What is covered:

- Severity sort order, and that the headline is `findings[0]`.
- Unknown severities sort **last**, not first.
- `{action:'run'}` on null, undefined, or a malformed response — the
  never-break-the-demo path.
- Counts per severity.
- The clean-state headline when `findings` is empty.

No vitest, no jsdom, no new dependency. Adding a test framework to cover twenty
lines of sorting would have cost more than the code.

## 9.4 The blind spot — stated plainly

The first version shipped with **25 passing tests** covering the conflict rules,
and every conflict rule was unreachable on a fresh clone. See
[chapter 7](07-what-went-wrong-first.md).

The mechanism is worth stating as a general lesson, because it is easy to
reproduce and hard to notice:

> Unit tests verify a function against inputs you supply. They cannot verify
> that anything supplies those inputs in production. A function tested only
> against fabricated inputs has been tested as a calculator, not as a feature.

`TestConflictRules` called `_conflict_findings()` directly with hand-built
dictionaries. Every assertion was correct. Not one of them touched the code path
that decides whether `cme`, `flare` or `l1` are ever non-`None`.

## 9.5 What was added to close it

**An end-to-end test against the real repository:**

```python
def test_schema_and_ready_on_real_repo(self):
    result = asyncio.run(run_preflight(STORM))
    assert set(result) == {"storm_id", "ready", "estimated_duration_s", "findings"}
    ...
    # today's normal: no frames committed -> stub replay predicted
    assert "cv_stub_replay" in _ids(result["findings"])
```

No `tmp_path`, no fixtures, no fabricated inputs. It runs the real check against
the real checkout and asserts on what actually comes back — which is the only
kind of test that could have caught the original bug.

**`TestStubDonkiRules`, run against the committed DONKI caches**, so the one rule
that fires on a clean checkout is covered by data that ships with the repo rather
than by a dictionary written in the test file.

**And the suite passes with and without the ignored caches.** The commit message
records this explicitly: *"35 in test_preflight, passing with and without the
ignored caches"*. That is the property that makes the tests meaningful on a
developer machine that has L1 and XRS data locally, and on a fresh clone that
does not.

## 9.6 The general rule this suggests

For any feature whose behaviour depends on data files, ask three questions of
the test suite before believing it:

1. **Does anything run the real entry point against the real repository?** If
   every test constructs its inputs, nothing proves the inputs arrive.
2. **Would the suite still pass if the feature were inert?** For the first
   version the answer was yes, and that is the whole failure in one sentence.
3. **Does it pass on a clean clone?** Not on a machine that has been developing
   the feature for three hours.

## 9.7 Verified state

Recorded at the time of the fix and confirmed since:

- **284 backend tests** at `a18490b`; **307 passed / 1 skipped** on the current
  tree after subsequent features landed.
- `ruff check backend/` clean.
- Frontend test and build pass.
- Live `uvicorn`: 400 on a malformed storm id, 404 on a well-formed unknown one,
  correct results for both storms, no rate-limit slot consumed across repeated
  calls, and the block correctly reported mid-run.
- A full pipeline run after the change produced 4 grounded advisories with zero
  errors.

One known flake, unrelated: `tests/test_retrieval.py` intermittently fails with a
chromadb `InternalError` under full-suite ordering and passes standalone.

---

Next: [Timeline](10-timeline.md).
