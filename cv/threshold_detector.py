"""
cv/threshold_detector.py — Deterministic threshold-based CME detector (Option C)

Replaces the CNN inference path from cv/cmecnn.py with a 9-step algorithm that
requires zero trained weights and zero labeled data:

  1. Annular mask (exclude occulter + far field)
  2. Per-frame μ/σ in the masked region
  3. Bright pixel threshold at μ + 2.5σ
  4. Morphological open+close cleanup
  5. Connected components — take largest
  6. Bounding box (Cartesian, normalized)
  7. CPA + angular width (polar geometry)
  8. Confidence = f(area, SNR)
  9. Annotate frame + save PNG

Determinism guarantee: no RNG anywhere.  Same diff_frame → identical dict + PNG
bytes every run.  Satisfies the commit-23 byte-identical DoD.

Imports from existing codebase:
  cv.preprocessing    — load_ccor1_frame, running_difference, preprocess,
                        find_occulter_center  (commit 12, unchanged)
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

# ── Tunable constants ─────────────────────────────────────────────────────────
ANNULAR_INNER_PAD = 10    # pixels beyond occulter edge to exclude
ANNULAR_OUTER_PX  = 220   # outer corona limit at 512px (≈6 R☉ for LASCO C2)
SIGMA_THRESHOLD   = 2.5   # bright_mask = diff > μ + N×σ
MIN_BRIGHT_PX     = 40    # below this: no detection
MIN_COMPONENT_PX  = 30    # connected-component area filter
BBOX_PAD_PX       = 20    # padding added to each side of the bounding box
CONF_AREA_SCALE   = 300.0 # area that gives conf_area = 1.0
CONF_SNR_SCALE    = 3.0   # SNR that gives conf_snr = 1.0

# LASCO and CCOR-1 differ slightly; these instrument defaults are overridden
# at runtime when find_occulter_center() returns real values.
DEFAULT_OCCULTER_R = 80   # pixels, 512px image
DEFAULT_CENTER_XY  = (256, 256)


# ═════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═════════════════════════════════════════════════════════════════════════════

def _annular_mask(shape: tuple[int, int], cx: int, cy: int,
                  inner_r: int, outer_r: int) -> np.ndarray:
    """Boolean mask: True for pixels in the annular corona region."""
    h, w = shape
    y_idx, x_idx = np.ogrid[:h, :w]
    dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
    return (dist > inner_r) & (dist < outer_r)


def _circular_mean_deg(angles_deg: np.ndarray) -> float:
    """Circular mean of angles (handles 0/360 boundary correctly)."""
    rad = np.radians(angles_deg)
    return float(math.degrees(math.atan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)


def _circular_range_deg(angles_deg: np.ndarray) -> float:
    """Angular span of a set of angles — wraps correctly at 0/360."""
    if len(angles_deg) < 2:
        return 0.0
    rad = np.radians(angles_deg)
    # Use circular std as proxy for width; full circular range is ill-defined
    # for arcs > 180° so we cap at 360.
    c_mean_rad = math.atan2(np.sin(rad).mean(), np.cos(rad).mean())
    diffs = np.abs(np.angle(np.exp(1j * (rad - c_mean_rad))))  # in [-π, π]
    return float(min(2.0 * np.max(diffs) * (180.0 / math.pi), 360.0))


# ═════════════════════════════════════════════════════════════════════════════
# Core detection function
# ═════════════════════════════════════════════════════════════════════════════

def detect_cme_in_frame(
    diff_frame: np.ndarray,
    frame_norm: np.ndarray,
    occulter_r: int = DEFAULT_OCCULTER_R,
    center_xy: tuple[int, int] = DEFAULT_CENTER_XY,
) -> dict:
    """
    Run the 9-step threshold algorithm on a single running-difference frame.

    Args:
        diff_frame  : float32 [0,1] running-difference, neutral=0.5
                      Output of cv.preprocessing.running_difference()[i]
        frame_norm  : float32 [0,1] corresponding normalised frame
                      Output of cv.preprocessing.load_ccor1_frame()
        occulter_r  : occulter disk radius in pixels (from find_occulter_center)
        center_xy   : (cx, cy) disk center in pixels

    Returns dict with keys:
        detected        : bool
        bbox_px         : [x1, y1, x2, y2] padded, clipped to image
        bbox_norm       : [x1/W, y1/H, x2/W, y2/H] in [0,1]
        cpa_deg         : float — Central Position Angle, N=0 CCW
        width_deg_visual: float — angular width of the detected arc
        confidence      : float in [0,1]
        centroid_px     : (cx, cy) of the CME component
        snr             : float (for diagnostics)
        n_bright_px     : int (for diagnostics)
    """
    cx, cy = center_xy
    h, w = diff_frame.shape[:2]

    # ── Step 1: Annular mask ──────────────────────────────────────────────────
    inner_r = occulter_r + ANNULAR_INNER_PAD
    mask = _annular_mask((h, w), cx, cy, inner_r, ANNULAR_OUTER_PX)

    # ── Step 2: Statistics in masked region ───────────────────────────────────
    masked_vals = diff_frame[mask].astype(np.float32)
    if len(masked_vals) == 0:
        return _no_detection()
    mu = float(masked_vals.mean())
    sigma = float(masked_vals.std())
    if sigma < 1e-6:
        return _no_detection()

    # ── Step 3: Threshold ─────────────────────────────────────────────────────
    threshold = mu + SIGMA_THRESHOLD * sigma
    bright_raw = (diff_frame > threshold) & mask

    if int(bright_raw.sum()) < MIN_BRIGHT_PX:
        log.debug("Threshold: %d bright px < %d minimum — no detection", bright_raw.sum(), MIN_BRIGHT_PX)
        return _no_detection()

    # ── Step 4: Morphological cleanup ─────────────────────────────────────────
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bright_u8 = bright_raw.astype(np.uint8)
    bright_u8 = cv2.morphologyEx(bright_u8, cv2.MORPH_OPEN,  kernel)
    bright_u8 = cv2.morphologyEx(bright_u8, cv2.MORPH_CLOSE, kernel)

    if int(bright_u8.sum()) < MIN_BRIGHT_PX:
        return _no_detection()

    # ── Step 5: Connected components ──────────────────────────────────────────
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bright_u8)

    best_label, best_area = 0, 0
    for label in range(1, n_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area > MIN_COMPONENT_PX and area > best_area:
            best_area = area
            best_label = label

    if best_label == 0:
        return _no_detection()

    component_mask = (labels == best_label).astype(np.uint8)
    component_centroid = (int(round(centroids[best_label][0])),
                          int(round(centroids[best_label][1])))

    # ── Step 6: Bounding box ──────────────────────────────────────────────────
    x, y, bw, bh, _ = stats[best_label]
    x1 = max(0, x - BBOX_PAD_PX)
    y1 = max(0, y - BBOX_PAD_PX)
    x2 = min(w, x + bw + BBOX_PAD_PX)
    y2 = min(h, y + bh + BBOX_PAD_PX)
    bbox_px   = [x1, y1, x2, y2]
    bbox_norm = [x1 / w, y1 / h, x2 / w, y2 / h]

    # ── Step 7: CPA and angular width ─────────────────────────────────────────
    ys_comp, xs_comp = np.where(component_mask > 0)
    # Image angle: atan2(-dy, dx) — y-axis flipped (image coords)
    image_angles_rad = np.arctan2(-(ys_comp - cy), xs_comp - cx)
    image_angles_deg = np.degrees(image_angles_rad) % 360.0
    # CPA measured from North (up), counterclockwise
    cpa_image = _circular_mean_deg(image_angles_deg)
    cpa_deg   = (90.0 - cpa_image) % 360.0
    width_deg = _circular_range_deg(image_angles_deg)

    # ── Step 8: Confidence ────────────────────────────────────────────────────
    background_vals = diff_frame[mask & (labels == 0)].astype(np.float32)
    mu_bg   = float(background_vals.mean()) if len(background_vals) > 0 else mu
    sigma_bg = float(background_vals.std())  if len(background_vals) > 0 else sigma
    mu_bright = float(diff_frame[component_mask > 0].mean())
    snr = (mu_bright - mu_bg) / (sigma_bg + 1e-8)

    conf_area = min(1.0, best_area / CONF_AREA_SCALE)
    conf_snr  = min(1.0, snr / CONF_SNR_SCALE)
    confidence = conf_area * conf_snr

    log.debug(
        "CME detected: area=%d  snr=%.2f  conf=%.3f  CPA=%.1f°  width=%.1f°",
        best_area, snr, confidence, cpa_deg, width_deg,
    )

    return {
        "detected":         True,
        "bbox_px":          bbox_px,
        "bbox_norm":        [round(v, 4) for v in bbox_norm],
        "cpa_deg":          round(cpa_deg, 1),
        "width_deg_visual": round(width_deg, 1),
        "confidence":       round(confidence, 4),
        "centroid_px":      component_centroid,
        "snr":              round(snr, 3),
        "n_bright_px":      best_area,
    }


def _no_detection() -> dict:
    return {
        "detected":         False,
        "bbox_px":          [],
        "bbox_norm":        [],
        "cpa_deg":          0.0,
        "width_deg_visual": 0.0,
        "confidence":       0.0,
        "centroid_px":      (0, 0),
        "snr":              0.0,
        "n_bright_px":      0,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Sequence processing
# ═════════════════════════════════════════════════════════════════════════════

def detect_cme_in_sequence(
    diff_frames: list[np.ndarray],
    norm_frames: list[np.ndarray],
    occulter_r: int = DEFAULT_OCCULTER_R,
    center_xy: tuple[int, int] = DEFAULT_CENTER_XY,
) -> dict:
    """
    Run detector on every frame in the sequence.

    norm_frames has N frames; diff_frames has N-1 (no diff for frame[0]).
    We align diff_frames[i] with norm_frames[i+1].

    Returns:
        {
          "frames": [per-frame det dicts],
          "best_frame_idx": int — index into norm_frames with highest confidence,
          "detected_count": int,
        }
    """
    if len(diff_frames) == 0:
        return {"frames": [], "best_frame_idx": 0, "detected_count": 0}

    results = []
    best_conf = -1.0
    best_idx  = 0

    for i, diff in enumerate(diff_frames):
        norm_idx = i + 1  # diff[i] = norm[i+1] - norm[i]
        norm = norm_frames[norm_idx] if norm_idx < len(norm_frames) else norm_frames[-1]
        det = detect_cme_in_frame(diff, norm, occulter_r, center_xy)
        det["frame_index"] = norm_idx
        results.append(det)

        if det["detected"] and det["confidence"] > best_conf:
            best_conf = det["confidence"]
            best_idx  = norm_idx

    detected_count = sum(1 for r in results if r["detected"])
    return {
        "frames":          results,
        "best_frame_idx":  best_idx,
        "detected_count":  detected_count,
    }


def estimate_speed_from_centroids(
    centroid_sequence: list[tuple[int, int]],
    cadence_sec: float = 900.0,
    pixel_scale_deg: float = 0.0225,
    solar_radius_km: float = 695_700.0,
) -> float:
    """
    Plane-of-sky speed from frame-to-frame centroid displacement.

    Used as fallback when DONKI is unavailable.
    pixel_scale_deg: degrees per pixel (CCOR-1 approximate).
    """
    if len(centroid_sequence) < 2:
        return 500.0
    displacements = [
        math.sqrt((centroid_sequence[i][0] - centroid_sequence[i - 1][0]) ** 2 +
                  (centroid_sequence[i][1] - centroid_sequence[i - 1][1]) ** 2)
        for i in range(1, len(centroid_sequence))
    ]
    avg_disp_px = float(np.mean(displacements))
    speed = avg_disp_px * pixel_scale_deg * (math.pi / 180.0) * solar_radius_km / cadence_sec
    return float(np.clip(speed, 50.0, 5000.0))


# ═════════════════════════════════════════════════════════════════════════════
# Annotation
# ═════════════════════════════════════════════════════════════════════════════

def annotate_and_save(
    frame_norm: np.ndarray,
    det_result: dict,
    kinematics: Optional[dict],
    output_path: str,
) -> str:
    """
    Draw bbox + CPA lines + text on the normalised frame and save as PNG.

    frame_norm  : float32 [0,1] or uint8 [0,255]
    det_result  : output of detect_cme_in_frame()
    kinematics  : {"speed_km_s": float, "angular_width_deg": float,
                   "arrival_estimate": str} — from DONKI; pass None to skip text
    output_path : absolute path for the annotated PNG

    Returns output_path.
    Deterministic: integer pixel coordinates only — cv2.putText is stable.
    """
    # Convert to uint8 BGR
    if frame_norm.dtype != np.uint8:
        img8 = (np.clip(frame_norm, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        img8 = frame_norm.copy()
    canvas = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)

    if not det_result.get("detected"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, canvas)
        return output_path

    h, w = canvas.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in det_result["bbox_px"])
    cx, cy = DEFAULT_CENTER_XY  # image center (occulter)
    if "centroid_px" in det_result:
        # Use frame center, not centroid, for radial lines
        pass

    cpa_deg   = det_result["cpa_deg"]
    width_deg = det_result["width_deg_visual"]

    # Green bounding box (2px)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Yellow radial lines from occulter center at CPA ± width/2
    ray_len = ANNULAR_OUTER_PX + 10
    for angle_offset in (-width_deg / 2, 0, width_deg / 2):
        # CPA is from North CCW; convert to image angle
        img_angle_deg = 90.0 - (cpa_deg + angle_offset)
        img_angle_rad = math.radians(img_angle_deg)
        ex = int(round(cx + ray_len * math.cos(img_angle_rad)))
        ey = int(round(cy - ray_len * math.sin(img_angle_rad)))
        color = (0, 255, 255) if angle_offset == 0 else (0, 200, 180)
        thickness = 2 if angle_offset == 0 else 1
        cv2.line(canvas, (cx, cy), (ex, ey), color, thickness)

    # Text overlay
    lines = [
        f"CPA: {cpa_deg:.0f} deg",
        f"Width (visual): {width_deg:.0f} deg",
        f"Conf: {det_result['confidence']:.2f}",
    ]
    if kinematics:
        speed = kinematics.get("speed_km_s")
        if speed is not None:
            lines.append(f"Speed: {speed:.0f} km/s")
        arrival = kinematics.get("arrival_estimate", "")
        if arrival:
            lines.append(f"ETA: {arrival[:16]}")

    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness  = 1
    pad        = 4
    for i, line in enumerate(lines):
        y_pos = 16 + i * 18
        # Shadow for readability
        cv2.putText(canvas, line, (pad + 1, y_pos + 1), font, font_scale, (0, 0, 0), thickness + 1)
        cv2.putText(canvas, line, (pad,     y_pos),     font, font_scale, (255, 255, 255), thickness)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, canvas)
    log.info("Annotated frame saved: %s", output_path)
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
# Convenience loader for cached PNG sequences
# ═════════════════════════════════════════════════════════════════════════════

def load_cached_sequence(png_dir: str) -> tuple[list[np.ndarray], list[np.ndarray], list[dict]]:
    """
    Load preprocessed norm + diff PNGs from a cached sequence directory.

    Expects files named {stem}_normalized.png and {stem}_diff.png (commit-12 convention).

    Returns:
        diff_frames : list of float32 [0,1] diff arrays
        norm_frames : list of float32 [0,1] norm arrays (one more than diff_frames)
        meta_list   : list of dicts with center_xy and occulter_r (from sidecar .txt)
    """
    norm_dir = Path(png_dir) / "png"
    diff_dir = Path(png_dir) / "diff"

    norm_paths = sorted(norm_dir.glob("*_normalized.png")) if norm_dir.exists() else []
    diff_paths = sorted(diff_dir.glob("*_diff.png"))       if diff_dir.exists() else []

    # Fallback: flat directory (older layout)
    if not norm_paths:
        norm_paths = sorted(Path(png_dir).glob("*_normalized.png"))
    if not diff_paths:
        diff_paths = sorted(Path(png_dir).glob("*_diff.png"))

    norm_frames = [
        cv2.imread(str(p), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        for p in norm_paths
    ]
    diff_frames = [
        cv2.imread(str(p), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        for p in diff_paths
    ]

    # Load sidecar metadata
    meta_list = []
    for np_ in norm_paths:
        meta_path = np_.with_name(np_.name.replace("_normalized.png", "_meta.txt"))
        meta = {"center_xy": DEFAULT_CENTER_XY, "occulter_r": DEFAULT_OCCULTER_R}
        if meta_path.exists():
            with open(meta_path) as f:
                for line in f:
                    if "center_xy:" in line:
                        val = line.split(":", 1)[1].strip().strip("()")
                        parts = val.split(",")
                        if len(parts) == 2:
                            meta["center_xy"] = (int(parts[0].strip()), int(parts[1].strip()))
                    elif "occulter_r:" in line:
                        val = line.split(":", 1)[1].strip().replace("px", "")
                        try:
                            meta["occulter_r"] = int(float(val))
                        except ValueError:
                            pass
        meta_list.append(meta)

    return diff_frames, norm_frames, meta_list
