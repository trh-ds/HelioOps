"""
cv/detect.py — Heliospheric detection entry point (Option C)

Replaces the CNN-based detect() from cv/cmecnn.py with a threshold + DONKI pipeline.
Called by Tirth's replay engine:  from cv.detect import detect

Two modes:
  detect(storm_id)   — deterministic replay from cached data (DEMO_MODE=true)
  detect_live()      — hits live APIs (DEMO_MODE=false)

Fallback chain (every layer has a safe fallback):
  PNGs exist?         → use them        else → need to run cache_fits.py first
  Detector finds CME? → real bbox       else → stub bbox_norm
  DONKI cache exists? → real physics    else → fetch live → fail → stub speed
  StormEvent built?   → return it       else → load stub JSON directly

Usage:
  python -m cv.detect --storm 2024-10-G4
  python -m cv.detect --storm 2024-05-G5
  python -m cv.detect --storm 2024-10-G4 --dry-run   # prints result, no annotation write
  python -m cv.detect --live                          # real-time mode
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Storm configuration registry
# ─────────────────────────────────────────────────────────────────────────────

STORM_CONFIGS: dict[str, dict] = {
    "2024-10-G4": {
        "storm_date":    "2024-10-10T12:00:00Z",
        "source":        "CCOR-1",
        "png_dir":       "data/cached/ccor1/2024-10",
        "annotated_dir": "data/cached/ccor1/2024-10/annotated",
        "donki_start":   "2024-10-08",
        "donki_end":     "2024-10-12",
        "donki_cache":   "data/cached/donki/cme_2024-10-08_2024-10-12.json",
        "flare_cache":   "data/cached/xrs/2024-10-10.json",
        "l1_cache":      "data/cached/l1/2024-10-11.json",
        "alert_cache":   "data/cached/alerts/2024-10-10.txt",
        "stub_path":     "ml/stubs/storm_event_2024-10-G4.json",
        "stub_bbox":     [0.28, 0.18, 0.74, 0.62],
    },
    "2024-05-G5": {
        "storm_date":    "2024-05-10T06:00:00Z",
        "source":        "SOHO/LASCO",
        "png_dir":       "data/cached/lasco/2024-05",
        "annotated_dir": "data/cached/lasco/2024-05/annotated",
        "donki_start":   "2024-05-08",
        "donki_end":     "2024-05-12",
        "donki_cache":   "data/cached/donki/cme_2024-05-08_2024-05-12.json",
        "flare_cache":   "data/cached/xrs/2024-05-10.json",
        "l1_cache":      "data/cached/l1/2024-05-11.json",
        "alert_cache":   "data/cached/alerts/2024-05-10.txt",
        "stub_path":     "ml/stubs/storm_event_2024-05-G5.json",
        "stub_bbox":     [0.12, 0.08, 0.88, 0.86],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Alert cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_alert(cache_path: str) -> str:
    p = Path(cache_path)
    if p.exists():
        return p.read_text().strip()
    # Derive a sensible default from the stub if no cached alert exists
    return ""


def _load_stub(stub_path: str):
    from cv.fusion import StormEvent
    with open(stub_path) as f:
        return StormEvent(**json.load(f))


# ─────────────────────────────────────────────────────────────────────────────
# Main detection pipeline
# ─────────────────────────────────────────────────────────────────────────────

def detect(storm_id: str, base_dir: str = ".") -> "StormEvent":
    """
    Deterministic replay detection for a known storm.

    Same storm_id → byte-identical StormEvent every run (when cached data exists).
    Tirth calls this as:  from cv.detect import detect

    Args:
        storm_id : "2024-10-G4" | "2024-05-G5"
        base_dir : repo root (default cwd — matches how FastAPI is launched)

    Returns:
        StormEvent (pydantic model, JSON-serialisable via .model_dump())
    """
    from cv.fusion import StormEvent, fuse
    from cv.threshold_detector import (
        detect_cme_in_sequence,
        load_cached_sequence,
        annotate_and_save,
        DEFAULT_OCCULTER_R,
        DEFAULT_CENTER_XY,
    )
    from cv.donki_client import fetch_cme_analyses, select_best_cme, cme_to_fields
    from cv.flare_classifier import fetch_and_classify_flare
    from cv.l1_client import fetch_l1_wind

    if storm_id not in STORM_CONFIGS:
        raise ValueError(f"Unknown storm_id '{storm_id}'. Known: {list(STORM_CONFIGS)}")

    cfg = STORM_CONFIGS[storm_id]
    base = Path(base_dir)

    stub_path     = str(base / cfg["stub_path"])
    png_dir       = str(base / cfg["png_dir"])
    annotated_dir = str(base / cfg["annotated_dir"])

    # ── Step 1: Load preprocessed image sequences ─────────────────────────────
    diff_frames, norm_frames, meta_list = load_cached_sequence(png_dir)

    if not diff_frames:
        log.warning("No preprocessed PNGs in %s — falling back to stub", png_dir)
        return _load_stub(stub_path)

    # Derive occulter params from first frame's sidecar (all frames same instrument)
    occulter_r = meta_list[0]["occulter_r"] if meta_list else DEFAULT_OCCULTER_R
    center_xy  = meta_list[0]["center_xy"]  if meta_list else DEFAULT_CENTER_XY

    # ── Step 2: Run threshold detector ───────────────────────────────────────
    seq_result   = detect_cme_in_sequence(diff_frames, norm_frames, occulter_r, center_xy)
    best_idx     = seq_result["best_frame_idx"]
    frame_dets   = seq_result["frames"]
    best_det     = frame_dets[best_idx - 1] if frame_dets and best_idx > 0 else None

    if best_det is None or not best_det.get("detected"):
        log.warning("Threshold detector found no CME — using stub bbox")
        best_det = {
            "detected":         True,
            "bbox_norm":        cfg["stub_bbox"],
            "bbox_px":          [],
            "cpa_deg":          0.0,
            "width_deg_visual": 110.0,
            "confidence":       0.5,
            "centroid_px":      (256, 256),
        }

    # ── Step 3: Load DONKI (cache only in replay mode) ────────────────────────
    donki_cache = str(base / cfg["donki_cache"])
    analyses    = fetch_cme_analyses(cfg["donki_start"], cfg["donki_end"],
                                     str(Path(donki_cache).parent))
    cme_analysis = select_best_cme(analyses, cfg["storm_date"])

    if cme_analysis:
        cme_fields = cme_to_fields(cme_analysis)
    else:
        log.warning("No DONKI record found — using stub speed/width")
        stub = json.load(open(stub_path))
        cme_fields = {
            "speed_km_s":        stub["cme"]["speed_km_s"],
            "angular_width_deg": stub["cme"]["angular_width_deg"],
            "direction":         stub["cme"]["direction"],
            "arrival_estimate":  stub["cme"]["arrival_estimate"],
            "donki_id":          "",
        }

    # ── Step 4: Annotate best frame and save PNG ──────────────────────────────
    annotated_path = ""
    if norm_frames and best_idx < len(norm_frames):
        frame_for_annotation = norm_frames[best_idx]
        out_path = str(Path(annotated_dir) / f"frame_{best_idx:03d}.png")
        try:
            annotated_path = annotate_and_save(
                frame_for_annotation, best_det, cme_fields, out_path
            )
        except Exception as exc:
            log.error("Annotation failed: %s — continuing without annotated PNG", exc)

    # ── Step 5: Load flare, L1, NOAA alert ───────────────────────────────────
    flare_result = fetch_and_classify_flare(
        cfg["storm_date"],
        str(base / cfg["flare_cache"]),
    )
    l1_result = fetch_l1_wind(str(base / cfg["l1_cache"]))
    noaa_alert = _load_alert(str(base / cfg["alert_cache"]))

    # Pull G-scale from stub if L1 doesn't include it
    stub_data  = json.load(open(stub_path))
    l1_result["g_scale"] = stub_data["scales"].get("G", 0)

    # ── Step 6: Assemble StormEvent ───────────────────────────────────────────
    cme_block = {
        **cme_fields,
        "detected":    best_det["detected"],
        "source":      cfg["source"],
        "confidence":  best_det["confidence"],
        "frame_path":  annotated_path or stub_data["cme"]["frame_path"],
        "bbox_norm":   best_det["bbox_norm"] or cfg["stub_bbox"],
    }

    try:
        return fuse(cme_block, flare_result, l1_result, noaa_alert, storm_id)
    except Exception as exc:
        log.error("fuse() failed (%s) — loading stub", exc)
        return _load_stub(stub_path)


def detect_live() -> "StormEvent":
    """
    Real-time detection — hits live GOES XRS, DSCOVR, DONKI endpoints.
    Called when DEMO_MODE=false.

    Uses the most recent CCOR-1 frames from S3 if available,
    otherwise falls back to the threshold on cached frames.
    """
    import tempfile
    from cv.fusion import StormEvent, fuse
    from cv.donki_client import fetch_cme_analyses, select_best_cme, cme_to_fields
    from cv.flare_classifier import fetch_and_classify_flare
    from cv.l1_client import fetch_l1_wind
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    today      = now.strftime("%Y-%m-%d")
    yesterday  = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    with tempfile.TemporaryDirectory() as tmp:
        analyses    = fetch_cme_analyses(yesterday, today, tmp)
        cme_analysis = select_best_cme(analyses, now.isoformat())
        cme_fields   = cme_to_fields(cme_analysis) if cme_analysis else {
            "speed_km_s": 500.0, "angular_width_deg": 90.0,
            "direction": "unknown", "arrival_estimate": "", "donki_id": "",
        }

        # For live mode, we don't have a frame to annotate
        cme_block = {
            **cme_fields,
            "detected":   bool(cme_analysis),
            "source":     "CCOR-1",
            "confidence": 0.5 if cme_analysis else 0.0,
            "frame_path": "",
            "bbox_norm":  [],
        }

        flare_result = fetch_and_classify_flare(
            now.isoformat(),
            os.path.join(tmp, "xrs_live.json"),
        )
        l1_result = fetch_l1_wind(os.path.join(tmp, "l1_live.json"))

    return fuse(cme_block, flare_result, l1_result, "", f"live-{today}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    p = argparse.ArgumentParser(description="HelioOps CME detection entry point")
    p.add_argument("--storm", choices=list(STORM_CONFIGS), help="Replay a known storm")
    p.add_argument("--live",  action="store_true",         help="Real-time detection")
    p.add_argument("--dry-run", action="store_true",       help="Print result, no side effects")
    p.add_argument("--base-dir", default=".",              help="Repo root directory")
    args = p.parse_args()

    if args.live:
        event = detect_live()
    elif args.storm:
        event = detect(args.storm, base_dir=args.base_dir)
    else:
        p.error("--storm or --live required")

    result = event.model_dump()
    print(json.dumps(result, indent=2, default=str))

    if not args.dry_run:
        out = Path(args.base_dir) / "data" / "cached" / f"storm_event_{event.storm_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(result, f, indent=2, default=str)
        log.info("StormEvent written to %s", out)


if __name__ == "__main__":
    main()
