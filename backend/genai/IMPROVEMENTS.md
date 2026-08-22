# GenAI / Agentic Layer — Fallbacks, Gaps and Open Work

Honest state of the advisory layer as of 2026-08-22 (second pass). Companion to
[`ARCHITECTURE.md`](ARCHITECTURE.md), which describes how it works when it
works; this file describes where it does not.

Everything below was found by reading or running the code, not by inspection of
the docs. Where a claim is unverified it says so.

Severity key:

| | Meaning |
|---|---|
| **P0** | Produces wrong or misleading output that a user could act on |
| **P1** | Degrades quality or reliability in a way that shows |
| **P2** | Technical debt, cost, or ergonomics |

---

## 1. Fallback inventory

Every failure path, and what a caller actually receives. This is the part worth
reviewing before a demo, because several fallbacks are silent by design.

| # | Failure | Fallback | Visible to caller? |
|---|---|---|---|
| 1 | KB collection missing / empty | retrieve nothing, generate from storm data alone | Yes — `LOW_COVERAGE` |
| 2 | Transient chroma segment fault | re-acquire handle, retry ×4 | Only in logs; if all 4 fail → as #1 |
| 3 | Embedder fails on GPU | reload on CPU, at load *and* at encode | Log warning only |
| 4 | Embedding still fails | exception → `retrieve_chunks` returns `[]` | As #1 |
| 5 | LLM 429 | park that key, reroute to another key | Log only |
| 6 | LLM timeout (90s) | release reservation, retry | Log only |
| 7 | Output truncated at `max_tokens` | `TruncatedCompletion` → agent retry | Recorded in `generation_errors` |
| 8 | Schema / citation / floor violation | retry with the error fed back into the prompt | `generation_errors` |
| 9 | All 3 attempts exhausted | `ESCALATE_TO_SPECIALIST` advisory | Yes — `GENERATION_FAILED`, confidence `0.0` |
| 10 | Self-check flags a claim | ship anyway, −0.25 confidence | Yes — `HALLUCINATION_DETECTED` |
| 11 | LLM under-reports severity | keep the LLM value, flag it | Yes — `SEVERITY_MISMATCH` |
| 12 | Citation does not resolve | ship anyway | Yes — `CITATION_GAP` |
| 13 | Verifier finds an invalid number | rewrite to nearest valid, record substitution | Yes — `passed_with_corrections` |
| 14 | ML impact prediction fails | non-fatal, appended to `errors`, pipeline continues | Yes — `errors[]` |
| 15 | CV detection finds no PNGs | fall back to the committed stub event | Log warning only |
| 16 | Agent task raises | orchestrator emits `agent.error`, other industries continue | Yes — stream event |

### Fallbacks that deserve scrutiny

- **#9 is deliberately useless.** The fallback advisory says only "contact a
  specialist". That is intentional: a degraded run must not look like a good
  one. Do not "improve" it into something that reads like real guidance.
- **#11 never overrides.** The deterministic matrix is the authority for
  severity, but the code flags and keeps the LLM's lower value rather than
  replacing it. Arguably wrong — see §2.1.
- **#15 is invisible in the API response.** A run on stub data is
  indistinguishable from a run on freshly processed imagery unless you read the
  logs. See §3.4.
- **#2 exhausting all four attempts has been observed in a live run**, which
  degraded one advisory to ungrounded. See §4.1.

---

## 2. Wrong

### 2.1 ~~Severity floor is advisory, not enforced~~ — **RESOLVED**

`check_severity_consistency` detects that the LLM assigned a severity below the
deterministic matrix floor, flags `SEVERITY_MISMATCH`, and then **keeps the
LLM's value**. The comment says "human review required".

For a safety-adjacent system this is backwards. The matrix is described
everywhere else as authoritative; a model that under-reports a G5 as MEDIUM
should not be able to publish MEDIUM. The flag is easy to miss in a UI.

Resolved. `agents/base.py` clamps severity up to the matrix floor, keeps
`SEVERITY_MISMATCH` so the disagreement stays visible, and records the original
value in `generation_errors`. Over-reporting is still permitted. Covered by
`test_severity_floor_is_enforced_not_just_flagged`.

