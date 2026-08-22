# 5 — The conflict rules, and the physics behind each one

*This is the heart of "detect conflicts early". Each rule is a physical
statement about what two independent measurements are allowed to say about the
same event.*

---

## 5.1 The principle

A conflict rule is not a validation rule. Validation asks *"is this number
well-formed?"*. A conflict rule asks *"can these two well-formed numbers both
be true?"*

Every rule below therefore needs **two sources** and a **physical tolerance**.
The tolerance is the important half and the easy half to get wrong: set it too
tight and the panel cries wolf on ordinary measurement spread; set it too loose
and it never fires. Every threshold in the module carries a comment naming the
real-world quantity it was derived from:

```python
STALE_EPOCH_DAYS      = 7      # beyond this a cache cannot describe the storm
STUB_DONKI_SPEED_TOL  = 0.25   # DONKI's own analyses spread 10-20%; beyond that is disagreement
ARRIVAL_TOL_H         = 12.0   # ballistic arrival estimates carry ~10h MAE
TPM_LOW_THRESHOLD     = 4000   # ~one full advisory pass
```

None of these is a round number chosen because it looked sensible. Each is the
published error bar of the thing being compared, plus headroom.

## 5.2 The sources

| Source | What it measures | Serves historical dates? |
|---|---|---|
| **Committed stub** | The hand-checked reference description of this storm | n/a — it is local |
| **NASA DONKI** | Human-reviewed CME speed, width, ballistic arrival estimate | **Yes** |
| **GOES XRS** | Soft X-ray flux → flare class → R-scale | No — real-time only |
| **DSCOVR L1** | Solar wind speed and Bz at the L1 point, ~1h upstream | No — real-time only |

That last column is the single most consequential fact in this chapter, and it
is why the feature had to be rebuilt once. See
[chapter 7](07-what-went-wrong-first.md).

---

## 5.3 The rule catalogue

### `stub_donki_speed_mismatch` — warn

**Compares:** the committed reference speed against NASA's measured speed.
**Fires when:** `abs(ref - obs) / obs > 0.25`

```python
if obs and abs(ref - obs) / obs > STUB_DONKI_SPEED_TOL:
```

**The physics.** DONKI publishes multiple independent analyses of the same CME,
by different analysts using different coronagraph pairs. Those analyses
routinely spread by 10–20% against each other. So a gap inside 20% is the
normal disagreement of the method and means nothing. A gap beyond 25% is larger
than the method's own spread — which means the two files are not describing the
same event speed.

**On this repository, right now:**

| Storm | Reference | DONKI | Drift | Fires? |
|---|---|---|---|---|
| 2024-10-G4 | 1480 km/s | 1323 km/s | **11.9%** | no — inside analysis spread |
| 2024-05-G5 | 2200 km/s | 1332 km/s | **65.2%** | **yes** |

This is the one rule that runs on a clean checkout, and it is the reason the two
storms produce different panels. Without it the gate says the same four things
about every storm forever, which is how a warning becomes wallpaper.

### `stub_donki_arrival_mismatch` — warn

**Compares:** the reference arrival time against DONKI's ballistic estimate.
**Fires when:** the gap exceeds 12 hours.

**The physics.** A ballistic arrival estimate propagates the CME at constant
speed from the coronagraph to Earth. It ignores drag, so it carries roughly
**10 hours of mean absolute error** against real arrivals. Twelve hours is that
error bar plus a small margin: below it, a gap is the model's known inaccuracy;
above it, the two sources are describing different events.

Currently silent on both storms — G4 is 1.8h apart, G5 is 7.6h. Both inside the
ballistic error bar, correctly.

### `speed_disagreement` — warn

**Compares:** CME launch speed (DONKI) against solar wind speed at L1 (DSCOVR).
**Fires when:** `l1 > cme * 1.10`, or `l1 < cme * 0.30`

**The physics.** A CME leaves the Sun fast and is dragged toward the ambient
solar wind speed on the way out. Two things follow, and each is a bound:

- **Arriving faster than it launched is unphysical.** Nothing accelerates a CME
  between the Sun and L1. The 10% margin is measurement error, not a real
  allowance.
- **Losing 70% of its speed exceeds any plausible drag model.** Real events
  decelerate; they do not fall off a cliff. Below 30% of launch speed, the two
  files are almost certainly about different events.

The two bounds are asymmetric on purpose, because the physics is asymmetric:
deceleration is expected and unbounded-ish, acceleration is not allowed at all.

### `arrival_eta_mismatch` — warn

**Compares:** DONKI's ballistic arrival against the arrival implied by the L1
measurement (`measured_at + eta_minutes`).
**Fires when:** they are more than 12 hours apart.

Same 10h-MAE reasoning as `stub_donki_arrival_mismatch`, applied to a different
pair. Skipped entirely if either timestamp fails to parse — a missing input is
never treated as a disagreement.

### `bz_northward_strong_g` — warn

**Compares:** the reference G-scale against the measured Bz sign at L1.
**Fires when:** `stub.scales.G >= 3` and `l1.bz_nt >= 0`

