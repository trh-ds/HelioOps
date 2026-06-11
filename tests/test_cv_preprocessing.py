"""
tests/test_cv_preprocessing.py — Commit 12 test suite

Proves the DoD: "Difference images show CME arc for Oct 2024 sequence"

Also verifies all three bug fixes applied in this commit:
    [FIX-A] Non-square FITS padded to square before resize — no oval distortion
    [FIX-B] Running-difference midpoint median-corrected — no brightness drift
    [FIX-C] All outputs are exactly 512×512 — no 532×532 shape mismatch

Run:
    pytest tests/test_cv_preprocessing.py -v
"""

import numpy as np
import pytest
import cv2
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cv.preprocessing import (
    load_ccor1_frame,
    running_difference,
    preprocess,
    find_occulter_center,
    preprocess_sequence,
    OUTPUT_SIZE,
    _pad_to_square,
    _find_corona_mask,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — synthetic FITS-like arrays that simulate real SOHO LASCO data
# ─────────────────────────────────────────────────────────────────────────────

def _make_corona(
    shape: tuple[int, int] = (1024, 1024),
    cosmic_ray: bool = True,
    cme_arc: bool = False,
    cme_angle_deg: float = 0.0,
) -> np.ndarray:
    """
    Generate a synthetic coronagraph image that reproduces the key properties
    of a real LASCO C2 FITS frame:
    - Background ~ 0  (space)
    - Corona rings ~ 100–600  (the solar corona streamers)
    - Occulting disk = 0  (the artificial eclipse blocker)
    - Cosmic ray spike ~ 60,000  (if cosmic_ray=True)
    - CME arc ~ 800  (if cme_arc=True, at specified angle)
    """
    h, w = shape
    data = np.zeros(shape, dtype=np.float32)
    y_grid, x_grid = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
    r2 = x_grid ** 2 + y_grid ** 2

    # Background corona rings (radial gradient + rings)
    for ring_r in [180, 260, 340, 420, 500]:
        ring = (r2 > (ring_r - 12) ** 2) & (r2 < (ring_r + 12) ** 2)
        data[ring] = 200 + ring_r * 0.2

    # Occulting disk — zero (blocks the Sun)
    data[r2 < 150 ** 2] = 0.0

    # Optional CME arc (bright material at specified angle)
    if cme_arc:
        theta = np.arctan2(y_grid, x_grid)
        target = np.deg2rad(cme_angle_deg)
        cme_mask = (
            (r2 > 300 ** 2) & (r2 < 450 ** 2)
            & (np.abs(theta - target) < np.deg2rad(25))
        )
        data[cme_mask] = 850.0

    # Cosmic ray spike (the bug trigger)
    if cosmic_ray:
        data[200, 300] = 60_000.0

    return data


def _mock_load_raw(path: str):
    """Return synthetic data in place of reading a real FITS file."""
    shape = (1024, 1024)
    if "768x1024" in str(path):
        shape = (768, 1024)  # non-square — triggers FIX-A
    data = _make_corona(shape=shape, cosmic_ray=True)
    meta = {
        "instrument": "LASCO", "detector": "C2",
        "date_obs": "2024-10-11", "exptime": 25.0,
        "raw_shape": shape, "filename": str(path),
    }
    return data, meta


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — load_ccor1_frame
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadCcor1Frame:
    """Tests for the fixed FITS loader — the black-image bug must be gone."""

    @patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw)
    def test_returns_float32(self, _mock):
        result = load_ccor1_frame("fake.fts")
        assert result.dtype == np.float32, "Must return float32"

    @patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw)
    def test_range_zero_to_one(self, _mock):
        result = load_ccor1_frame("fake.fts")
        assert result.min() >= 0.0, "Min must be >= 0"
        assert result.max() <= 1.0, "Max must be <= 1"

    @patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw)
    def test_not_black_image(self, _mock):
        """
        THE CORE BUG FIX: with a cosmic ray at 60,000 in a field of 200-600,
        the old min-max normalisation produced mean ≈ 0.003 (black).
        The new pipeline must produce mean > 0.1.
        """
        result = load_ccor1_frame("fake.fts")
        mean_val = float(result.mean())
        assert mean_val > 0.10, (
            f"Image is too dark (mean={mean_val:.4f}). "
            "Cosmic ray spike likely dominating normalisation — "
            "percentile clip not working."
        )

    @patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw)
    def test_cosmic_ray_removed(self, _mock):
        """
        The cosmic ray pixel (200, 300) must not dominate the output.
        After clipping to p99.5, the max output value should come from
        the corona, not the spike.
        """
        result = load_ccor1_frame("fake.fts")
        # If cosmic ray were preserved, nearly every pixel would be ~0
        # and one pixel would be 1.0.  Check the histogram is spread.
        hist, _ = np.histogram(result[result > 0], bins=10)
        # At least 5 of the 10 bins should have non-zero counts (spread distribution)
        non_empty_bins = int((hist > 0).sum())
        assert non_empty_bins >= 5, (
            f"Histogram too sparse ({non_empty_bins} bins) — "
            "cosmic ray spike may still be dominating the output range."
        )

    @patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw)
    def test_fix_a_non_square_padded(self, _mock):
        """
        FIX-A: Non-square FITS (768×1024) must be letterbox-padded to square
        before any downstream processing.  The output array must be square.
        """
        result = load_ccor1_frame("768x1024_frame.fts")
        assert result.shape[0] == result.shape[1], (
            f"Non-square FITS was not padded to square. "
            f"Got shape {result.shape} — expected (1024, 1024)."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — running_difference
# ─────────────────────────────────────────────────────────────────────────────

class TestRunningDifference:
    """Tests for the corrected running-difference computation."""

    def _make_frame_pair(self, with_cme: bool = True):
        """Return (prev_frame, curr_frame) where curr has a CME arc if requested."""
        with patch("cv.preprocessing._load_raw_fits", side_effect=_mock_load_raw):
            prev_data, _ = _mock_load_raw("frame_prev.fts")
            curr_data, _ = _mock_load_raw("frame_curr.fts")

        if with_cme:
            h, w = curr_data.shape
            y, x = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
            r2 = x ** 2 + y ** 2
            theta = np.arctan2(y, x)
            cme = (r2 > 300 ** 2) & (r2 < 450 ** 2) & (np.abs(theta) < np.deg2rad(25))
            curr_data[cme] = 850.0

        # Manually apply preprocessing (bypass file I/O)
        def _proc(d):
            d = np.nan_to_num(d, nan=0.0, posinf=0.0, neginf=0.0)
            nz = d[d > 0]
            d = np.clip(d, float(np.percentile(nz, 0.5)), float(np.percentile(nz, 99.5)))
            d = np.log1p(d - d.min())
            return ((d - d.min()) / (d.max() - d.min() + 1e-8)).astype(np.float32)

        return _proc(prev_data), _proc(curr_data)

    def test_returns_n_minus_one_frames(self):
        prev, curr = self._make_frame_pair()
        diffs = running_difference([prev, curr])
        assert len(diffs) == 1, "Two input frames must produce one diff frame"

    def test_output_in_zero_one_range(self):
        prev, curr = self._make_frame_pair()
        diff = running_difference([prev, curr])[0]
        assert diff.min() >= 0.0
        assert diff.max() <= 1.0

    def test_cme_region_brighter_than_background(self):
        """
        DoD PROOF: The CME arc region must be measurably brighter than the
        surrounding quiet corona in the running-difference image.
        """
        prev, curr = self._make_frame_pair(with_cme=True)
        diff = running_difference([prev, curr])[0]

        h, w = diff.shape
        y, x = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
        r2 = x ** 2 + y ** 2
        theta = np.arctan2(y, x)
        cme_mask = (r2 > 300 ** 2) & (r2 < 450 ** 2) & (np.abs(theta) < np.deg2rad(25))
        bg_mask  = (r2 > 300 ** 2) & (r2 < 450 ** 2) & (~cme_mask)

        cme_mean = float(diff[cme_mask].mean()) if cme_mask.any() else 0.0
        bg_mean  = float(diff[bg_mask].mean())  if bg_mask.any()  else 0.0

        assert cme_mean > bg_mean, (
            f"CME arc not visible in diff image! "
            f"CME region mean={cme_mean:.3f}, background mean={bg_mean:.3f}. "
            f"Running-difference is not revealing the CME arc."
        )

    def test_fix_b_midpoint_near_neutral(self):
        """
        FIX-B: The diff image midpoint must be close to 0.5 (neutral gray).
        Old version had +40/255 ≈ +0.16 bias on 22015098 due to frame brightness shift.
        """
        prev, curr = self._make_frame_pair(with_cme=False)
        # Introduce a systematic brightness increase (simulates LASCO auto-gain shift)
        curr_shifted = np.clip(curr + 0.1, 0.0, 1.0)
        diff = running_difference([prev, curr_shifted])[0]

        h, w = diff.shape
        y, x = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
        corona_region = (x ** 2 + y ** 2) > (min(h, w) * 0.15) ** 2
        corona_mean = float(diff[corona_region].mean()) if corona_region.any() else 0.5

        assert abs(corona_mean - 0.5) < 0.08, (
            f"Diff midpoint too far from neutral (0.5). "
            f"Corona mean = {corona_mean:.3f}. "
            f"Median correction may not be working (FIX-B)."
        )

    def test_requires_at_least_two_frames(self):
        prev, _ = self._make_frame_pair()
        with pytest.raises(ValueError):
            running_difference([prev])


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — preprocess
# ─────────────────────────────────────────────────────────────────────────────

class TestPreprocess:
    """Tests for the final denoise + resize step."""

    def _sample_diff(self) -> np.ndarray:
        """Return a synthetic float32 [0,1] diff frame."""
        img = np.random.default_rng(42).uniform(0.3, 0.7, (1024, 1024)).astype(np.float32)
        return img

    def test_returns_uint8(self):
        result = preprocess(self._sample_diff())
        assert result.dtype == np.uint8

    def test_fix_c_exact_output_size(self):
        """
        FIX-C: Output must be exactly OUTPUT_SIZE (512, 512).
        Previous outputs were 532×532 — breaks PyTorch batch collation.
        """
        result = preprocess(self._sample_diff(), target_size=OUTPUT_SIZE)
        expected_h, expected_w = OUTPUT_SIZE[1], OUTPUT_SIZE[0]
        assert result.shape == (expected_h, expected_w), (
            f"Output shape is {result.shape}, expected ({expected_h}, {expected_w}). "
            f"FIX-C (exact 512×512) not applied."
        )

    def test_output_uses_full_range(self):
        """After CLAHE, the output histogram should span a wide range."""
        result = preprocess(self._sample_diff(), enhance_contrast=True)
        assert int(result.max()) > 200, "Output too dim — CLAHE may not be working"
        assert int(result.min()) < 50,  "Output too bright — CLAHE may not be working"

    def test_works_with_uint8_input(self):
        """Must handle uint8 [0,255] input as well as float32 [0,1]."""
        uint8_input = (self._sample_diff() * 255).astype(np.uint8)
        result = preprocess(uint8_input)
        assert result.dtype == np.uint8
        assert result.shape == (OUTPUT_SIZE[1], OUTPUT_SIZE[0])


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — occulter center detection
# ─────────────────────────────────────────────────────────────────────────────

class TestFindOcculterCenter:

    def _make_occulter_image(self) -> np.ndarray:
        """512×512 uint8 image with a circular black disk at center."""
        img = np.full((512, 512), 150, dtype=np.uint8)
        cv2.circle(img, (256, 256), 80, 0, -1)  # black occulter
        img = cv2.GaussianBlur(img, (5, 5), 1)  # soften edges (realistic)
        return img

    def test_center_within_tolerance(self):
        img = self._make_occulter_image()
        cx, cy, r = find_occulter_center(img)
        dist = float(((cx - 256) ** 2 + (cy - 256) ** 2) ** 0.5)
        assert dist < 20, (
            f"Center detected at ({cx},{cy}), true center (256,256). "
            f"Error {dist:.1f}px exceeds 20px tolerance."
        )

    def test_radius_reasonable(self):
        img = self._make_occulter_image()
        _, _, r = find_occulter_center(img)
        assert 40 < r < 150, f"Detected radius {r}px seems unreasonable for this image"

    def test_never_raises_on_blank_image(self):
        """Must return a fallback, not crash, on a blank image."""
        blank = np.zeros((512, 512), dtype=np.uint8)
        result = find_occulter_center(blank)
        assert len(result) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 — integration test (full pipeline end-to-end)
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndPipeline:
    """
    Simulate what the Commit-13 CME CNN DataLoader will do:
    load a sequence → diff → preprocess → tensor shape check.
    """

    @patch("cv.preprocessing._load_raw_fits")
    def test_preprocess_sequence_shape(self, mock_load):
        """preprocess_sequence must return (N-1, 1, H, W) float32 tensor."""
        # Two frames: frame 0 = quiet corona, frame 1 = corona + CME arc
        def side_effect(path):
            shape = (1024, 1024)
            has_cme = "frame_1" in str(path)
            data = _make_corona(shape=shape, cosmic_ray=True, cme_arc=has_cme)
            meta = {"instrument": "CCOR-1", "detector": "C2",
                    "date_obs": "2024-10-11", "exptime": 900.0,
                    "raw_shape": shape, "filename": str(path)}
            return data, meta
        mock_load.side_effect = side_effect

        tensor = preprocess_sequence(["frame_0.fts", "frame_1.fts"])

        assert tensor.ndim == 4, f"Expected 4-D tensor (N,C,H,W), got {tensor.ndim}-D"
        assert tensor.shape[0] == 1,                "N-1 frames for 2 inputs = 1 diff"
        assert tensor.shape[1] == 1,                "Single channel (grayscale coronagraph)"
        assert tensor.shape[2] == OUTPUT_SIZE[1],   f"H must be {OUTPUT_SIZE[1]}"
        assert tensor.shape[3] == OUTPUT_SIZE[0],   f"W must be {OUTPUT_SIZE[0]}"
        assert tensor.dtype == np.float32,          "Must be float32 for CNN"
        assert tensor.max() <= 1.0,                 "Values must be in [0,1]"

    @patch("cv.preprocessing._load_raw_fits")
    def test_cme_visible_in_sequence_diff(self, mock_load):
        """
        End-to-end DoD test:
        The diff frame from a CME sequence must show the CME region brighter
        than the quiet-corona background.
        """
        def side_effect(path):
            shape = (1024, 1024)
            has_cme = "cme" in str(path)
            data = _make_corona(shape=shape, cosmic_ray=True,
                                cme_arc=has_cme, cme_angle_deg=45.0)
            meta = {"instrument": "LASCO", "detector": "C2",
                    "date_obs": "2024-10-11", "exptime": 25.0,
                    "raw_shape": shape, "filename": str(path)}
            return data, meta
        mock_load.side_effect = side_effect

        tensor = preprocess_sequence(["quiet_frame.fts", "cme_frame.fts"])
        diff = tensor[0, 0]  # (H, W) in [0,1]

        h, w = diff.shape
        y, x = np.ogrid[-h // 2: h // 2, -w // 2: w // 2]
        r2 = x ** 2 + y ** 2
        theta = np.arctan2(y.astype(float), x.astype(float))
        cme_angle_rad = np.deg2rad(45.0)
        cme_region = (
            (r2 > (h * 0.29) ** 2)
            & (r2 < (h * 0.44) ** 2)
            & (np.abs(theta - cme_angle_rad) < np.deg2rad(25))
        )
        bg_region = (
            (r2 > (h * 0.29) ** 2)
            & (r2 < (h * 0.44) ** 2)
            & (np.abs(theta - cme_angle_rad) > np.deg2rad(60))
        )

        if cme_region.any() and bg_region.any():
            cme_mean = float(diff[cme_region].mean())
            bg_mean  = float(diff[bg_region].mean())
            assert cme_mean > bg_mean, (
                f"CME arc NOT visible in end-to-end diff! "
                f"CME mean={cme_mean:.3f}, BG mean={bg_mean:.3f}. "
                f"DoD FAILED: difference images must show CME arc."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 — regression tests for all three bug fixes
# ─────────────────────────────────────────────────────────────────────────────

class TestBugFixes:
    """
    Explicit regression tests — one per bug fix from the Commit 12 audit.
    These tests exist so that no future refactor accidentally re-introduces
    a fixed bug.
    """

    def test_fix_a_768x1024_no_oval(self):
        """
        FIX-A: A 768×1024 FITS must be letterbox-padded before resize.
        Squashing directly to 512×512 previously gave 4.45× oval distortion.
        After fix: a circular occulter must still appear circular.
        """
        # Synthetic 768×1024 with a circular occulter
        data = np.zeros((768, 1024), dtype=np.float32)
        y, x = np.ogrid[-384:384, -512:512]
        # Circle of radius 150px centered on the image
        circle = x ** 2 + y ** 2 < 150 ** 2
        data[circle] = 0.0
        data[~circle] = 300.0

        padded = _pad_to_square(data)
        assert padded.shape[0] == padded.shape[1], (
            "Padded array must be square. FIX-A not applied."
        )

        # Resize the padded data and check the circle is still roughly circular
        resized = cv2.resize(padded, (512, 512), interpolation=cv2.INTER_AREA)
        # Measure circle extent horizontally vs vertically in the resized image
        mid_row = resized[256, :]   # horizontal slice
        mid_col = resized[:, 256]   # vertical slice
        dark_h = int((mid_row < 10).sum())
        dark_v = int((mid_col < 10).sum())
        # Ratio should be close to 1.0 for a circle (was 4.45× before fix)
        ratio = float(dark_v) / max(dark_h, 1)
        assert ratio < 1.5, (
            f"Occulter is still oval after padding: "
            f"vertical span={dark_v}px, horizontal span={dark_h}px, "
            f"ratio={ratio:.2f} (should be < 1.5). FIX-A incomplete."
        )

    def test_fix_b_median_correction_removes_drift(self):
        """
        FIX-B: A systematic +0.1 brightness increase between frames (like the
        LASCO auto-gain shift in 22015098) must not push the diff midpoint
        above 0.65.  Old code produced mean=0.66 (168/255); new code must
        produce mean in [0.42, 0.58].
        """
        rng = np.random.default_rng(0)
        quiet = rng.uniform(0.2, 0.5, (512, 512)).astype(np.float32)
        bright = np.clip(quiet + 0.15, 0.0, 1.0)  # simulate gain increase

        diffs = running_difference([quiet, bright], correct_median=True)
        diff = diffs[0]

        h, w = diff.shape
        y, x = np.ogrid[-h // 2:h // 2, -w // 2:w // 2]
        corona = (x ** 2 + y ** 2) > (min(h, w) * 0.15) ** 2
        mean_val = float(diff[corona].mean()) if corona.any() else 0.5

        assert 0.42 < mean_val < 0.58, (
            f"Diff midpoint drift not corrected: corona mean={mean_val:.3f}. "
            f"Expected in (0.42, 0.58). FIX-B incomplete."
        )

    def test_fix_c_output_exactly_512x512(self):
        """
        FIX-C: All outputs from preprocess() must be exactly 512×512.
        Previous outputs were 532×532 which breaks PyTorch batch collation.
        """
        for input_shape in [(1024, 1024), (532, 532), (768, 1024)]:
            img = np.random.default_rng(0).uniform(0.2, 0.8, input_shape).astype(np.float32)
            result = preprocess(img, target_size=OUTPUT_SIZE)
            assert result.shape == (512, 512), (
                f"Input shape {input_shape} → output {result.shape}. "
                f"Expected (512, 512). FIX-C incomplete."
            )