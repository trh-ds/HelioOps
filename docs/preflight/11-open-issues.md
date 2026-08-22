# 11 — Open issues and honest limits

*What is still wrong, what is thinner than it sounds, and what a hostile
reviewer would find. Nothing here is hidden elsewhere in the pack.*

---

## 11.1 A live bug: `_stale_epoch` truncates asymmetrically

```python
gap_days = abs((ts - storm_dt).days)
if gap_days <= STALE_EPOCH_DAYS:
    return None
```

`timedelta.days` truncates toward negative infinity, so taking `abs()` of it
gives a different answer depending on the *sign* of the gap.

A cache 7.5 days away from the storm:

| Direction | `(ts - storm).days` | `abs(...)` | Fires? |
|---|---|---|---|
| Cache is 7.5 days **after** the storm | `7` | 7 | no |
| Cache is 7.5 days **before** the storm | `-8` | 8 | **yes** |

The same physical gap produces opposite verdicts. The fix is one line:

```python
gap_days = abs((ts - storm_dt).total_seconds()) / 86400.0
```

**Practical impact is small** — real wrong-epoch caches are months out, not
seven-and-a-half days — but it is a correctness bug in a rule whose whole job is
to prevent other rules from producing wrong findings, and it is one line. It is
listed here rather than fixed silently because this pack is the record of the
feature's real state.

## 11.2 Coverage is thinner than "four cross-source physics rules" sounds

There are six rules in the module. On a clean checkout, **exactly one can
fire**: `stub_donki_speed_mismatch`.

| Rule | Needs | Can it fire on a fresh clone? |
|---|---|---|
| `stub_donki_speed_mismatch` | Committed stub + DONKI | **Yes** |
| `stub_donki_arrival_mismatch` | Committed stub + DONKI | Yes, but silent on both storms (1.8h and 7.6h, both inside the 12h ballistic tolerance) |
| `speed_disagreement` | DONKI + L1 | No — L1 is gitignored and real-time only |
| `arrival_eta_mismatch` | DONKI + L1 | No — same |
| `bz_northward_strong_g` | Stub + L1 | No — same |
| `flare_r_mismatch` | Stub + GOES XRS | No — XRS is gitignored and real-time only |

This is handled *honestly* — the stale-epoch rules report the wrong-epoch
condition rather than dressing a date-range error up as a physics finding, which
is the right behaviour. But it means the headline should be read as: **one rule
that fires on a clean checkout, one that could, and four that need data a fresh
clone cannot obtain from the upstream endpoints at all.**

If a judge asks about coverage, volunteer this before they find it.

## 11.3 Discriminating power is two storms and one signal

The panel differs between G4 and G5 by exactly one line — the 65%-vs-12% speed
drift. That single difference is doing all the work of proving the check reads
this storm rather than reciting a template.

It is enough to demonstrate the mechanism. It is not enough to claim the check
has been exercised across a range of failure modes on real data.

## 11.4 The duration estimate ignores the main cause of slowness

`_estimate_duration()` is a running mean of observed pipeline durations with a
70s default. It is honest about what it measures, but it does not incorporate
the one factor most likely to make the *next* run slow: exhausted token budget,
which causes a stall rather than a failure.

The panel does report low quota as a separate `warn` finding, and that finding
explicitly says the run will stall. But the two are not connected — the estimate
still says "~70s" next to a warning that it will not be 70s. Folding quota state
into the estimate is the obvious improvement.

## 11.5 Quota headroom is process-local

`_quota_findings` reads this process's own TPM accounting, because probing the
provider would spend the quota being measured (see
[6.4](06-the-read-only-invariants.md#64-invariant-3--never-probe-the-provider)).

That means a second process, a teammate's laptop, or a deployed instance sharing
the same key is **invisible** to the check. The finding says so in its own text,
which is the right mitigation, but the limitation is real: the panel can report
healthy headroom while the key is in fact saturated by someone else.

## 11.6 Health findings can be up to 30 seconds stale

`HEALTH_TTL_S = 30`. A dependency that degrades within that window will not
appear until the cache expires. This is a deliberate trade — the alternative is
~9.7s and eleven rewritten files per click — but it is a staleness window, and a
run started at second 29 of the TTL is being gated on information from the
beginning of it.

## 11.7 Things that are correct but easy to break later

Each of these is currently right, has no test that would obviously survive a
rewrite of the surrounding function, and would fail *silently*:

- **Adding `check_rate_limit()` back to the preflight handler** for consistency
  with `detect_storm`. This is the most likely future regression: it makes the
  two handlers look symmetric and destroys the feature.
- **Restoring a per-call `health_collector.run()`.** Puts back both ~9.7s and
  the writes. The project memory carries a standing warning; the docstring does
  too.
- **Removing the `None` assignment after a stale-epoch finding.** The finding
  stays visible, so the code still looks correct — but the vetoed source flows
  back into the physics rules.
- **Reordering `_cache_findings` so the epoch check is not last.** It can no
  longer veto sources the rules already consumed.

## 11.8 Deliberately out of scope

From the original plan, and still deferred:

> Scope decision (user-confirmed): **preflight only** — no provenance threading
> through `detect()`/`StormEvent`; that is the natural follow-up, deferred.

The natural next feature is to carry the pre-flight findings *into* the run, so
the advisory that comes out is annotated with the degradations that were
predicted before it started. Today the panel's knowledge is discarded the moment
you press Start.

Also not built, and not planned: persistence of findings across sessions,
alerting on them, and any auto-remediation.

## 11.9 Adjacent work still outstanding

Recorded here because the plan file that held it (`latestplan.md`) has been
retired into this pack. These are *not* part of the pre-flight feature; they are
the surrounding backlog as it stood.

| Phase | Status |
|---|---|
| 1 — Make CI green | **Done** (`cede5a2`, `ruff.toml`) |
| 2 — Backend on HF Spaces | **Open** — needs the owner's HF account, secrets, and a Vercel build-time `VITE_API_URL` |
| 3 — Collapse 16 markdown files to 5 | **Open** |
| 4 — Citations that open the source at the cited page | **Done** (`0ed2e45`) |
| 5 — Per-agent operator chatbot | **Done** (`f46ad3e`) |
| 6 — Email on critical findings | **Open** — infra-blocked on a mail provider and SPF/DKIM on `heliops.dpdns.org` |
| 7 — README refresh | **Partly done** — rewritten at `1b87f9c`; still wants the live Space URL and the corrected chunk count |

Minor, unrelated: the docker actions in CI still run on the deprecated Node 20
runtime, and `frontend/src/data.js` retains orphaned `REAL` / `CAVEATS` exports
plus `.maturity` CSS after the About page section was removed at `4defd3c`.

---

Next: [Glossary](12-glossary.md).
