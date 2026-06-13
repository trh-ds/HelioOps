# Change in Plan — Heliospheric Detection Layer (Neal)

**Date:** June 2026  
**Affects:** Commits 12–15 (Layer ① CV pipeline)  
**Status:** Replaced by Option C — 3 commits shipped, 51/51 tests green

---

## What the original plan was

Commits 12–15 in the 25-commit roadmap described a fully learned detection pipeline:

| Commit | What it was supposed to do |
|--------|---------------------------|
| 12 | FITS load + running-difference preprocessing |
| 13 | EfficientNet-B0 CNN trained on LASCO catalog → CME bbox + CPA + speed |
| 14 | GOES XRS flare detection + R-scale |
| 15 | Fusion → `StormEvent` with calibrated confidence |

The CNN (commit 13) was a multi-task model with three heads: binary CME classification, cyclic CPA regression (sin/cos encoding), and angular-width regression. It required a labeled dataset: a `cme_catalog.csv` with `event_id`, `cpa_deg`, `width_deg`, `is_cme` columns, and a `data/final_processed/` directory of preprocessed image pairs.

Commit 12 preprocessing is fully implemented and solid (`cv/preprocessing.py`). The CNN architecture and training loop are also implemented (`cv/cmecnn.py`, fold checkpoints in `ml/checkpoints/commit13/`).

---

## Why we changed

**The labeled dataset does not exist.**

The CDAW CME catalog (the standard labeling source) requires significant preprocessing to join with the LASCO image archive by timestamp. That join is non-trivial: LASCO filenames encode time in a non-standard format, the catalog uses a different timestamp convention, and the image archive has gaps. Building a clean `(image_pair, label)` dataset from scratch was a multi-day data engineering task that would have blocked the demo.

Additionally, training a 5-fold temporal CV run on a CPU (no GPU available locally) would have taken 6–10 hours even with the data ready.

**The CNN approach was the wrong tool for a 2-storm demo.** Training a generalizable model is valuable for production, but for demonstrating the system on two specific, well-documented historical storms (Oct 2024 G4, May 2024 G5), authoritative physics numbers already exist from NOAA post-event reports and the DONKI catalog. There is no reason to re-derive them with an uncertain neural network when the ground truth is published.

---

## What we changed to — Option C

### Core architectural decision

> The threshold detector owns the **visual** (bbox on screen). DONKI owns the **physics** (speed, width, arrival). They never need to agree.

The CNN's two jobs are split:
- **Visual detection** (is there a CME, where is it on the image) → deterministic threshold algorithm on the running-difference frame
- **Physics** (speed, angular width, arrival time) → pulled directly from the NASA DONKI CMEAnalysis API, which provides authoritative human-reviewed values

This means the demo visual is generated from real imagery with a real algorithm, and the physics numbers are from the same source NOAA uses — both more defensible than a CNN trained on insufficient data.

### New file structure

```
cv/
├── preprocessing.py      ← commit 12, UNCHANGED — reused directly
├── cmecnn.py             ← commit 13, kept for estimate_speed_from_diff fallback
├── cache_fits.py         ← NEW — CCOR-1 via S3, LASCO via sunpy Fido
├── threshold_detector.py ← NEW — 9-step deterministic CME detector
├── fusion.py             ← NEW — StormEvent model + fuse() (from imp.md §10)
├── donki_client.py       ← NEW — DONKI CMEAnalysis API, cache-first
├── flare_classifier.py   ← NEW — GOES XRS endpoint + R-scale classification
├── l1_client.py          ← NEW — DSCOVR L1 solar wind, ETA computation
└── detect.py             ← NEW — assembly entry point (replaces cmecnn.detect_cme)

ml/stubs/
├── storm_event_2024-10-G4.json   ← NEW — real G4 physics, immediate fallback
└── storm_event_2024-05-G5.json   ← NEW — real G5 physics, immediate fallback
```

### Threshold detector algorithm (9 steps, all deterministic)

