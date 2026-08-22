# Computer Vision & ML Impact Layer — Q&A

Judge-facing reference for HelioOps **Layer ① (CV detection)** and **Layer ② (ML impact
prediction)**. Every number here is either read out of the source or measured by running
it. Where the shipped code and the designed pipeline differ, both are stated — see §8.

Source of truth: `backend/cv/**`, `backend/ml/**`. The ML layer trains and serves on
synthetic data only; §8 states exactly what that does and does not buy.

---

## §0 — The 60-second answer

**What is it?** Two layers. The CV layer turns raw coronagraph FITS images of the Sun into
a structured `StormEvent` — bounding box, central position angle, angular width, speed,
flare class, solar-wind state, confidence. The ML layer turns that `StormEvent` into two
operational impact numbers, each with a 95% prediction interval: **GPS L1 position error
(metres)** and **HF radio blackout probability (0–1)**.

**Why does it exist?** An operator cannot act on "G4 Watch, Kp 8.3". They can act on
"GPS error 11.2 m (95% CI 6.8–13.7 m), HF blackout 93%". The CV layer is what makes the
system *see* the storm rather than subscribe to someone else's alert; the ML layer is what
converts a geophysical index into a number that maps to a decision.

**The one design claim that matters:** *there is no neural network anywhere in the
detection path, on purpose.* Detection is a deterministic 9-step threshold algorithm; the
only learned component in the entire system is a small gradient-boosted quantile ensemble
whose physics is imposed as a structural constraint. That choice is defended in §6.

---

## §1 — Problem framing

### Q1.1 What exactly is the problem the CV layer solves?

A coronagraph produces a grayscale image of the solar corona every ~15 minutes. A CME
appears in it as a faint, expanding, diffuse arc — often only a few percent brighter than
the streamers and instrument background it sits on top of. The problem is:

