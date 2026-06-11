"""
cv/fits_to_image.py — CLI wrapper around cv.preprocessing

Usage:
    # Single file — normal + diff
    python -m cv.fits_to_image --input frame_n.fts --prev frame_n_minus_1.fts --output data/processed/

    # Single file — normalised only
    python -m cv.fits_to_image --input frame.fts --output data/processed/ --mode normal

    # Batch — entire directory (pairs frames automatically)
    python -m cv.fits_to_image --input data/cached/ccor1/2024-10/ --output data/processed/ --batch

    # Inspect FITS headers without writing output
    python -m cv.fits_to_image --input frame.fts --inspect

All three Commit-12 bug fixes are applied via cv.preprocessing:
    Fix A — non-square FITS letterbox-padded before resize  (22010014: 768×1024 → oval was 4.45× distorted)
    Fix B — diff median-corrected per corona region          (22015098: midpoint +40 above neutral gray)
    Fix C — output locked to exactly (512,512)               (all images were 532×532)
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from cv.preprocessing import (
    _load_raw_fits,
    load_ccor1_frame,
    running_difference,
    preprocess,
    find_occulter_center,
    batch_preprocess_directory,
    OUTPUT_SIZE,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def convert_single(
    input_path: str,
    output_dir: str,
    mode: str = "both",
    prev_path: Optional[str] = None,
    target_size: tuple[int, int] = OUTPUT_SIZE,
) -> dict:
    """
    Convert one FITS file to normalised and/or diff PNG.

    Args:
        input_path  : path to current FITS frame
        output_dir  : directory to write output files
        mode        : "normal" | "diff" | "both"
        prev_path   : path to previous frame (required for mode "diff" or "both")
        target_size : (width, height) — default 512×512

    Returns:
        dict with keys: normal_path, diff_path, center_xy, radius
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    stem = Path(input_path).stem
    result: dict = {"normal_path": None, "diff_path": None,
                    "center_xy": None, "radius": None}

    curr = load_ccor1_frame(input_path)

    # ── Normalised PNG ────────────────────────────────────────────────────
    if mode in ("normal", "both"):
        norm_img = preprocess(curr, target_size=target_size, enhance_contrast=False)
        out = str(Path(output_dir) / f"{stem}_normalized.png")
        cv2.imwrite(out, norm_img)
        result["normal_path"] = out
        cx, cy, r = find_occulter_center(norm_img)
        result["center_xy"] = (cx, cy)
        result["radius"]    = r
        log.info("Saved normalised: %s  |  center=(%d,%d) r=%dpx", out, cx, cy, r)

    # ── Running-difference PNG ────────────────────────────────────────────
    if mode in ("diff", "both"):
        if prev_path is None:
            log.warning("--prev not supplied — skipping diff output")
        else:
            prev = load_ccor1_frame(prev_path)
            diffs = running_difference([prev, curr])
            diff_img = preprocess(diffs[0], target_size=target_size, enhance_contrast=True)
            out = str(Path(output_dir) / f"{stem}_diff.png")
            cv2.imwrite(out, diff_img)
            result["diff_path"] = out
            log.info("Saved diff:       %s", out)

    # ── Metadata sidecar ─────────────────────────────────────────────────
    _, meta = _load_raw_fits(input_path)
    meta_path = str(Path(output_dir) / f"{stem}_meta.txt")
    with open(meta_path, "w") as f:
        f.write(f"source_file:  {input_path}\n")
        f.write(f"instrument:   {meta['instrument']}\n")
        f.write(f"detector:     {meta['detector']}\n")
        f.write(f"date_obs:     {meta['date_obs']}\n")
        f.write(f"exptime:      {meta['exptime']}\n")
        f.write(f"raw_shape:    {meta['raw_shape']}\n")
        f.write(f"output_size:  {target_size}\n")
        f.write(f"log_scale:    True\n")
        f.write(f"clip_pct:     [0.5, 99.5]\n")
        if result["center_xy"]:
            f.write(f"center_xy:    {result['center_xy']}\n")
            f.write(f"occulter_r:   {result['radius']}px\n")

    return result


def inspect_fits(path: str) -> None:
    """Print header and data statistics without writing any output."""
    from astropy.io import fits as _fits

    with _fits.open(path) as hdul:
        print(f"\n{'=' * 60}")
        print(f"File  : {path}")
        print(f"HDUs  : {len(hdul)}")
        print(f"{'=' * 60}")
        for i, hdu in enumerate(hdul):
            print(f"\n── HDU [{i}]: {hdu.name}")
            if hdu.data is not None:
                d = hdu.data.astype(np.float32)
                d_ok = d[np.isfinite(d)]
                print(f"  Shape  : {hdu.data.shape}")
                print(f"  Dtype  : {hdu.data.dtype}")
                if len(d_ok):
                    print(f"  Min    : {d_ok.min():.2f}")
                    print(f"  Max    : {d_ok.max():.2f}")
                    print(f"  Mean   : {d_ok.mean():.2f}")
                    print(f"  Std    : {d_ok.std():.2f}")
                    print(f"  p0.5   : {np.percentile(d_ok, 0.5):.2f}")
                    print(f"  p99.5  : {np.percentile(d_ok, 99.5):.2f}")
                    print(f"  NaN px : {np.isnan(d).sum()}")
                    print(f"  Zero px: {(d == 0).sum()}")
            for k in ["INSTRUME", "DETECTOR", "DATE-OBS", "EXPTIME", "BSCALE", "BZERO"]:
                if k in hdu.header:
                    print(f"  {k:<12} = {hdu.header[k]}")


def _parse_size(s: str) -> tuple[int, int]:
    if "x" in s.lower():
        w, h = s.lower().split("x")
        return int(w), int(h)
    n = int(s)
    return n, n


def main() -> None:
    p = argparse.ArgumentParser(
        description="FITS → PNG converter (HelioOps Commit 12)"
    )
    p.add_argument("--input",   required=True, help=".fts file or directory (with --batch)")
    p.add_argument("--output",  default="data/processed/")
    p.add_argument("--prev",    default=None,  help="Previous frame for running-difference")
    p.add_argument("--mode",    default="both", choices=["normal", "diff", "both"])
    p.add_argument("--size",    default="512",  help="Output size: 512 or 1024x1024")
    p.add_argument("--batch",   action="store_true")
    p.add_argument("--inspect", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    target_size = _parse_size(args.size)

    if args.inspect:
        inspect_fits(args.input)
        return

    if args.batch:
        batch_preprocess_directory(
            input_dir=args.input,
            output_dir=args.output,
            target_size=target_size,
        )
    else:
        r = convert_single(
            input_path=args.input,
            output_dir=args.output,
            mode=args.mode,
            prev_path=args.prev,
            target_size=target_size,
        )
        print("\nDone.")
        if r["normal_path"]:
            print(f"  Normalised : {r['normal_path']}")
        if r["diff_path"]:
            print(f"  Diff       : {r['diff_path']}")
        if r["center_xy"]:
            print(f"  Center     : {r['center_xy']}, r={r['radius']}px")


if __name__ == "__main__":
    main()