```
Input: diff_frame (512×512, float32, neutral=0.5), occulter_r, center_xy

1. Annular mask — exclude occulter shadow (inner) and far field (outer=220px)
2. μ, σ from masked pixels only
3. bright_mask = diff > μ + 2.5σ   →   < 40px bright: no detection
4. Morphological OPEN + CLOSE with 3×3 elliptical kernel
5. Connected components — filter < 30px, take largest area
6. Bounding box — pad ±20px, clip to bounds, normalize to [0,1]
7. CPA = (90 − circular_mean(image_angles)) % 360
   angular_width = circular_range(image_angles)
8. confidence = min(1, area/300) × min(1, SNR/3)
9. Annotate: green bbox + yellow CPA radial lines → save to annotated/
```

No random state anywhere. Same input → identical PNG bytes every run. Satisfies the commit-23 byte-identical DoD.

### DONKI physics fields

```
GET https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis
    ?startDate=&endDate=&mostAccurate=true

Fields used:
  speed       → speed_km_s
  halfAngle×2 → angular_width_deg
  lat/lon     → direction (earth_directed: |lat|<25 AND |lon|<30)
  time21_5    → arrival_estimate via straight-line from 21.5 R☉ to 1 AU
```

### Fallback chain

Every layer has a safe fallback so the demo never crashes:

```
PNGs exist?         YES → load them       NO → error with instructions
Detector finds CME? YES → real bbox       NO → stub bbox_norm
DONKI cache exists? YES → real physics    NO → fetch live → fail → stub speed
StormEvent built?   YES → return it       NO → load stub JSON directly
```

The stubs are last resort, not primary path. But they're always there.

---

## What Tirth's code needs (one addition)

```python
from fastapi.staticfiles import StaticFiles
app.mount("/solar-imagery", StaticFiles(directory="data/cached"), name="solar")
```

`StormEvent.cme` now includes two new fields:
- `frame_path` — relative path to the annotated PNG
- `bbox_norm` — `[x1/W, y1/H, x2/W, y2/H]` normalized to `[0,1]`

These map directly to a `position: absolute` CSS overlay rectangle. No Canvas API needed.

---

## Bug found and fixed in imp.md

`classify_flare()` in imp.md §10 had a 10× divisor error for M-class flux:

```python
# imp.md (WRONG)
n = peak_flux_wm2 / 1e-6   # M5 (5e-5 W/m²) → n=50 → key="M50" → not in map → R1

# Fixed in cv/flare_classifier.py
n = peak_flux_wm2 / 1e-5   # M5 (5e-5 W/m²) → n=5  → key="M5"  → R2 ✓
```

Same error would have made X1 return "X10" (R4) instead of "X1" (R3). Fixed in `flare_classifier.py` and covered by the parametrized test `test_classification`.

---

## Commits shipped

| # | Commit | SHA |
|---|--------|-----|
| A | `chore(cv): freeze StormEvent stubs for G4 + G5` | `ef8f94e` |
| B | `feat(cv): FITS cache + threshold CME detector` | `5c2a2e0` |
| C | `feat(cv): DONKI + flare + L1 + fusion → detect()` | `95ddf2d` |

Replaces commits 12 (partially), 13, 14, 15 from the original roadmap.  
Commit 12 preprocessing (`cv/preprocessing.py`) is **unchanged and reused**.

---

## Phase 5 — run once before demo (needs internet + AWS CLI)

```bash
python -m cv.cache_fits --storm 2024-10-G4
python -m cv.cache_fits --storm 2024-05-G5
python -m cv.donki_client --prefetch --storm 2024-10-G4
python -m cv.donki_client --prefetch --storm 2024-05-G5
python -m cv.flare_classifier --prefetch --storm 2024-10-G4
python -m cv.flare_classifier --prefetch --storm 2024-05-G5
python -m cv.l1_client --prefetch --storm 2024-10-G4
python -m cv.l1_client --prefetch --storm 2024-05-G5
python -m cv.detect --storm 2024-10-G4 --dry-run
python -m cv.detect --storm 2024-05-G5 --dry-run
```

After this, commit `data/cached/donki/*.json`, `data/cached/xrs/*.json`, `data/cached/l1/*.json`, and `data/cached/*/annotated/*.png`. The demo then has zero network dependency.
