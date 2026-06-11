"""
cv/preprocessing.py — FITS preprocessing for HelioOps Layer ① (Commit 12)

Drop-in replacement for the three functions defined in imp.md §10 Layer ①:
    load_ccor1_frame()   ← fixed: log-scale + percentile clip (was: black-image bug)
    running_difference() ← fixed: median-corrected + sigma clip (was: raw subtraction)
    preprocess()         ← fixed: square-pad + CLAHE (was: clip-only, no pad)

Instruments supported: CCOR-1 (Oct 2024, primary), SOHO LASCO C2/C3 (May 2024 anchor)

Author : Neal
Commit : 12 — feat(cv): CCOR-1 pre-processing — FITS load + denoise + running-difference
DoD    : Difference images show CME arc for Oct 2024 sequence
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

# ── astropy is a hard dependency for FITS reading ────────────────────────────
try:
    from astropy.io import fits as _fits
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "astropy is required for FITS reading.  pip install astropy"
    ) from exc


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

OUTPUT_SIZE: tuple[int, int] = (512, 512)   # (width, height) — must match CNN input
CCOR1_CADENCE_SEC: float = 900.0            # 15-minute frame cadence
CCOR1_PLATE_SCALE: float = 0.0225          # degrees per pixel (approximate)
SOLAR_RADIUS_KM: float = 695_700.0


# ═════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _load_raw_fits(path: str) -> tuple[np.ndarray, dict]:
    """
    Load raw float32 data from a FITS file.

    Handles:
    - Multiple HDU extensions (searches for first 2-D image HDU)
    - BSCALE / BZERO physical scaling (common in LASCO integer files)
    - BLANK sentinel value (missing pixels in older SOHO data)

    Returns:
        data   : float32 array in physical units (counts or DN)
        header : dict of useful metadata keys
    """
    with _fits.open(path, memmap=False) as hdul:
        data, header = None, {}
        for i, hdu in enumerate(hdul):
            if hdu.data is not None and hdu.data.ndim == 2:
                data = hdu.data.astype(np.float32)
                header = dict(hdu.header)
                log.debug("HDU[%d] selected — shape %s", i, data.shape)
                break

    if data is None:
        raise ValueError(f"No 2-D image data found in {path}")

    # Physical scaling
    bscale = float(header.get("BSCALE", 1.0))
    bzero  = float(header.get("BZERO",  0.0))
    if bscale != 1.0 or bzero != 0.0:
        data = data * bscale + bzero

    # Zero-out BLANK (missing-data sentinel)
    blank = header.get("BLANK")
    if blank is not None:
        data[data == float(blank)] = 0.0

    return data, {
        "instrument": header.get("INSTRUME", "UNKNOWN"),
        "detector":   header.get("DETECTOR", "UNKNOWN"),
        "date_obs":   header.get("DATE-OBS", "UNKNOWN"),
        "exptime":    float(header.get("EXPTIME", 1.0)),
        "raw_shape":  data.shape,
        "filename":   Path(path).name,
    }


def _pad_to_square(data: np.ndarray) -> np.ndarray:
    """
    Letterbox-pad a non-square FITS array to square with zeros.

    WHY THIS IS CRITICAL:
        SOHO LASCO data from 1996-2003 sometimes stored as 768×1024.
        Squashing directly to 512×512 compresses the horizontal axis
        by 2× more than the vertical, turning the circular occulting
        disk into a tall oval.  Consequence: every CPA measurement
        derived from that image is geometrically wrong.

        Letterbox padding makes the resize uniform in both axes,
        preserving the circular occulter geometry.
    """
    h, w = data.shape
    if h == w:
        return data
    size = max(h, w)
    square = np.zeros((size, size), dtype=data.dtype)
    pad_h = (size - h) // 2
    pad_w = (size - w) // 2
    square[pad_h: pad_h + h, pad_w: pad_w + w] = data
    log.debug("Letterbox pad %s → (%d, %d)", data.shape, size, size)
    return square


def _find_corona_mask(image: np.ndarray) -> np.ndarray:
    """
    Return a boolean mask of the corona region, excluding:
    - The occulting disk (central black square or bright oval)
    - The image corners (octagonal mask edges, always zero)

    Used for computing statistics only on meaningful corona pixels.
    """
    h, w = image.shape
    mask = image > 0
    # Exclude ~15% radius from center (occulter region)
    y, x = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
    occulter = (x ** 2 + y ** 2) < (min(h, w) * 0.15) ** 2
    mask[occulter] = False
    return mask


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API — three functions that imp.md Layer ① calls directly
# ═════════════════════════════════════════════════════════════════════════════

def load_ccor1_frame(
    path: str,
    target_size: Optional[tuple[int, int]] = OUTPUT_SIZE,
) -> np.ndarray:
    """
    Load and normalise a single CCOR-1 or LASCO FITS frame.

    REPLACES the broken version in imp.md §10:
        OLD (black-image bug):
            data = (data - data.min()) / (data.max() - data.min() + 1e-8)
        NEW (correct):
            percentile clip [0.5, 99.5] → kills cosmic ray spikes
            log1p scale → stretches faint outer corona
            min-max normalise → full [0, 1] range used

    Why the old version produced black images:
        A single cosmic ray spike (value 65,000) in a field where the
        corona lives at 100–800 forces the entire corona into the bottom
        1.2% of the [0, 1] range after min-max normalisation → visually
        black.  Percentile clipping removes the spike before normalisation.

    Args:
        path        : path to a .fts / .fits file
        target_size : (width, height) to resize output — default OUTPUT_SIZE (512, 512).
                      Set None to return at original FITS resolution (for debugging only).
                      IMPORTANT: always use default in production. Mixed-shape sequences
                      crash running_difference() with broadcast errors.

    Returns:
        float32 ndarray, shape = target_size (H, W), values in [0, 1]
        Ready to feed into running_difference() or the CNN DataLoader.
    """
    raw, meta = _load_raw_fits(path)
    log.debug("Loaded %s  shape=%s  instrument=%s", meta["filename"],
              meta["raw_shape"], meta["instrument"])

    # Step 1 — NaN / Inf fix
    data = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)

    # Step 2 — letterbox pad for non-square FITS (e.g. 768×1024 LASCO)
    data = _pad_to_square(data)

    # Step 3 — percentile clip (kills cosmic rays without touching corona)
    nonzero = data[data > 0]
    if len(nonzero) == 0:
        log.warning("All-zero frame in %s — returning black", meta["filename"])
        if target_size:
            return np.zeros((target_size[1], target_size[0]), dtype=np.float32)
        return data.astype(np.float32)
    p_low  = float(np.percentile(nonzero, 0.5))
    p_high = float(np.percentile(nonzero, 99.5))
    data   = np.clip(data, p_low, p_high)

    # Step 4 — log1p scale  (power-law corona → linear perceptual contrast)
    data = np.log1p(data - data.min())

    # Step 5 — min-max normalise to [0, 1]
    d_min, d_max = data.min(), data.max()
    if d_max - d_min < 1e-8:
        log.warning("Near-constant frame after log-scale in %s", meta["filename"])
        if target_size:
            return np.zeros((target_size[1], target_size[0]), dtype=np.float32)
        return np.zeros_like(data, dtype=np.float32)
    data = ((data - d_min) / (d_max - d_min)).astype(np.float32)

    # Step 6 — resize to common output size (FIXES shape-mismatch crash in batch runs)
    # Root cause: LASCO archive mixes 512×512 and 1024×1024 frames in same sequence.
    # running_difference() subtracts frame[i] - frame[i-1]. Different shapes → broadcast error.
    # Resizing HERE guarantees all frames exit load_ccor1_frame() at identical shape.
    if target_size is not None:
        h, w = data.shape
        tw, th = target_size
        if (w, h) != (tw, th):
            interp = cv2.INTER_AREA if (tw < w or th < h) else cv2.INTER_CUBIC
            data = cv2.resize(data, target_size, interpolation=interp)

    return data


def running_difference(
    frames: list[np.ndarray],
    clip_sigma: float = 3.0,
    correct_median: bool = True,
) -> list[np.ndarray]:
    """
    Compute running-difference images from a sorted sequence of frames.

    WHY RUNNING DIFFERENCE:
        In a static corona image, bright streamers and the instrument
        background dominate.  Subtracting the previous frame cancels
        that static background — only MOVING material (the CME plasma
        front) remains visible as a bright expanding arc.

    REPLACES the broken version in imp.md §10:
        OLD:  frames[i] - frames[i-1]  (raw subtraction, no normalisation)
        NEW:
            1. Float subtraction (negative = material that left, positive = CME)
            2. Median correction — removes global brightness shifts between
               frames (LASCO auto-gain drift, large-scale CME brightening)
            3. Sigma clip — kills cosmic ray residuals in the diff
            4. Scale to [0, 1] centred at 0.5 (gray = no change,
               bright = new CME material, dark = vacated region)

    Args:
        frames         : list of float32 [0, 1] arrays from load_ccor1_frame()
                         Must be sorted chronologically.
        clip_sigma     : clip difference at ±N standard deviations (default 3.0)
        correct_median : subtract corona-region median to remove brightness shift
                         (set False only for debugging)

    Returns:
        list of N-1 float32 diff frames, shape same as input, values in [0, 1]
        First frame is dropped — no previous frame to subtract from.
    """
    if len(frames) < 2:
        raise ValueError("running_difference needs at least 2 frames")

    diffs = []
    for i in range(1, len(frames)):
        curr = frames[i].astype(np.float32)
        prev = frames[i - 1].astype(np.float32)

        # Ensure [0,1] range (handles uint8 inputs too)
        if curr.max() > 1.5:
            curr = curr / 255.0
        if prev.max() > 1.5:
            prev = prev / 255.0

        # Shape guard — safety net for mixed-resolution sequences.
        # Primary fix is in load_ccor1_frame() (target_size param).
        # This guard catches any caller that bypasses load_ccor1_frame().
        if prev.shape != curr.shape:
            log.warning(
                "Shape mismatch in running_difference: "
                "prev=%s curr=%s — resizing prev to match curr",
                prev.shape, curr.shape,
            )
            interp = cv2.INTER_AREA if prev.shape[0] > curr.shape[0] else cv2.INTER_CUBIC
            prev = cv2.resize(prev, (curr.shape[1], curr.shape[0]), interpolation=interp)

        diff = curr - prev  # range ~ [-1, 1]

        # Median correction — removes systematic brightness shift
        if correct_median:
            corona_mask = _find_corona_mask(curr)
            if corona_mask.any():
                diff -= float(np.median(diff[corona_mask]))

        # Sigma clip — removes cosmic ray residuals
        mu, sigma = diff.mean(), diff.std()
        diff = np.clip(diff, mu - clip_sigma * sigma, mu + clip_sigma * sigma)

        # Normalise to [0, 1] centred at 0.5
        abs_max = max(abs(diff.min()), abs(diff.max())) + 1e-8
        diff_norm = (diff / (2.0 * abs_max) + 0.5).astype(np.float32)
        diffs.append(diff_norm)

    return diffs


def preprocess(
    frame: np.ndarray,
    target_size: tuple[int, int] = OUTPUT_SIZE,
    enhance_contrast: bool = True,
) -> np.ndarray:
    """
    Denoise and resize a running-difference frame for CNN input or PNG export.

    REPLACES the broken version in imp.md §10:
        OLD:
            frame = np.clip(frame, 0, None)       # loses dark (vacated) signal
            frame = cv2.GaussianBlur(frame, (3,3), 0)
            return (frame / frame.max() * 255).astype(uint8)
        NEW:
            No clip to zero — dark regions are meaningful CME wakes
            CLAHE instead of Gaussian — reveals faint CME arcs at field edge
            Final resize locked to exactly (512, 512) — avoids shape mismatch
            in PyTorch DataLoader when batching across different source images

    Args:
        frame           : float32 [0, 1] diff frame from running_difference()
                          OR raw uint8 [0, 255] normalised frame
        target_size     : (width, height) output size — default OUTPUT_SIZE (512, 512)
        enhance_contrast: apply CLAHE for improved CME arc visibility (default True)

    Returns:
        uint8 ndarray, shape = (target_size[1], target_size[0]), values in [0, 255]
    """
    # Convert to uint8 if needed
    if frame.dtype != np.uint8:
        img = (np.clip(frame, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        img = frame.copy()

    # CLAHE — Contrast Limited Adaptive Histogram Equalisation
    # Splits image into tiles, equalises locally → faint outer CME arcs
    # become visible without over-brightening the already-bright inner region.
    if enhance_contrast:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe.apply(img)

    # Gaussian denoise — reduce LASCO/CCOR-1 sensor read noise
    img = cv2.GaussianBlur(img, (3, 3), 0)

    # Resize — INTER_AREA for downscaling (anti-aliased), INTER_CUBIC for up
    h, w = img.shape[:2]
    tw, th = target_size
    if (w, h) != (tw, th):
        interp = cv2.INTER_AREA if (tw < w or th < h) else cv2.INTER_CUBIC
        img = cv2.resize(img, target_size, interpolation=interp)

    return img


# ═════════════════════════════════════════════════════════════════════════════
# CONVENIENCE — sequence processing helpers used by the CNN DataLoader
# ═════════════════════════════════════════════════════════════════════════════

def preprocess_sequence(
    fits_paths: list[str],
    target_size: tuple[int, int] = OUTPUT_SIZE,
) -> np.ndarray:
    """
    Load → normalise → diff → preprocess a full FITS sequence in one call.

    Args:
        fits_paths  : list of paths sorted chronologically
        target_size : (width, height) for each output frame

    Returns:
        float32 tensor of shape (N-1, 1, H, W) — ready for PyTorch CNN/LSTM.
        Channel dim added at axis 1 for Conv2d compatibility.
    """
    frames = [load_ccor1_frame(p) for p in fits_paths]
    diffs  = running_difference(frames)
    out    = []
    for d in diffs:
        preprocessed = preprocess(d, target_size=target_size, enhance_contrast=True)
        out.append(preprocessed.astype(np.float32) / 255.0)  # back to [0,1] for training
    return np.stack(out, axis=0)[:, np.newaxis, :, :]  # (N-1, 1, H, W)


def find_occulter_center(image: np.ndarray) -> tuple[int, int, int]:
    """
    Detect the occulting disk center (cx, cy) and radius in pixels.

    WHY THIS MATTERS:
        CPA is measured counterclockwise from Solar North, relative to the
        solar center pixel.  A 5-pixel center error on a 512-px image
        introduces ~0.6° systematic CPA bias.  Accurate center detection
        is therefore a prerequisite for correct CPA regression.

    Strategy:
        Primary   : Hough circle transform — robust on LASCO C2 black disk
        Fallback  : Binary threshold + contour fitting — handles bright-center
                    (Type 2) images and cases where Hough fails on noisy frames

    Returns:
        (cx, cy, radius) in pixels.
        Falls back to (w//2, h//2, estimated_r) if detection fails — never raises.
    """
    h, w = image.shape[:2]
    fallback_r = min(h, w) // 8

    # Primary: Hough circles
    blurred = cv2.GaussianBlur(image, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=h // 4,
        param1=50,
        param2=30,
        minRadius=h // 12,
        maxRadius=h // 4,
    )
    if circles is not None:
        cx, cy, r = np.round(circles[0, 0]).astype(int)
        return int(cx), int(cy), int(r)

    # Fallback: threshold + contour
    center_crop = image[h // 2 - h // 8: h // 2 + h // 8,
                        w // 2 - w // 8: w // 2 + w // 8]
    is_bright_center = float(center_crop.mean()) > 128.0
    _, thresh = cv2.threshold(
        image,
        200 if is_bright_center else 30,
        255,
        cv2.THRESH_BINARY if is_bright_center else cv2.THRESH_BINARY_INV,
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_cnt, best_dist = None, float("inf")
    for cnt in contours:
        if cv2.contourArea(cnt) < 500:
            continue
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        cx_c = int(M["m10"] / M["m00"])
        cy_c = int(M["m01"] / M["m00"])
        dist = float(((cx_c - w // 2) ** 2 + (cy_c - h // 2) ** 2) ** 0.5)
        if dist < best_dist:
            best_dist, best_cnt = dist, (cx_c, cy_c, int((cv2.contourArea(cnt) / np.pi) ** 0.5))
    if best_cnt and best_dist < min(h, w) * 0.15:
        return best_cnt
    log.warning("Occulter detection failed — using image center as fallback")
    return w // 2, h // 2, fallback_r


def batch_preprocess_directory(
    input_dir: str,
    output_dir: str,
    target_size: tuple[int, int] = OUTPUT_SIZE,
    extensions: tuple[str, ...] = (".fts", ".fits", ".fit"),
) -> list[dict]:
    """
    Batch-convert all FITS files in a directory to normalised + diff PNGs.

    File naming convention (matches existing project outputs):
        {stem}_normalized.png  — log-scaled normalised frame
        {stem}_diff.png        — running-difference frame (vs previous)
        {stem}_meta.txt        — sidecar with instrument metadata

    Frames are processed in sorted filename order.
    Frame[0] produces only a normalised PNG (no previous frame for diff).
    Frame[i>0] produces both normalised and diff PNGs.

    Returns:
        list of result dicts — one per file — with keys:
        "file", "success", "normalized_path", "diff_path", "center_xy", "error"
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    fits_paths = sorted(
        str(p) for p in Path(input_dir).iterdir()
        if p.suffix.lower() in extensions
    )
    if not fits_paths:
        log.warning("No FITS files found in %s", input_dir)
        return []

    log.info("Batch: %d files in %s", len(fits_paths), input_dir)
    results = []
    prev_frame: Optional[np.ndarray] = None

    for fpath in fits_paths:
        stem = Path(fpath).stem
        r: dict = {"file": fpath, "success": False,
                   "normalized_path": None, "diff_path": None,
                   "center_xy": None, "error": None}
        try:
            curr_frame = load_ccor1_frame(fpath)

            # Normalised PNG
            norm_img = preprocess(curr_frame, target_size=target_size,
                                   enhance_contrast=False)
            norm_path = str(Path(output_dir) / f"{stem}_normalized.png")
            cv2.imwrite(norm_path, norm_img)
            r["normalized_path"] = norm_path

            # Occulter center
            cx, cy, _ = find_occulter_center(norm_img)
            r["center_xy"] = (cx, cy)

            # Diff PNG
            if prev_frame is not None:
                diffs = running_difference([prev_frame, curr_frame])
                diff_img = preprocess(diffs[0], target_size=target_size,
                                       enhance_contrast=True)
                diff_path = str(Path(output_dir) / f"{stem}_diff.png")
                cv2.imwrite(diff_path, diff_img)
                r["diff_path"] = diff_path

            # Metadata sidecar
            raw, meta = _load_raw_fits(fpath)
            meta_path = str(Path(output_dir) / f"{stem}_meta.txt")
            with open(meta_path, "w") as f:
                for k, v in meta.items():
                    f.write(f"{k}: {v}\n")
                f.write(f"output_size: {target_size}\n")
                f.write(f"log_scale: True\n")
                f.write(f"clip_pct: [0.5, 99.5]\n")
                f.write(f"center_xy: {r['center_xy']}\n")

            prev_frame = curr_frame
            r["success"] = True
            log.info("  ✅ %s", stem)

        except Exception as exc:
            log.error("  ❌ %s — %s", stem, exc)
            r["error"] = str(exc)
            results.append(r)
            continue

        results.append(r)

    ok = sum(1 for r in results if r["success"])
    log.info("Batch done: %d/%d succeeded", ok, len(results))
    return results