### 2.2 Telecom has no verifier rules — **PARTLY RESOLVED**

`verify_advisory` dispatches checks by industry:

| Industry | Checks applied |
|---|---|
| aviation | HF frequency band, reroute latitude |
| maritime | HF frequency band, GMDSS channel |
| grid | NERC GIC operating step |
| **telecom** | **none** |

A telecom advisory passes the "deterministic verifier gate" trivially, and
comes back `verifier.status == "passed"` having been checked against nothing.
That is worse than no verifier, because the status field implies scrutiny that
did not happen.

Half done: the verifier now reports **`not_applicable`** when no rule set
matched, so it no longer claims a verification that did not happen. Telecom
still has no rules of its own.

Remaining work — add telecom checks: GNSS L1/L2/L5 carrier frequencies
(1575.42 / 1227.60 / 1176.45 MHz), GPS error bounds cross-checked against the
NOAA scale table already in `impact_matrix_kb`, and satellite band designators
(L/S/C/X/Ku/Ka ranges). All are published constants, so this is the same shape
of work as the existing four rule sets.

### 2.3 `raw_alert_text` is interpolated into the prompt unsanitised — **P1**

`prompts/base.py` appends the raw NOAA alert text straight into the user turn:

```python
+ (f"\n\nRaw NOAA Alert Text:\n{storm.raw_alert_text}" if storm.raw_alert_text else "")
```

That string originates outside the system — NOAA/SWPC alert feeds and DONKI. It
is currently read from committed cache files, so the practical risk today is
low, but the moment live fetching is enabled this is a prompt-injection path
into an advisory generator whose output is meant to be trusted.

Fix: fence it explicitly (`<untrusted_alert_text>`), instruct the model to treat
it as data, strip control characters, and cap its length. Cheap; worth doing
before any live feed is wired up.

### 2.4 `SELF_CHECK_MAX_CHUNKS` is dead config — **P2, still open**

It survived the self-check context fix only as a `# noqa: F401` import. It no
longer influences anything. Either remove it or reconnect it as an explicit cap.
Leaving a knob that looks live but is not is how the
`HELIOOPS_CHROMA_PERSIST_PATH` bug happened.

---

## 3. Missing

### 3.1 ~~The verifier has zero tests~~ — **RESOLVED**

`verifier.py` is 416 lines, is described in the project docs as a headline
feature ("the 21 MHz block"), can **rewrite operator instructions**, and has no
test file. `grep -rl verify_advisory backend/tests/` returns nothing.

Every rule table in it is a hand-written constant — ICAO HF bands, reroute
latitudes, NERC step names, GMDSS frequencies — and none is checked against
anything. A typo in `GMDSS_VALID_FREQUENCIES_KHZ` would silently "correct"
valid advice into invalid advice.

Resolved. `backend/tests/test_verifier.py`, 35 tests: parametrised over every
published constant, both correction paths, the storm-severity gradient, the
`not_applicable` path, and the severity clamp end to end.

Writing them surfaced three real defects, all fixed:
- `GMDSS_VALID_FREQUENCIES_KHZ` was declared and never read. Nothing checked
  maritime frequencies at all, so an action naming a distress frequency that
  does not exist emitted no check and the advisory came back `passed`.
- Corrections were each computed from the original action text while
  `verify_advisory` keeps only the last one, so an action naming two invalid
  values shipped with the first still in it.
- `verify_advisory` discarded the GMDSS corrected text, which would have
  recorded a correction in the provenance trace while dispatching the bad
  value.

### 3.2 No advisory quality regression suite — **P1**

Nothing detects quality drift. The measurements in this repo (citation validity,
self-check flag rate, action-item counts) were all produced by throwaway
scripts. A model swap, a prompt edit, or a corpus change could halve grounding
quality and every test would still pass.