1. **The signal is buried.** Static corona structure (streamers, F-corona, stray light,
   the occulter's own diffraction) dominates the frame. A CME is a *change*, not a
   brightness.
2. **The instrument is hostile.** Cosmic-ray hits produce single pixels at ~65,000 counts
   in a field where the corona lives at 100–800. Auto-gain drifts between frames. The
   LASCO archive mixes 512² and 1024² frames *inside one sequence*, plus 768×1024 frames
   from the 1996–2003 era.
3. **The output must be geometric, not categorical.** Downstream needs *where* the CME is
   headed (central position angle), *how wide* it is, and *how fast* — not "CME: yes".
4. **There is no labelled training set.** Nobody publishes per-pixel CME segmentation
   masks for coronagraph imagery. The catalogues that do exist (CDAW, DONKI) publish
   *kinematics*, not masks.

### Q1.2 What exactly is the problem the ML layer solves?

NOAA publishes the **G-scale** (G1–G5) and the **Kp index**. Both are *geophysical*
quantities — they describe the state of the magnetosphere. Neither is an *operational*
quantity. A dispatcher deciding whether to reroute a polar flight needs metres of GNSS
error and a probability of HF failure, with an honest uncertainty band, not an index.

There is no published closed-form `G-scale → GPS error`. The relationship is real but
non-linear, and depends on geomagnetic latitude, local time, solar EUV background and CME
kinematics. It is also strongly **heteroscedastic**: the spread of outcomes at G5 is far
wider than at G1. A regression problem that must report a *conditional distribution*, not
a point estimate, is exactly what quantile regression is for.

### Q1.3 Why run CV at all when NASA DONKI already publishes CME data?

We run both, deliberately, because they answer different questions and fail differently:

| | CV detector | NASA DONKI |
|---|---|---|
| Answers | *where* in the image, *which direction*, *how wide it looks*, *how confident* | *how fast*, *how wide*, *when it arrives* |
| Latency | frame-time (~15 min) | hours — a human analyst reviews it |
| Availability | always, offline, from pixels we already hold | HTTP endpoint; may be stale or empty |
| Failure mode | degrades to a stub bbox | degrades to a stub speed |

DONKI's kinematics are **human-reviewed and therefore better than anything we could fit**,
so we take speed and width from it. But DONKI is not real-time and can be missing; the CV
detector is what makes the system independent, and it produces the annotated frame an
operator actually looks at. Using both is not redundancy — each source does the part it is
authoritative for.

### Q1.4 What is the interface between the two layers?

`backend/cv/storm_event_generator/fusion.py::StormEvent` — a Pydantic model, the single
contract every downstream layer reads. The ML layer's `predict()` takes
`StormEvent.model_dump()` (a plain dict) and returns an `ImpactPrediction`. Neither layer
imports the other; `backend/pipeline.py` wires them through adapters.

---

## §2 — CV: data ingestion

### Q2.1 What instruments, and why those?

| Storm | Instrument | Why |
|---|---|---|
| 2024-10-G4 | **CCOR-1** — Compact Coronagraph, GOES-19 | Current operational NOAA coronagraph; 15-min cadence; publicly mirrored to S3, no auth |
| 2024-05-G5 | **SOHO/LASCO C2 + C3** | The May 2024 Gannon storm predates CCOR-1 operations; LASCO is the 28-year archive of record |

Fetched by `cv/data_ingestion/cache_fits.py`: `sync_ccor1()` shells out to
`aws s3 sync --no-sign-request`; `fetch_lasco()` uses **SunPy Fido**, the standard
solar-physics data broker.

### Q2.2 What is a coronagraph, and what is an occulter?

A coronagraph is a telescope with a physical disk — the **occulter** — blocking the solar
photosphere so the corona (about a million times fainter) becomes visible. Three
consequences the algorithm has to respect:

- The image centre is a black (or saturated) disk carrying no information. Every statistic
  must exclude it.
- The occulter's centre *is* the solar centre. Every angular measurement is referenced to
  it, so finding it accurately is a hard prerequisite (§3.4).
- LASCO C2 covers ~2–6 R☉ (solar radii), C3 ~3.7–30 R☉. That is why the detector's outer
  limit is a radius in pixels, not the frame edge.

### Q2.3 What is FITS and what breaks when reading it?

**FITS** (Flexible Image Transport System) is the astronomy standard container: a header of
`KEY = value` cards plus a binary array, in one or more **HDUs** (Header/Data Units).
`_load_raw_fits()` handles three real-world failures:

- **Multi-HDU files** — the image is not always HDU[0]; we scan for the first 2-D HDU.
- **`BSCALE` / `BZERO`** — LASCO stores integers with a linear rescale to physical units:
  `physical = raw × BSCALE + BZERO`. Skipping it gives numerically wrong pixel values.
- **`BLANK`** — the missing-pixel sentinel in older SOHO data. Left in, it becomes a huge
  outlier that defeats the percentile clip.

### Q2.4 What is DONKI and how is a CME selected from it?

**DONKI** = Space Weather Database Of Notifications, Knowledge, Information (NASA CCMC).
Its `CMEAnalysis` endpoint publishes analyst-fitted CME kinematics. `select_best_cme()`:

1. Keep records with `isMostAccurate == True` — DONKI's own flag for the analyst's final
   fit when several exist for one event.
2. Keep those with `time21_5` within ±12 h of the storm date. **21.5 R☉** is the standard
   measurement radius: it is the inner boundary of the WSA–ENLIL heliospheric model, so
   every operational CME fit is quoted there.
3. Take the **highest-speed** survivor. Rationale: when several CMEs erupt in a window, the
   fast one arrives first and dominates the geomagnetic response.
4. If nothing carries `isMostAccurate`, relax to any record in the window rather than
   return nothing.

`cme_to_fields()` converts: `angular_width_deg = halfAngle × 2` (DONKI publishes the
half-angle of the cone fit), and the arrival estimate from straight-line transit,
`t_arrival = time21_5 + (1 AU − 21.5 R☉) / speed`. Direction is `earth_directed` when
`|lat| < 25°` and `|lon| < 30°`, else `off_limb`.

### Q2.5 How are flares classified?

`flare_classifier.py` reads **GOES XRS** 1-minute long-channel (0.1–0.8 nm) X-ray flux in
W/m² from SWPC and applies the NOAA scheme — a base-10 logarithmic ladder:

| Class | Peak flux (W/m²) | NOAA R-scale |
|---|---|---|
| C | ≥ 1e-6 | 0 (no operational impact) |
| M1–M4 | ≥ 1e-5 | R1 |
| M5–M9 | ≥ 5e-5 | R2 |
| X1–X9 | ≥ 1e-4 | R3 |
| X10–X19 | ≥ 1e-3 | R4 |
| X20+ | ≥ 2e-3 | R5 |

The class *number* is the multiplier inside the decade: `X5.8` = `5.8e-4 W/m²`. Pinned by
tests against both anchors: Oct 2024 = X1.8 → R3, May 2024 = X5.8 → R3.

X-rays travel at c, so the flare's HF effect (dayside D-region absorption) is **already
happening** when you see the flare — 8 minutes late, no warning. This is why R-scale enters
the HF model but not the GPS model's arrival timing.

### Q2.6 What does the L1 client contribute?

`l1_client.py` reads **DSCOVR** real-time solar wind from the **L1 Lagrange point**
(~1.5 million km sunward of Earth): **Bz** (north–south interplanetary magnetic field
component in the GSM frame), bulk speed, and proton density.

Bz is the single most important scalar in the system. **Southward Bz (negative) reconnects
with Earth's northward dayside field and is what makes a CME geoeffective.** A fast CME
arriving with northward Bz does comparatively little damage. This is why `fuse()` gives
southward Bz a 20% weight in confidence and why the ML feature set constrains `bz_nt` to a
*negative* monotone relationship with GPS error.

L1 buys roughly **15–60 minutes of warning**: `eta_minutes = 1.5e6 km / speed / 60`.

---

## §3 — CV: preprocessing algorithms

`backend/cv/image_threshold_algorithm/preprocessing.py`

### Q3.1 `load_ccor1_frame()` — the six steps and the reason for each

| Step | Operation | Why |
|---|---|---|
| 1 | `np.nan_to_num` on NaN/±Inf | Dead detector pixels propagate NaN through every later mean/std |
| 2 | **Letterbox pad to square** | A 768×1024 LASCO frame squashed straight to 512² compresses x by 1.33× more than y — the circular occulter becomes an ellipse and **every CPA derived from it is geometrically wrong**. Zero-padding to 1024² first makes the resize isotropic |
| 3 | **Percentile clip [0.5, 99.5]** | A cosmic-ray hit at 65,000 in a corona living at 100–800. Min–max normalising *after* that spike squeezes the entire corona into the bottom ~1.2% of [0,1] — a visually black image. This was a real bug; `test_cosmic_ray_removed` pins the fix |
| 4 | **`log1p` scale** | Coronal brightness falls off as a steep power law with radius. A linear stretch renders the outer corona invisible. `log(1+x)` compresses the bright inner region and expands the faint outer one — precisely the region where CMEs become detectable |
| 5 | Min–max to [0,1] | Puts every frame on one comparable scale |
| 6 | Resize to 512², `INTER_AREA` down / `INTER_CUBIC` up | The LASCO archive mixes 512² and 1024² *within one sequence*; `running_difference()` subtracts frame pairs and would raise a NumPy broadcast error. Normalising shape here makes every downstream consumer shape-safe |

> `INTER_AREA` is pixel-area resampling — it averages the source pixels falling into each
> destination pixel, the correct anti-aliased downsample. `INTER_CUBIC` fits a bicubic
> surface over a 4×4 neighbourhood, smoother than bilinear when upscaling.

### Q3.2 `running_difference()` — what it is and why it is the core trick

A **running difference** image is `frame[i] − frame[i−1]`. It is the standard technique in
coronagraph analysis and the single most important step in the detector: **it cancels
everything static.** Streamers, the F-corona, stray light, occulter diffraction — identical
between consecutive frames, all subtract to zero. What survives is *moving material*: the
CME front as a bright arc, and its wake as a dark region.

Four operations, each fixing a specific artefact:

1. **Float subtraction.** Positive = new material arrived, negative = material left. Both
   are signal; the naive version clipped negatives to zero and threw the wake away.
2. **Median correction** — subtract the median of the difference over the corona mask.
   Removes global brightness shifts from LASCO auto-gain drift. Without it a gain step
   between two frames looks like the whole corona brightening at once.
3. **Sigma clip at ±3σ** — cosmic rays that survived the loader leave residuals in the
   difference; clipping at 3 standard deviations removes them without touching the arc.
4. **Rescale to [0,1] centred on 0.5.** Grey = no change, bright = new material, dark =
   vacated. Pinned by `test_fix_b_midpoint_near_neutral`.

> Related technique, not used: **base difference** (subtract one fixed pre-event frame),
> which preserves cumulative structure but drifts as the corona evolves. Running difference
> is the correct choice for detecting the *front*.

### Q3.3 What is CLAHE, and why not plain histogram equalisation or a blur?

**CLAHE** = Contrast Limited Adaptive Histogram Equalisation (Zuiderveld, 1994). Ordinary
histogram equalisation remaps intensities *globally*, so the bright inner corona dominates
the transform and the faint outer arc stays flat. CLAHE splits the image into tiles
(`tileGridSize=(8,8)`), equalises within each, then bilinearly interpolates across tile
boundaries to avoid seams. The "contrast limited" part clips each tile's histogram at
`clipLimit=2.0` and redistributes the excess — without it, adaptive equalisation amplifies
noise in flat regions until the image is destroyed.

Net effect: a faint CME arc at the edge of the field becomes visible without blowing out
the already-bright inner region. The old code used `GaussianBlur` as its "contrast" step;
blur *removes* information, it does not reveal it. We still apply a 3×3 Gaussian, but
afterwards and only as sensor read-noise denoise.

### Q3.4 What is the Hough Circle Transform and where is it used?

`find_occulter_center()` uses `cv2.HoughCircles` with `HOUGH_GRADIENT`. The Hough transform
is a **voting scheme in parameter space**: each edge pixel votes for the `(cx, cy, r)`
circles it could lie on, and peaks in the accumulator are detected circles.
`HOUGH_GRADIENT` is the efficient variant — it uses the Sobel gradient direction at each
edge pixel to vote along a line rather than a full circle, collapsing the accumulator from
3-D to effectively 2-D plus a radius pass.

Parameters: `dp=1` (accumulator at image resolution), `minDist=h/4` (only one occulter
expected), `param1=50` (upper Canny threshold), `param2=30` (accumulator threshold — lower
means more circles and more false ones), `minRadius=h/12`, `maxRadius=h/4`.

**Fallback when Hough fails on a noisy frame:** binary threshold — inverted for a dark
occulter, direct for a saturated bright one, chosen by sampling the central crop's mean —
then `findContours` plus **image moments**. The centroid is `(M10/M00, M01/M00)`, where
`M00` is contour area and `M10`, `M01` are first-order spatial moments. Never raises;
degrades to image centre.

**Why the precision matters:** CPA is measured from the solar centre. A 5-pixel centre
error on a 512-px image is a ~0.6° *systematic* CPA bias on every frame — a bias, not
noise, so it never averages out.

---

## §4 — CV: the 9-step detection algorithm

`backend/cv/image_threshold_algorithm/threshold_detector.py::detect_cme_in_frame`

Input: one running-difference frame plus its normalised frame. Output: a dict with
`detected`, `bbox_px`, `bbox_norm`, `cpa_deg`, `width_deg_visual`, `confidence`,
`centroid_px`, `snr`, `n_bright_px`.

### Step 1 — Annular mask

`_annular_mask()` builds a boolean ring: `inner_r = occulter_r + 10 px`,
`outer_r = 220 px`. Everything inside the occulter (no information) and everything outside
the useful field (vignetted corners, the octagonal instrument mask, pure noise) is
excluded.

Implemented with `np.ogrid` broadcasting — an `(H,1)` and a `(1,W)` index array produce the
full distance matrix without materialising two `(H,W)` meshgrids. `ANNULAR_OUTER_PX = 220`
at 512 px corresponds to roughly 6 R☉ for LASCO C2.

### Step 2 — Per-frame statistics inside the mask

`μ` and `σ` computed over masked pixels only. **Per-frame, not global**, because the noise
floor changes between frames (exposure, gain, solar activity). A fixed global threshold
would be too sensitive on quiet frames and blind on noisy ones. Guard: `σ < 1e-6` returns
no-detection rather than dividing by zero.

### Step 3 — Threshold at μ + 2.5σ

`bright_mask = (diff > μ + 2.5σ) & annular_mask`.

**Why 2.5σ?** For an approximately Gaussian noise field, 2.5σ is a one-sided
false-positive rate of ~0.62%. On the ~130k pixels in the annulus that is ~800 false
pixels — deliberately more than a real CME's area, because steps 4–5 are what remove them:
false positives are *spatially scattered* while a CME is *spatially contiguous*. Thresholding
loosely and then filtering on connectivity is far more robust than thresholding tightly and
missing faint fronts. `MIN_BRIGHT_PX = 40` is the early exit.

> This is the classic detection-theory trade-off. We sit deliberately toward high
> sensitivity at the pixel stage and recover specificity geometrically.

### Step 4 — Morphological open then close

`cv2.morphologyEx` with a 3×3 **elliptical structuring element**.

- **Opening** = erosion then dilation. Removes isolated bright specks smaller than the
  kernel — exactly the scattered false positives from step 3 — without shrinking large
  regions.
- **Closing** = dilation then erosion. Fills small holes and bridges gaps *within* the CME
  arc, so a front broken by noise becomes one connected object rather than five.

Order matters: open first (kill noise), close second (heal the real object). Doing it the
other way round would first fatten the noise and then fail to remove it.

### Step 5 — Connected components, take the largest

`cv2.connectedComponentsWithStats` labels every 8-connected blob and returns area,
bounding box and centroid per label. We take the largest blob with area above
`MIN_COMPONENT_PX = 30`.

**Why the largest?** A CME front is by far the largest coherent moving structure in the
field. Smaller components are residual noise, streamer wobble or a second, weaker
transient. This is a documented simplification: *the detector reports one CME per frame*.

### Step 6 — Bounding box

Padded by `BBOX_PAD_PX = 20` on each side (the threshold clips the faint outer edge of the
front, so the tight box systematically undercuts the true extent), clipped to image bounds,
and emitted in **two coordinate systems**: `bbox_px` in pixels for annotation, and
`bbox_norm` in `[0,1]` — resolution-independent, so the frontend can overlay it on any
display size without knowing the source resolution.

### Step 7 — CPA and angular width (polar geometry)

**CPA (Central Position Angle)** is the standard coronagraph coordinate: the angle of the
CME's centre measured **from solar North, counterclockwise**, in degrees. It is what tells
you whether the CME is headed at Earth, over a pole, or off the limb.

Two conversions happen here, and both are easy to get wrong:

1. **Image coordinates have y increasing downward.** So the image angle is
   `atan2(−(y − cy), x − cx)` — note the negated y. Forgetting the sign flips the CME
   north–south.
2. **Image angle is measured from +x (East, CCW); CPA is measured from North (up, CCW).**
   Hence `cpa_deg = (90 − cpa_image) mod 360`.

**Circular statistics, not arithmetic means.** Angles wrap at 0/360, so `mean(350°, 10°)`
is `180°` arithmetically and `0°` correctly. `_circular_mean_deg()` converts each angle to
a unit vector, averages the vectors, and takes `atan2(mean sin, mean cos)`. Pinned by
`test_circular_mean_0_360_boundary`.

`_circular_range_deg()` computes the width as twice the maximum angular deviation from the
circular mean, using `np.angle(np.exp(1j·Δ))` to wrap differences into `[−π, π]`, capped at
360°. The output is named **`width_deg_visual`** on purpose — it is the *apparent* width in
the plane of the sky, which is not the same quantity as DONKI's cone-fit `halfAngle × 2`.
They are kept as separate fields rather than conflated.

### Step 8 — Confidence

```
snr        = (mean(component) − mean(background)) / (std(background) + 1e-8)
conf_area  = min(1, area / 300)
conf_snr   = min(1, snr / 3)
confidence = conf_area × conf_snr
```

Background statistics are recomputed over `mask & (labels == 0)` — pixels in the annulus
that are *not* part of any detected component. Using the original `μ`/`σ` from step 2 would
include the CME's own pixels in its own background estimate and deflate the SNR.

**Multiplicative, not additive**, deliberately: a large but low-contrast blob (a gain
artefact) and a tiny but very bright blob (a cosmic ray that survived) should *both* score
low. A sum would let either one carry the score alone; a product requires both to be
plausible. Both factors are saturating (`min(1, ·)`), so the output is bounded in [0,1] —
pinned by `test_confidence_between_0_and_1`.

### Step 9 — Annotation

Green bounding box, yellow radial rays at CPA and CPA ± width/2 drawn from the occulter
centre, and a text overlay (CPA, visual width, confidence, DONKI speed, ETA) with a
one-pixel black shadow for legibility on both bright and dark backgrounds. Integer pixel
coordinates only, so `cv2.putText` output is byte-stable.

### Q4.1 How does the sequence-level detector work?

`detect_cme_in_sequence()` runs the frame detector over every difference frame and returns
`best_frame_idx` — the frame with maximum confidence — plus `detected_count`. Alignment:
`diff_frames[i]` corresponds to `norm_frames[i+1]`, because a difference needs a previous
frame and frame 0 has none. There are always N−1 differences for N frames.

**Known simplification:** this is *max-confidence selection*, not *tracking*. It does not
associate the same CME across frames or fit a height–time curve. That is why plane-of-sky
speed from `estimate_speed_from_centroids()` is a fallback only, and DONKI supplies speed
whenever it is available.

### Q4.2 Is the detector deterministic, and why does that matter?

Yes — no RNG, no learned weights, no thread-order dependence. The same input frames
produce a byte-identical result dict and a byte-identical annotated PNG. Pinned by
`test_determinism`.

Why it matters: this is a system whose whole pitch is auditability. If an operator acts on
an advisory and there is an inquiry six months later, the pipeline must reproduce exactly
what it saw. A stochastic detector makes "what did the system see at 03:14?" an
unanswerable question.

---

## §5 — CV: fusion into a StormEvent

`backend/cv/storm_event_generator/fusion.py::fuse`

### Q5.1 How is the overall event confidence computed?

A fixed weighted sum of four independent evidence channels:

| Weight | Evidence | Rationale |
|---|---|---|
| 0.40 | CV visual confidence (continuous) | The only *direct* observation of the eruption |
| 0.20 | Flare detected (binary) | Corroborating eruption signature at a different wavelength |
| 0.20 | Southward Bz at L1 (binary, `bz < 0`) | Geoeffectiveness — the physics gate |
| 0.20 | A NOAA alert exists (binary) | Independent human/agency corroboration |

The CV channel carries the largest single weight but **cannot exceed 0.40 on its own** —
a confident detection of a CME that is not geoeffective and not corroborated tops out
below 0.5. That is the intended behaviour: the visual is necessary, not sufficient. The
weights are hand-set and calibrated against NOAA post-event reports; they are not fitted,
and we say so.

### Q5.2 What else does fusion assemble?

- **Scales** — G (geomagnetic, from L1/NOAA), S (solar radiation, from proton flux), R
  (radio blackout, from X-ray flux). The three NOAA Space Weather Scales.
- **ETA** — `1.5e6 km / speed_km_s / 60` minutes, the L1-to-Earth transit.
- **Timeline** — three horizons: `days_out` (CME arrival estimate from DONKI),
  `one_hour` (L1 measurement time), `onset` (geomagnetic). These map to the three genuinely
  different lead times operators plan against.
- **`noaa_alert_raw`** — the verbatim alert text, kept for provenance.

### Q5.3 What happens when something is missing?

Every stage has a fallback and none of them raise:

```
No preprocessed PNGs      -> load the stub StormEvent JSON
Detector finds nothing    -> stub bbox, confidence 0.5, width 110°
No DONKI record           -> stub speed / width / arrival
Annotation write fails    -> log, continue without the PNG
fuse() raises             -> load the stub StormEvent JSON
```

Design rule: **degrade, never hard-fail.** A space-weather console that returns HTTP 500
during a G5 is worse than one that returns a conservative estimate with a lowered
confidence. Pinned by `TestDetectStubFallback`.

---

## §6 — Why there is no CNN (the flagship design decision)

An earlier version of this repo contained `cv/cmecnn.py` — a convolutional network for CME
segmentation. **It was deleted.** This is the most important engineering judgement in the
project and it should be argued, not apologised for.

### Q6.1 Why delete it?

**1. The labels do not exist.** Supervised segmentation needs per-pixel masks. No public
dataset provides them for coronagraph CMEs. What exists — CDAW, DONKI — is *kinematics*
(speed, width, PA), which is a different target and is itself partly subjective. Training a
segmentation CNN would have meant generating our own masks, i.e. **training a model to
reproduce the output of the threshold algorithm we already have.** That is a distillation
exercise dressed up as machine learning: strictly worse than the teacher, plus a GPU.

**2. Determinism is a product requirement here, not a preference.** See Q4.2.

**3. The physics is already known.** A CNN would have to *learn* that a CME is a bright
contiguous outward-moving region in a difference image. We can simply write that down. ML
earns its keep where the mapping is unknown or too complex to specify — which is exactly
where we *do* use it (§7), and not here.

**4. Operational cost.** No GPU, no weights file, no CUDA in the container, ~15 ms per
frame on CPU, and it runs unchanged on a free-tier CPU host.

### Q6.2 Isn't a threshold detector just less capable?

On some axes, yes, and we name them (§6.4). But compare against the honest alternative,
which is not "a good CNN" — it is "a CNN trained on labels we fabricated":

| | Threshold detector | CNN on self-generated labels |
|---|---|---|
| Ceiling | The algorithm's own accuracy | The threshold algorithm's accuracy, minus distillation loss |
| Reproducible | Byte-identical | Depends on seed, device, cuDNN version |
| Explainable to a regulator | Nine steps with published constants | Saliency maps, at best |
| Fails how | Predictably: low SNR → low confidence | Unpredictably: out-of-distribution → confident nonsense |
| Cost | 15 ms CPU | GPU, weights, training rig |

### Q6.3 What is the academic prior art, and where does this sit?

Automated CME detection has a real literature and this detector is squarely in it:

- **CACTus** (Robbrecht & Berghmans, 2004) — the classic. Runs a Hough transform in
  `[time, position-angle]` space on running-difference maps unwrapped to polar
  coordinates; a CME is a ridge in that space.
- **SEEDS** (Solar Eruptive Event Detection System; Olmedo et al., 2008) — thresholds a
  polar-transformed running-difference image, then segments by region growing. **This is
  the closest relative of our approach.**
- **ARTEMIS** (Boursier et al., 2009) — filtering plus a similar polar-space segmentation.
- **CORIMP** (Byrne et al., 2012) — multiscale edge detection with a deconvolution-based
  removal of the static corona instead of a running difference.

Ours is a SEEDS-family detector operating in Cartesian rather than polar coordinates, with
the polar conversion applied at the measurement stage (step 7) instead of the segmentation
stage. **Deep learning is a minority approach in this field, not the default** — precisely
because of the labelling problem.

### Q6.4 What are the honest limitations of the threshold detector?

State these before a judge finds them:

1. **Halo CMEs.** An Earth-directed CME appears as a ring surrounding the occulter, so its
   circular mean CPA is close to meaningless and the visual width saturates. Mitigation:
   DONKI's cone fit provides the true width, and `is_halo` (`width ≥ 270°`) is an explicit
   feature in the ML layer.
2. **Plane-of-sky projection.** Every coronagraph measurement is a 2-D projection of a 3-D
   eruption; apparent speed and width underestimate the true values, worst exactly for
   Earth-directed events. Same mitigation — DONKI's fit is 3-D-informed.
3. **One CME per frame.** Largest-component selection cannot report two simultaneous
   eruptions.
4. **No tracking.** Max-confidence frame selection rather than height–time fitting.
5. **Fixed constants.** 2.5σ, 220 px, 300 px area scale are hand-tuned for CCOR-1/LASCO at
   512². Another instrument needs recalibration — these are calibration knobs, and they are
   named module-level constants for exactly that reason.
6. **Occulter-radius dependency.** If the `_meta.txt` sidecar is missing,
   `DEFAULT_OCCULTER_R = 80` is used for every frame, which is a known accuracy loss. This
   is documented in `AGENTS.md`, not hidden.

---

## §7 — ML: the impact layer

`backend/ml/inference.py`, `backend/ml/01_data_generation_eda.py`,
`backend/ml/02_train_and_tune.py`, `backend/ml/03_anchor_test.py`

### Q7.1 What does it predict, and what is the output contract?

```python
class ImpactPrediction(BaseModel):
    gps_error_m: float           # GPS L1 position error, metres
    gps_error_ci_low: float      # 2.5th percentile
    gps_error_ci_high: float     # 97.5th percentile
    hf_blackout_prob: float      # probability in [0, 1]
    hf_blackout_ci_low: float
    hf_blackout_ci_high: float
```

Measured live on the two anchor storms:

| Storm | Scales | GPS error (m) | 95% CI | HF blackout | 95% CI |
|---|---|---|---|---|---|
| 2024-10-G4 | G4 S2 R3 | 11.23 | 6.83 – 13.67 | 0.932 | 0.870 – 0.999 |
| 2024-05-G5 | G5 S3 R5 | 22.02 | 13.34 – 25.92 | 0.947 | 0.928 – 1.000 |

### Q7.2 Why quantile regression rather than ordinary regression?

**The contract demands an interval, and the interval must mean something.** Three reasons:

1. **Operators need a worst case.** A dispatcher plans against `ci_high`, not the median.
   "12 m expected" is planning information; "up to 26 m" is the number that closes a polar
   route.
2. **The noise is heteroscedastic.** A point regressor plus a single global error bar
   assumes constant variance. Storm impacts do not have constant variance — the conditional
   spread at G5 is several times that at G1. Quantile regression models each quantile of
   the conditional distribution separately, so the interval *widens where the physics is
   genuinely more uncertain*.
3. **It requires no distributional assumption.** Gaussian error bars would be wrong: the
   GPS-error distribution is heavy-tailed and strictly non-negative.

We fit three quantiles: **α = 0.025, 0.500, 0.975** — the median plus a 95% interval.

### Q7.3 What is pinball loss?

The training objective of quantile regression, also called quantile loss or check loss:

```
L_α(y, ŷ) = max( α·(y − ŷ), (α − 1)·(y − ŷ) )
```

It is asymmetric. For α = 0.975 an under-prediction is penalised 0.975 per unit while an
over-prediction is penalised 0.025 per unit — a 39:1 ratio — so the minimiser is pushed up
to the 97.5th percentile. At α = 0.5 the penalties are symmetric and it reduces to
mean-absolute-error, whose minimiser is the median. Minimising `L_α` in expectation is
provably minimised at the true conditional α-quantile; that is the whole theoretical basis.

Implemented in `02_train_and_tune.py::pinball_loss` and used as the Optuna objective.

### Q7.4 Why gradient-boosted trees rather than a neural network?

| Requirement | Consequence |
|---|---|
| Tabular data, tens of features, ~10⁵ rows | GBDTs are the empirically dominant model class in this regime; a net has no structure to exploit |
| CPU inference under 50 ms | 6 checkpoints totalling ~470 KB, no GPU, no ONNX runtime |
| Monotone physics constraints | **GBDTs support hard monotone constraints natively; neural networks do not** without architectural surgery |
| Explainability to a regulator | Tree paths and feature importances are inspectable; per-split contributions are exact |
| Non-linear thresholded physics | Impact turns on sharply above Kp ≈ 5 — trees represent thresholds natively, whereas a net must approximate a step with smooth activations |

A measured negative result worth keeping: on a GPU a 200-round fit takes 5.76 s CUDA vs
8.51 s CPU — 1.5×, not 10×. At this data size the GPU is not the bottleneck, and a
sequence model is not worth adding unless the trees are shown to plateau.

### Q7.5 What are the features?

**Shipped model — 9 features** (`inference.py::_FEATURE_COLS`):

`g_scale`, `kp_index`, `bz_nt`, `wind_speed_km_s`, `cme_speed_km_s`, `cme_width_deg`,
`r_scale`, `geomag_lat_bin`, `local_time_bin`.

`kp_index` is derived from `g_scale` via the NOAA mapping
`{0:0, 1:5, 2:6, 3:7, 4:8.3, 5:9}`. `geomag_lat_bin` (0 = low, 1 = mid, 2 = auroral) and
`local_time_bin` (0 = night, 1 = day) are currently **hardcoded to mid-latitude / dayside**
— a known placeholder pending per-region inference, called out honestly in Q11.4.

## §8 — ML: what is shipped today versus what is designed

**Be up front about this. A judge who discovers it is much worse than a judge who is told.**

### Q8.1 What is actually running?

`backend/ml/checkpoints/` holds **six LightGBM quantile models** (~470 KB total) — GPS and
HF, each at α ∈ {0.025, 0.5, 0.975} — trained by `02_train_and_tune.py` on
`backend/ml/data/synthetic_storms.csv`: **4,800 rows, 120 synthetic storms × 40 frames**,
generated by `01_data_generation_eda.py` from a hand-written physics-shaped rule with
`np.random.seed(42)`.

Training used Optuna (15 trials per quantile) with `GroupKFold(n_splits=5)` grouped on
`storm_id`, minimising pinball loss, plus LightGBM early stopping.

**What that means honestly:** the shipped model reproduces a *designed* relationship with
calibrated uncertainty. It demonstrates the architecture end to end and it passes the
physical sanity anchors. It is **not** yet evidence of predictive skill on real storms,
because its labels were authored, not observed. Saying anything stronger would be a claim
the data does not support.

### Q8.2 Was there a real-data track, and where did it go?

Yes, and it was **removed** rather than left in the tree as scaffolding.

An earlier iteration downloaded NASA OMNI2 hourly (1996–2025), built a 38-feature physics
matrix from it with published coupling functions, and ran a distributed Optuna HPO harness
across worker pods. It ran end to end on the drivers — and it was permanently blocked on
the one thing OMNI does not contain: **labels**. OMNI carries every input and no target.
`target_gps_error` would have needed IONEX Global Ionosphere Maps; `target_hf_prob` would
have needed GOES XRS/SEP. Neither exists as a published time series in the form required,
and building both was out of scope.

So the repo now contains exactly one ML pipeline — the synthetic one — and 296 MB of OMNI
data, the feature builder and the HPO pods are gone. The reasoning: a scaffolded pipeline
that cannot be trained is indistinguishable, to anyone reading the tree, from one that can.
Deleting it makes the honest claim in Q8.1 the *only* claim the repo supports.

If the label problem is ever solved, the design notes live in this file's git history.

## §9 — ML: the methodology behind what ships

Every item here is implemented in `02_train_and_tune.py` or `inference.py` and its
numbers are measured on the synthetic set, not asserted.

### Q9.1 Why `GroupKFold` on `storm_id`?

Each synthetic storm contributes 40 frames that share one base profile — Kp, wind speed,
CME speed and width are drawn once per storm and jittered per frame. A random row split
therefore puts near-duplicate rows on both sides of the fold boundary and the CV loss comes
out meaninglessly good. `GroupKFold(n_splits=5)` grouped on `storm_id` keeps every frame of
a storm on one side.

This is the right tool *for this data*. It would not be sufficient on a real geophysical
time series, where autocorrelation crosses event boundaries and a purged/embargoed time
split is required instead — but the shipped data has no time axis to leak along.

### Q9.4 What is quantile crossing and how is it handled?

Fitting three quantiles as three independent models gives no guarantee that
`q025 ≤ q500 ≤ q975` at every input — a nonsensical interval. `inference.py` applies a
`sorted()` guard on each triple, which is the standard cheap fix. The three models are
fitted independently, so crossing is genuinely possible near the edges of the feature
space; `03_anchor_test.py` asserts `q025 <= q500 <= q975` on both anchors.

### Q9.6 What are PICP and PINAW?

- **PICP** — Prediction Interval Coverage Probability: the fraction of true values falling
  inside the predicted interval. For a 95% interval it should be ≈ 0.95.
- **PINAW** — Prediction Interval Normalised Average Width: mean interval width divided by
  the range of the target. It is the *cost* of that coverage.

They must be read together. PICP alone is trivially gamed — predicting `(−∞, +∞)` gives
100% coverage and is useless. PINAW is what stops that.

Measured on the last training run (`02_train_and_tune.py` prints both):

| Target | PICP (nominal 95%) | PINAW |
|---|---|---|
| GPS L1 error | **95.90%** | 0.0369 |
| HF blackout probability | **94.21%** | 0.1941 |

Both land within ~1 point of nominal at a narrow interval width, which is the whole
claim the quantile objective is making.

### Q9.8 What is Optuna doing, and what is TPE?

**Optuna** is the hyperparameter optimisation framework. **TPE** (Tree-structured Parzen
Estimator) is its default sampler: rather than modelling `p(score | params)` like a
Gaussian-process Bayesian optimiser, it models `p(params | score)` as two densities — one
over the best trials `l(x)` and one over the rest `g(x)` — and samples the point maximising
`l(x)/g(x)`. Cheaper than a GP and handles conditional/categorical spaces naturally.

The shipped run is deliberately small: **15 trials per quantile**, six quantiles, single
process, minimising 5-fold grouped pinball loss with LightGBM early stopping inside each
fold. The whole thing finishes in a couple of minutes on a laptop, which is the point —
the checkpoints are cheap to regenerate, so nobody is tempted to treat a stale pkl as
precious.

## §10 — Glossary

Every domain and technical term used above, in one place.

### Solar physics and space weather

| Term | Meaning |
|---|---|
| **CME** | Coronal Mass Ejection — a billion-tonne eruption of magnetised plasma from the solar corona |
| **Corona** | The Sun's outer atmosphere, ~10⁻⁶ the photosphere's brightness |
| **Coronagraph** | Telescope with an occulting disk that blocks the photosphere so the corona is visible |
| **Occulter** | That blocking disk. Its centre is the solar centre for all angular measurements |
| **R☉** | Solar radius, 695,700 km — the standard length unit in coronagraph work |
| **AU** | Astronomical Unit, ~149.6 million km, Sun–Earth distance |
| **L1** | First Sun–Earth Lagrange point, ~1.5 million km sunward; where DSCOVR sits, giving 15–60 min warning |
| **CPA** | Central Position Angle — CME direction measured from solar North, counterclockwise |
| **Halo CME** | Apparent width ≥ ~270°; surrounds the occulter, meaning it is coming at (or away from) the observer |
| **Plane-of-sky** | The 2-D projection a coronagraph sees; underestimates true speed/width for Earth-directed events |
| **Running difference** | `frame[i] − frame[i−1]`; cancels static structure so only moving material remains |
| **IMF** | Interplanetary Magnetic Field — the solar magnetic field carried out by the solar wind |
| **Bz (GSM)** | North–south IMF component in Geocentric Solar Magnetospheric coordinates. **Southward (negative) = geoeffective** |
| **Clock angle θc** | `atan2(By, Bz)` — IMF rotation in the plane perpendicular to the Sun–Earth line |
| **Kp** | Planetary K index, 0–9, 3-hourly, from 13 subauroral magnetometers. The standard geomagnetic-activity index |
| **Dst** | Disturbance Storm Time index — measures ring-current strength; integrates over ~24 h |
| **AE / AL** | Auroral Electrojet indices — high-latitude current strength; respond within ~6 h |
| **G-scale** | NOAA geomagnetic storm scale, G1 (Kp 5) to G5 (Kp 9) |
| **R-scale** | NOAA radio blackout scale, R1–R5, from GOES X-ray flux |
| **S-scale** | NOAA solar radiation storm scale, S1–S5, from >10 MeV proton flux |
| **GOES XRS** | X-Ray Sensor on the GOES satellites; the long channel (0.1–0.8 nm) defines flare class |
| **Flare class** | Logarithmic ladder C/M/X by peak W/m²; the number is the multiplier within the decade |
| **SEP** | Solar Energetic Particle event; causes polar cap absorption and elevated radiation dose |
| **D-region** | Lowest ionospheric layer (~60–90 km); where HF absorption happens |
| **SZA** | Solar Zenith Angle; D-region absorption ∝ `cos^0.75(SZA)` |
| **TEC / TECU** | Total Electron Content; 1 TECU = 10¹⁶ electrons/m². Drives GNSS group delay |
| **F10.7** | 10.7 cm solar radio flux (sfu); the standard proxy for solar EUV / background ionisation |
| **Solar cycle SC23/24/25** | ~11-year activity cycles; SC23 1996–2008, SC24 2009–2019, SC25 2020– |
| **DONKI** | NASA CCMC's space-weather event database; publishes analyst-fitted CME kinematics |
| **Ionosonde / GIRO** | Vertical-sounding radar; "no echo" is a *measured* HF blackout. GIRO/DIDBase is the global network |

### Computer vision

| Term | Meaning |
|---|---|
| **FITS** | Flexible Image Transport System — the astronomy image container |
| **HDU** | Header/Data Unit; a FITS file may hold several |
| **BSCALE / BZERO** | Linear rescale from stored integers to physical units |
| **BLANK** | FITS sentinel for a missing pixel |
| **Letterbox padding** | Zero-pad to square before resizing, so the resize is isotropic and circles stay circular |
| **Percentile clipping** | Clamp to the [0.5, 99.5] percentile range to remove outliers before normalisation |
| **log1p scaling** | `log(1+x)`; compresses a power-law dynamic range so faint structure survives |
| **CLAHE** | Contrast Limited Adaptive Histogram Equalisation — per-tile equalisation with a clip limit |
| **Sigma clipping** | Clamp to ±Nσ about the mean to remove outliers |
| **Annular mask** | Ring-shaped region of interest; excludes the occulter and the far field |
| **Morphological opening** | Erosion then dilation; removes specks smaller than the structuring element |
| **Morphological closing** | Dilation then erosion; fills holes and bridges gaps within an object |
| **Structuring element** | The kernel shape a morphological operation probes with (here a 3×3 ellipse) |
| **Connected components** | Labelling of contiguous (8-connected) foreground pixels into distinct objects |
| **Bounding box** | Axis-aligned rectangle enclosing an object; here emitted normalised to [0,1] |
| **Centroid** | Object's mean position; from `connectedComponentsWithStats`, or from image moments `(M10/M00, M01/M00)` |
| **Image moments** | Weighted sums `Mpq = Σ xᵖyᵠ I(x,y)`; `M00` = area, first-order pair = centroid |
| **Hough Circle Transform** | Voting in `(cx, cy, r)` parameter space to find circles; `HOUGH_GRADIENT` votes along the gradient direction |
| **Canny thresholds** | The two hysteresis thresholds for edge detection; `param1` is the upper one |
| **Circular statistics** | Averaging angles as unit vectors so 0/360 wraps correctly |
| **SNR** | Signal-to-Noise Ratio; here `(mean_object − mean_background) / std_background` |
| **INTER_AREA / INTER_CUBIC** | Pixel-area resampling (correct downsample) / bicubic over 4×4 (smooth upsample) |
| **CACTus / SEEDS / ARTEMIS / CORIMP** | The four established automated CME detection systems; ours is SEEDS-family |

### Machine learning

| Term | Meaning |
|---|---|
| **Quantile regression** | Predicting a specified quantile of `p(y \| x)` rather than its mean |
| **Pinball / quantile / check loss** | `max(α(y−ŷ), (α−1)(y−ŷ))`; asymmetric, minimised at the true α-quantile |
| **Prediction interval** | `[q025, q975]`; a 95% interval on the outcome, not on a parameter |
| **Heteroscedasticity** | Conditional variance that depends on the inputs — why one global error bar is wrong here |
| **Quantile crossing** | `q025 > q500` from independently fitted models; fixed by a `sorted()` guard |
| **PICP** | Prediction Interval Coverage Probability — fraction of truths inside the interval |
| **PINAW** | Prediction Interval Normalised Average Width — the cost of that coverage |
| **Conformal prediction / CQR** | Distribution-free finite-sample coverage guarantee via calibration-set conformity scores (Romano et al. 2019) |
| **Mondrian conformal** | CQR calibrated *per stratum* (here per G-scale) so coverage holds where the risk is |
| **GBDT** | Gradient-Boosted Decision Trees; sequential additive trees each fitting the previous residual |
| **LightGBM** | The GBDT implementation the six shipped checkpoints are built with |
| **Monotone constraint** | Hard structural requirement that predictions move one way in a feature; enforced at split time |
| **Brier score** | Mean squared error of a probabilistic forecast; the right loss for the HF probability's *calibration* |
| **Reliability curve** | Predicted probability vs observed frequency; a calibrated model lies on the diagonal |
| **Optuna** | Hyperparameter optimisation framework |
| **TPE** | Tree-structured Parzen Estimator — models `p(params\|score)` as two densities and maximises `l(x)/g(x)` |
| **MedianPruner** | Kills trials whose intermediate score is below the running median |
| **Early stopping** | Halt boosting when validation loss stops improving; makes tree count data-driven |
| **GroupKFold** | CV that keeps a group entirely within one fold; insufficient for autocorrelated time series |
| **Purged split + embargo** | Time-blocked CV that also *deletes* rows within N hours of a fold boundary |
| **Data leakage** | Test information reaching the training set; inflates measured skill and never generalises |
| **Autocorrelation** | Correlation of a series with its own lag; sets how far apart folds must sit |
| **Spearman ρ** | Rank correlation; measures monotone association without assuming linearity |
| **Informative missingness** | Missingness that correlates with the target; here L1 drops out 3× more during storms |
| **Sample weighting** | Reweighting rare, important rows (storm hours are 5.1% of the record) |
| **Training/serving skew** | Features computed differently in training and production; silent and fatal |
| **SMOTE** | Synthetic minority oversampling; rejected here — it fabricates physics that never happened |
| **Stacking** | Ensembling via a meta-learner; rejected here for opacity |
| **Feature importance / ablation** | Which features earn their place; the plan reports 9 raw → +coupling → +integrated with a number |

---

## §11 — Hostile questions a judge might ask

### Q11.1 "Your CV is just a threshold. Where is the AI?"

The AI is where it earns its keep — the quantile ensemble that maps a storm state to an
impact distribution, a mapping that genuinely has no closed form. Detection *does* have a
closed form: a CME is a bright, contiguous, outward-moving region in a difference image,
and we can write that down in nine steps.

The unasked question is "why isn't there *more* AI", and the answer is that we deleted a
CNN we had already written, because it could only have been trained on labels we generated
ourselves from this very algorithm. That is distillation with extra steps: strictly worse
than the teacher, plus a GPU dependency, minus determinism. **Shipping less AI where the
physics is known is the engineering judgement, not an absence of one.** See §6.3 — deep
learning is a minority approach in the published CME-detection literature for exactly this
reason.

### Q11.2 "Your models are trained on synthetic data. Isn't the whole ML layer fake?"

The shipped checkpoints are trained on 4,800 synthetic rows and we say so in the docs, in
`AGENTS.md`, and here. What they demonstrate is real: the full architecture — quantile
objective, calibrated intervals, physical anchors, sub-50 ms CPU inference, the contract
the API depends on.

What they do *not* demonstrate is predictive skill on real storms, and we do not claim it.
A real-data track existed and was **deleted**, not shelved — it was permanently blocked on
labels, which no public dataset supplies in the required form (§8.2). Keeping an
untrainable pipeline in the tree would have made the repo look like it had two ML layers
when it has one.

The alternative — quietly training on real drivers with an invented target and calling it
"real data" — would be strictly less honest and no more skilful. So would shipping
scaffolding that never runs.

### Q11.3 "Two hardcoded features. Isn't that a bug?"

`geomag_lat_bin=1` and `local_time_bin=1` are pinned to mid-latitude/dayside in
`inference.py::_extract_features`. It is a known placeholder, not a hidden one.

The reason it exists: a `StormEvent` describes the *storm*, not the *observer*. Latitude
and local time are properties of whoever is asking. Filling them correctly requires the API
to take a location — a request-shape change, not a model change. The designed path replaces
both with `dregion_factor` (continuous physics rather than a day/night flag) and computes
the bin per-region in the label builder.

Its actual cost today: the prediction is a mid-latitude dayside estimate. For a high-
latitude polar route, mid-latitude *understates* the impact — which is the conservative
direction to be wrong in for a placeholder, but it is still a limitation and it is listed
as one.

### Q11.4 "What if the CV detector misses the CME entirely?"

It degrades rather than fails. `detect()` substitutes a stub bounding box with confidence
0.5, and the physics — speed, width, arrival — still comes from DONKI, which is the
authoritative source for those numbers anyway. The advisory is still produced; the *event
confidence* drops, because CV carries 40% of `fuse()`'s weight, and that lowered confidence
is surfaced to the operator.

Missing detection is therefore an honesty signal, not an outage. `TestDetectStubFallback`
pins this behaviour.

### Q11.5 "Your 95% intervals — are they actually 95%?"

Today: measured PICP 96.4% / 94.8% against a 95% target, on our own test set. That is an
empirical observation on one sample, and it is stated that way.

After conformal calibration it becomes a **guarantee** rather than an observation:
distribution-free, finite-sample, assuming only exchangeability. Stratified per G-scale,
because marginal coverage can hide catastrophic coverage at G5 — which is the one regime
anybody cares about. That is ~15 lines and two scalars, and it is in the plan (Q9.5).

### Q11.6 "Why should I trust a G5 prediction when you have almost no G5 data?"

**You should not trust a free model's G5 prediction, and that is exactly why the model is
not free.** Extreme storms are vanishingly rare in any real record — roughly 18 hours of
Kp = 9 in the last 30 years. In that regime every
statistical incentive points toward hedging to the training mean.

Three structural answers, none of which are "more data":

1. **Monotone constraints.** The tree is *structurally forbidden* from predicting less
   impact at higher Kp. Not penalised — forbidden at split time. This is a structural
   substitute for data that does not exist.
2. **A monotonicity audit in `finalize()`.** Kp is swept 0→9 on a real storm row and the
   output curve must be non-decreasing, or the training run fails. Constraints cannot be
   silently dropped.
3. **The anchor tests.** The 2024-05-G5 anchor asserts GPS error > 15 m and HF > 0.80. In
   the designed pipeline SC25 is the held-out cycle, so both anchors become genuine
   out-of-sample extreme-event tests rather than memorisation checks.

And the honest closer: no amount of technique manufactures G5 statistics.

### Q11.7 "What is your latency, and where does it go?"

Detection is ~15 ms per frame on CPU for the threshold algorithm; the sequence run scales
linearly with frame count. ML inference is six small tree ensembles, ~470 KB total — well
under the 50 ms CPU budget that shaped the model choice. No GPU is required at serve time,
anywhere in either layer. The dominant cost in the end-to-end pipeline is the LLM advisory
call in Layer ③, not CV or ML.

### Q11.8 "Halo CMEs are the dangerous ones, and you said your detector handles them badly."

Correct, and it is a property of coronagraphs, not of our algorithm. An Earth-directed CME
projects as a ring around the occulter: its circular-mean CPA becomes ill-defined and its
apparent width saturates near 360°. Every plane-of-sky detector has this problem — it is
why the field distinguishes "plane-of-sky speed" from "true speed" at all.

Three mitigations, all already in the code: (a) speed and width come from **DONKI's 3-D
cone fit**, not from our pixels; (b) `width_deg_visual` is deliberately named as the
*visual* quantity and never conflated with the cone width; (c) `is_halo` (`width ≥ 270°`)
is an explicit ML feature, so the model can learn a halo-specific response rather than
treating 300° as merely "a bit wider than 250°".

### Q11.9 "Why 2.5σ? Did you tune that, or guess?"

It is a detection-theory trade-off made deliberately toward sensitivity. At 2.5σ the
one-sided Gaussian false-positive rate is ~0.62%, which over the ~130k annulus pixels is
around 800 false pixels — knowingly more than a real CME's area. Steps 4 and 5 remove them,
because false positives are *spatially scattered* while a CME is *spatially contiguous*:
morphological opening kills isolated specks, and largest-connected-component selection
discards whatever survives.

Thresholding loosely and filtering geometrically is more robust than thresholding tightly
and missing faint fronts. And it is a named module-level constant next to
`ANNULAR_OUTER_PX` and `CONF_AREA_SCALE`, precisely because a different instrument needs
recalibration — real hardware always does.

### Q11.10 "Confidence is a hand-written weighted sum. Why not learn the weights?"

Because there is nothing to learn them from. Learning `0.4/0.2/0.2/0.2` requires a labelled
set of *storm-detection-correctness* judgements, which does not exist — the same labelling
problem as §6, one level up. Fitting them on two anchor storms would overfit to two events.

What the weights do encode is a defensible structural claim: **the visual detection is
necessary but not sufficient.** Capping CV at 0.40 means a confident detection of a
non-geoeffective, uncorroborated CME cannot exceed 0.5 confidence. That is the behaviour
we want, it is inspectable in six lines, and it is calibrated against NOAA post-event
reports rather than fitted. When real detection-correctness labels exist, it becomes a
fittable model — and until then, a transparent constant beats an unjustified fit.

### Q11.11 "How do you know your nine features actually help?"

Honestly: for the shipped model we know they *suffice*, not that each earns its place. The
targets are generated from a rule that uses `kp_index`, `bz_nt`, `cme_speed_km_s`,
`r_scale`, `geomag_lat_bin` and `local_time_bin`, so the model recovering them is
circular by construction — that is exactly what Q8.1 says the R2 measures.

What is measured and not circular: interval calibration (95.9% / 94.2% PICP against a
nominal 95%, Q9.6) and the physical ordering gate in `03_anchor_test.py`, which fails the
build if a G5 anchor does not exceed a quiet baseline on both targets. A feature-ablation
table would need real labels to mean anything, so it is not claimed.

### Q11.12 "What happens if the ML checkpoints are missing at runtime?"

`predict()` returns conservative fixed defaults — 20 m GPS error (CI 8–35) and 0.85 HF
blackout probability (CI 0.60–0.95) — and logs a warning. **Fail-safe, not fail-open:** the
fallback errs high, so a missing model produces an over-cautious advisory rather than a
falsely reassuring one or a 500. The same philosophy as the CV stub chain (Q5.3).

### Q11.13 "This is a hackathon project. How much of it is real?"

Concretely real: 2,183 lines of CV running on archived coronagraph frames, six trained
checkpoints with measured interval calibration, a 918-chunk RAG corpus built from actual
ICAO/NERC/ITU documents, 244 passing tests, and a working end-to-end API deployed as one
container.

Concretely *not* real, and labelled as such throughout: both ML targets are synthetic, so
the ML layer demonstrates architecture and calibration rather than forecast skill; and two
features (`geomag_lat_bin`, `local_time_bin`) are hardcoded placeholders.

We would rather hand you an accurate map of both lists than a demo that blurs them.

---

## §12 — Numbers worth memorising

| Quantity | Value |
|---|---|
| Detector steps | 9 |
| Threshold | μ + **2.5σ**, computed per frame inside the annular mask |
| Annulus | `occulter_r + 10 px` to **220 px** (≈6 R☉ at 512²) |
| Morphology | 3×3 ellipse, **open then close** |
| Frame size | **512×512**, letterbox-padded before resize |
| Percentile clip | **[0.5, 99.5]** |
| Sigma clip in the difference | **±3σ** |
| CLAHE | `clipLimit=2.0`, `tileGridSize=(8,8)` |
| Confidence | `min(1, area/300) × min(1, snr/3)` — multiplicative |
| Fusion weights | **0.4** CV / 0.2 flare / 0.2 southward Bz / 0.2 NOAA alert |
| DONKI measurement radius | **21.5 R☉** (WSA–ENLIL inner boundary) |
| L1 distance / ETA | 1.5 million km; **15–60 min** warning |
| Quantiles | **α = 0.025, 0.500, 0.975** |
| Shipped checkpoints | **6** LightGBM models, ~470 KB total |
| Shipped features | **9** (2 hardcoded) |
| Designed features | **38** |
| Training data (shipped) | 4,800 synthetic rows, 120 storms × 40 frames |
| Training data | **synthetic**, 4,800 rows = 120 storms x 40 frames, seed 42 |
| Interval calibration | PICP **95.9%** GPS / **94.2%** HF against nominal 95% |
| Kp = 9 hours in 30 years | **18** |
| Embargo | **120 h** (autocorrelation r < 0.1 only past 120 h) |
| Outer holdout | **SC25 (2020–2025)** — a whole solar cycle; both anchors are in it |
| Coupling gain | Newell/ε beat raw Bz by **+69% on Kp**, **+24% on AE** |
| Rolling-window gain | Dst ρ **0.382 → 0.691** (1 h → 24 h) |
| Measured PICP | 96.4% / 94.8% vs a 95% target |
| Anchor: 2024-05-G5 | GPS **22.0 m** (CI 13.3–25.9), HF **94.7%** — passes >15 m, >0.80 |
| Anchor: 2024-10-G4 | GPS **11.2 m** (CI 6.8–13.7), HF **93.2%** |
| GPU speedup, measured | 5.76 s CUDA vs 8.51 s CPU — **1.5×**, not 10× |
| CV determinism | Byte-identical output; no RNG, no weights |
| Tests | 154 passing |

---

## §13 — The three sentences to close on

1. **We detect with physics and predict with ML, and the boundary between them is the
   boundary between "the mapping is known" and "the mapping is not."** A CME is a bright
   contiguous moving arc — that we can write down. What a G5 does to a GPS receiver at
   70° latitude — that we have to learn.

2. **Every place we could have added a model and did not is a decision we can defend with
   a number**, and every place we did add one is constrained by physics that the algorithm
   is structurally forbidden from violating.

3. **We tell you which parts are real and which are scaffolded**, because a system whose
   entire value proposition is auditable advice cannot start by being unauditable about
   itself.