**The physics.** This is the most fundamental relationship in the whole system.
Geomagnetic storms are driven by *magnetic reconnection* between the arriving
field and Earth's, and reconnection requires the arriving field to point
**southward** (negative Bz). Northward Bz does not drive strong storms. It is
not a matter of degree — it is the mechanism.

So a cached L1 file showing positive Bz alongside a G3-or-worse severity is a
contradiction at the level of the underlying physics, not a discrepancy in a
number. The finding also names the downstream consequence: `fuse()` weights Bz
at 0.2 of the detection confidence and will drop that term.

### `flare_r_mismatch` — warn or info

**Compares:** the reference R-scale against the flare class the GOES cache
actually classifies to.
**Fires when:**
- `stub.scales.R >= 2` and `flare.r_scale == 0` → **warn**
- otherwise `abs(stub_r - flare_r) >= 2` → **info**

**The physics.** The R-scale is defined directly from peak soft X-ray flux —
it is a lookup, not a model. So "the reference says R3 but the flux record
classifies below M-class" is not two estimates differing; it is a severity with
no evidence behind it in the file that is supposed to contain the evidence.

The two-tier severity is deliberate. Complete absence of a flare behind a real
R-scale is a `warn`. Being two levels off is a discrepancy worth stating but not
worth changing your decision over, so `info`.

### `l1_fallback_data` — warn

Not a cross-source rule, but the same spirit. `fetch_l1_wind` returns
`source == "DSCOVR (fallback defaults)"` when the cache holds nothing usable.
The file exists, it parses, and the numbers you get back are 400 km/s and Bz 0 —
invented placeholders that look exactly like measurements. Catching this is the
difference between "no data" and "data that is secretly not data."

### `cv_stub_replay` — warn

The headline finding on this checkout. No preprocessed frames on disk means
`detect()` returns the committed stub wholesale — the pipeline never looks at
imagery at all. It also short-circuits *before* reading any of the other
sources, which is what drives the demotion in 5.6.

---

## 5.4 The stale-epoch veto

```python
def _stale_epoch(fid, label, path, storm_dt, hint):
    """
    NOAA's rtsw (L1) and xrays (GOES) endpoints are REAL-TIME only - no date
    parameter - so a cache named for a 2024 storm actually holds whatever was
    current when it was fetched.
    """
```

This rule exists to stop the panel from being confidently wrong.

If a file named `2024-10-10.json` actually contains data from the day it was
downloaded, every physics rule above will fire — and every one of those findings
will be **true and useless**. "The solar wind speed contradicts the CME launch
speed" is a correct statement about two files that describe different months. It
diagnoses an instrument disagreement when the actual fault is a date range.

So `_stale_epoch` runs last, and when it fires it does two things:

1. Emits a `warn` explaining that the cache is from the wrong dates, naming the
   gap in days, and telling you *why* the endpoint cannot serve the date you
   want.
2. **Sets the parsed value back to `None`**, withholding that source from every
   cross-source rule.

The finding text says this out loud:

> Cross-source physics checks against this source are skipped - running them
> would report a date-range error dressed up as a disagreement between
> instruments.

**This is the most under-appreciated rule in the module.** It is the only one
whose job is to prevent other rules from producing findings. A conflict detector
that cannot recognise its own inputs as invalid will manufacture conflicts out
of bad data, and it will manufacture them in the exact confident register it
uses for real ones.

## 5.5 Why L1 and XRS are gitignored, and DONKI is committed

```gitignore
# rtsw (L1) and xrays (GOES) are REAL-TIME endpoints with no date parameter, so
# these snapshots hold the day they were fetched, not the 2024 storm they are
# named for - ~8MB that preflight can only ever report as unusable.
backend/data/cached/l1/
backend/data/cached/xrs/
```

Committing 8 MB of data whose only possible use is to trigger a "this data is
unusable" finding would be storing noise. Committing 44 KB of DONKI records that
make a real conflict rule fire on a clean checkout is storing signal.

The `.gitignore` comment also carries the regeneration commands, so the decision
is reversible by anyone who reads it:

```
python -m backend.cv.data_ingestion.l1_client        --prefetch --storm 2024-10-G4
python -m backend.cv.data_ingestion.flare_classifier --prefetch --storm 2024-10-G4
```

## 5.6 The stub-replay demotion

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

This is the rule that keeps the severity scale honest.

If the detector is replaying a stored answer, it never opens the DONKI, flare or
L1 caches. A disagreement between them is still *true* — the files really do
contradict each other, and you would want to know before fixing the data — but
it **cannot affect this run's output**. Reporting it as a `warn` would put an
amber pill on the panel for something with no path to the result.

Three properties, all deliberate:

- The finding is **not hidden**. Suppressing true information because it is
  currently inert is how you lose it permanently.
- It is **demoted, not deleted**, so the severity pill keeps meaning "this can
  change what you get".
- The reason is **appended to the detail**, so the demotion explains itself
  rather than looking like an inconsistency.

This is why the G5 panel on a clean checkout shows the 65% speed mismatch as
`info` rather than `warn` — the honest answer, given that nothing on this
checkout will read that file.

---

Next: [The read-only invariants](06-the-read-only-invariants.md).