Needed: a small golden set — both anchor storms × four industries — asserting
schema validity, `>= MIN_ACTION_ITEMS`, citation-resolution rate above a
threshold, and no placeholder text. Run it behind a marker so it is opt-in and
does not burn tokens in normal CI.

### 3.3 Tests mock the LLM, so nothing catches a dead model — **P1**

Both configured Groq models were decommissioned and returned 404 for every
call. The advisory layer was **100% non-functional** and the full suite stayed
green, because tests mock `complete_json`.

A single opt-in smoke test that lists `Groq().models.list()` and asserts
`GROQ_MODEL` and `GROQ_CHECKER_MODEL` are present would have caught it the day
it happened. `test_llm_ratelimit.py` currently guards this with a hard-coded
`DECOMMISSIONED` set, which only catches models already known to be dead.

### 3.4 Stub-vs-real provenance is not surfaced — **P1**

When no preprocessed imagery exists, CV detection falls back to a committed stub
storm event. Nothing in `PipelineResult` records that. A demo run on stubs and a
run on real imagery return identical-looking payloads.

Fix: a `data_source: "live" | "stub"` field on the result, propagated into the
provenance trace.

### 3.5 No caching — **P2**

The anchor storms are deterministic and replayed constantly, yet every request
regenerates all four advisories from scratch. At ~12k tokens per run that is the
dominant cost during development and demos, and the main reason the free-tier
budget kept running dry during this work.

Fix: cache on `(storm_id, model, prompt_hash)` with an explicit bypass. Should
be a large win for very little code.

### 3.6 No token or cost accounting — **P2**

`llm.py` knows the exact `usage.total_tokens` of every call and throws it away
after reconciling the rate-limit bucket. There is no per-run total, no
per-industry breakdown, no way to answer "what does one storm cost".

### 3.7 No evaluation of retrieval quality — **P2**

There is no measurement of whether the retrieved chunks are the *right* chunks —
no labelled query set, no recall@k. `RAG_MIN_SIMILARITY = 0.35` is a guess, and
observed similarities cluster at 0.73–0.83, so the threshold is nowhere near
binding and effectively does nothing.

---

## 4. Unresolved

### 4.1 chromadb segment faults — **P1, root cause unknown**

```
chromadb.errors.InternalError: Error executing plan: Internal error:
Error creating hnsw segment reader: Nothing found on disk
```

Intermittent, roughly one pytest session in five before mitigation. Ruled out by
measurement, so nobody needs to re-check these:

| Hypothesis | Result |
|---|---|
| OneDrive / synced folder | **Rejected** — reproduces on a local non-synced disk |
| DB corruption from a partial revert | **Rejected** — all 5 vector segments have directories, no orphans |
| Concurrent access | **Rejected** — 320 concurrent same-collection queries, 0 failures |
| Our client-construction race | **Rejected** — separately locked; that was a real but different bug |
| Memory pressure from TensorFlow | **Partially** — removing TF cut RSS 1025→791MB and the rate dropped, but this was not isolated as *the* cause |

Mitigation in place: every chroma read goes through `with_collection()`, which
re-acquires the handle and retries (4 attempts). Six consecutive clean full-suite
runs afterwards. **But it has been seen to exhaust all four attempts during a
live pipeline run**, degrading one advisory to ungrounded.

Do **not** also reset the client singleton between attempts. That was tried: it
invalidates handles other callers hold and made things measurably worse — soak
went from 1 failure in 10 to 3 in 8.

Next step: pin a different chromadb version and re-soak. Failing that, consider
a different vector store; the interface surface we use is small.

### 4.2 Telecom corpus is the wrong genre — **IMPROVED, not closed**

`telecom_kb` holds ITU-R P-series recommendations (P.531, P.533, P.372, P.618).
These are mathematical propagation references. They ground *mechanism* claims
well — why GNSS degrades, how MUF collapses — but contain almost no operational
procedure, so the model struggles to derive concrete steps and reaches for
placeholder text.

Symptom: telecom is the industry that most often trips the `MIN_ACTION_ITEMS`
floor and the placeholder-action rejection.

Improved by adding **ITU-T G.8272** (primary reference time clock), the one
source in the corpus about consequences rather than physics: what a clock must
do once GNSS traceability is lost. telecom_kb 164 → 195 chunks.

Two candidates were evaluated and rejected, so nobody repeats the work:
- **3GPP TS 38.331** is the RRC protocol spec. 29% ASN.1, `ionospher` 0 hits,
  `holdover` 1 hit across 3.8M chars. Wrong document.
- **NGA Sailing Directions Pub 120/140/160** are regional navigation planning
  guides; their comms-dense pages are scattered country-specific reporting
  tables, not procedure. 1,742 pages would have buried the corpus.

Still wanted: a genuine operator runbook — national regulator continuity
guidance, or an internal network-continuity procedure.

### 4.3 Maritime primary source — **IMPROVED, blocked on cost**

The IMO GMDSS Manual is a paid IMO publication (sale no. IH970E) with no
legitimate free download, so the corpus uses the free ITU-R M-series instead —
the standards GMDSS is built on. That is a good substitute for procedures and
frequencies, but it is a substitute.

**NGA Pub. 117** is now in the corpus — the GMDSS / distress / emergency block,
pages 542-581 of 710. `msi.nga.mil` returns 503 to automated clients, so it came
from the Internet Archive; it is a US Government work and therefore public
domain. maritime_kb 174 → 214 chunks.

Ingested selectively on purpose: only ~118 of its 710 pages are prose, the rest
being a country-by-country station directory that would have added ~1,800 chunks
of call-sign tables and buried the ITU-R procedure chunks. `ingest_maritime.py`
carries a page range per document for exactly this.

The copy is the **2014 edition** and is not current — replace it from NGA when
the MSI portal is back up.

### 4.4 Retrieval quality is uneven across industries — **P2**

Observed top-chunk cosine similarity on the G5 anchor storm:

| Industry | Top similarity | Corpus genre |
|---|---|---|
| grid | 0.831 | operational standards |
| aviation | 0.818 | operational procedures |
| telecom | 0.749 | mathematical references |
| maritime | 0.738 | technical standards |

The gap tracks corpus genre, not corpus size — maritime and telecom now have
comparable chunk counts to grid. This feeds directly into `confidence_score`,
whose base term is mean similarity, so maritime and telecom are structurally
scored lower for reasons unrelated to advisory quality.

---

## 5. Weak but working

| Item | Note | Severity |
|---|---|---|
| Retry loop cost | 3 attempts × full prompt. A schema failure on attempt 1 costs a full regeneration. Cheaper: ask for a targeted repair of the invalid field. | P2 |
| `stream_pipeline` polling | Drains its queue on a `sleep(0.05)` loop rather than awaiting task completion. Works, but is a busy-wait and adds up to 50ms latency per event. | P2 |
| No chunk dedupe | Industry and impact-matrix results are concatenated without deduplication. Harmless today because they come from different collections. | P2 |
| `estimated_impact_window` unvalidated | Free-form string, accepted as written. Could be any text. | P2 |
| `MAX_RETRY_ATTEMPTS` fixed at 3 | Not adaptive. A hard schema failure and a transient rate limit get the same budget. | P2 |
| Confidence formula is unvalidated | The bonus/penalty constants are reasonable-looking guesses. Nothing calibrates them against human judgement. | P2 |

---

## 6. How to make this measurably better

Concrete next moves, each with what it buys and roughly what it costs. Ordered
by value per unit of effort.

### 6.1 Close the guardrail loop with an evaluation set — *highest value*

Nothing today detects quality drift. Every number in this document came from a
throwaway script; a prompt edit or model swap could halve grounding quality and
all 237 tests would still pass.

Build a golden set: both anchor storms × four industries, asserting schema
validity, `>= MIN_ACTION_ITEMS`, citation-resolution rate above a threshold, no
placeholder text, and self-check flag rate below a ceiling. Mark it
`@pytest.mark.live` so it is opt-in and does not burn tokens in normal CI.

Once that exists, every item below becomes safe to attempt.

### 6.2 Give telecom and grid real verifier rules

Telecom has none. Grid's GIC rule can only ever confirm, never block — an action
referencing no NERC step is silently unverified, the same weakness the GMDSS
check had before it was wired to its frequency table.

- Telecom: GNSS carrier frequencies, GPS error bounds against the NOAA scale
  table, satellite band designators.
- Grid: block an action that quotes a GIC threshold in A/phase that contradicts
  the retrieved standard, rather than only recognising step names.

Both are published constants; the pattern is already established four times over.

### 6.3 Make the confidence score mean something

`score = mean similarity + citation bonuses − penalties + coverage bonus −
self-check penalty`. Every constant is a plausible-looking guess and nothing
calibrates them. Two advisories scoring 0.73 and 0.84 are not reliably better or
worse than each other.

Cheapest real improvement: have two people rank ~40 advisories, then fit the
weights to that ranking. Even a crude calibration beats invented constants, and
it makes the LOW_CONFIDENCE threshold defensible.

### 6.4 Repair-not-regenerate on validation failure

A schema failure currently costs a full regeneration: whole prompt, whole
completion, three attempts. Most failures are one bad field — a missing
`source_ref`, two action items instead of three.

Send the invalid JSON back with just the failing field and ask for a patch.
Roughly a 5-10x token saving on the retry path, which is the single largest
avoidable cost in the layer.

### 6.5 Cache deterministic replays

The anchor storms are deterministic and get replayed constantly, yet every
request regenerates all four advisories. Key on
`(storm_id, model, prompt_hash, corpus_version)` with an explicit bypass. Large
saving, low risk, and it removes the free-tier budget as a demo constraint.

### 6.6 Retrieval quality measurement

`RAG_MIN_SIMILARITY = 0.35` is a guess, and observed similarities cluster at
0.67-0.83, so the threshold never binds and effectively does nothing. There is
no labelled query set and no recall@k.

Write ~20 labelled queries per industry with the chunk that should win. That
turns every future corpus or embedder change from a guess into a measurement —
and would have caught the maritime catalogue-page problem on day one.

### 6.7 Fence untrusted text

`raw_alert_text` still goes into the prompt unsanitised (§2.3). Low risk while
it is read from committed cache files; required before any live NOAA/DONKI feed
is wired up.

### 6.8 Corpus depth where it is thinnest

grid_kb is the smallest at 101 chunks and its sources are standards rather than
operating procedures, which is why grid was the last industry still inventing
numbers. NERC publishes GMD operating-procedure reference material; adding one
would let grid cite figures instead of reaching for them.

### 6.9 Stub-vs-live provenance

A run on committed stub imagery and a run on freshly processed imagery return
identical-looking payloads. Add `data_source: "live" | "stub"` to
`PipelineResult` and into the provenance trace.

### 6.10 Timebox the chromadb bisect

Mitigation holds, but the fault is unexplained (§4.1). Pin a different chromadb
version and re-soak. If that does not settle it, the interface surface we use is
small enough to swap the store.

---

## 7. Decisions taken

| Question | Answer | Effect |
|---|---|---|
| Enforce the severity floor? | **Enforce** | Clamped up, flag kept, original recorded |
| Is `MIN_ACTION_ITEMS = 3` right? | **Yes for now** | Revisit if it pushes industries into fallback |
| `passed` when no rules matched? | **No** | Reports `not_applicable` |
| Validate the rule constants? | **Published standards as-is** | Tests check application, not values |
| Buy the IMO GMDSS Manual? | **Skip** | ITU-R M-series + NGA Pub 117 substitute |

## 8. Still needs a human

1. **A domain expert to validate the rule tables.** The verifier's constants —
   ICAO HF bands, GMDSS frequencies, reroute latitudes, NERC step names — are
   hand-written. Tests confirm they are *applied* correctly; nothing confirms
   they are *right*, and a wrong constant silently corrects good advice into
   bad.
2. **A current NGA Pub 117** once the MSI portal is back.
3. **A telecom operations runbook** — the corpus gap no amount of tuning fixes.
