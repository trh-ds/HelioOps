"""
cv/cache_fits.py — FITS data acquisition for Option C demo storms

Two download paths:
  CCOR-1 Oct 2024 → AWS S3 public bucket (no auth)
  LASCO  May 2024 → SOHO archive via sunpy Fido (VSO)

Usage:
  python -m cv.cache_fits --storm 2024-10-G4
  python -m cv.cache_fits --storm 2024-05-G5
  python -m cv.cache_fits --list-bucket        # verify CCOR-1 S3 structure
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── CCOR-1 S3 ────────────────────────────────────────────────────────────────
CCOR1_BUCKET = "s3://noaa-nesdis-swfo-ccor-1-pds"

# Only frames in the CME onset window — reduces download from ~1 GB to ~400 MB
CCOR1_DAYS = {
    "2024-10-G4": [("2024", "10", "10"), ("2024", "10", "11")],
    "2024-05-G5": [],  # CCOR-1 not primary for May 2024 — use LASCO
}

# ── LASCO Fido ───────────────────────────────────────────────────────────────
LASCO_WINDOWS = {
    "2024-05-G5": ("2024-05-10T06:00", "2024-05-10T18:00"),
    "2024-10-G4": None,  # CCOR-1 is primary for Oct 2024
}

OUTPUT_ROOTS = {
    "2024-10-G4": "data/cached/ccor1/2024-10",
    "2024-05-G5": "data/cached/lasco/2024-05",
}


def sync_ccor1(year: str, month: str, day: str, output_dir: str) -> list[str]:
    """
    Download one day of CCOR-1 FITS from the public S3 bucket.

    Runs `aws s3 sync` as a subprocess — AWS CLI must be installed.
    Returns sorted list of .fits paths written to output_dir/raw/.
    """
    raw_dir = Path(output_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    s3_prefix = f"{CCOR1_BUCKET}/{year}/{month}/{day}/"
    cmd = [
        "aws", "s3", "sync", s3_prefix, str(raw_dir),
        "--no-sign-request",
        "--exclude", "*",
        "--include", "*.fits",
        "--include", "*.fts",
        "--include", "*.fit",
    ]

    log.info("Syncing CCOR-1 %s/%s/%s → %s", year, month, day, raw_dir)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("aws s3 sync failed:\n%s", result.stderr)
        raise RuntimeError(f"S3 sync failed for {s3_prefix}: {result.stderr[:500]}")

    paths = sorted(
        str(p) for p in raw_dir.iterdir()
        if p.suffix.lower() in (".fits", ".fts", ".fit")
    )
    log.info("CCOR-1 sync complete — %d files", len(paths))
    return paths


def fetch_lasco(start: str, end: str, output_dir: str) -> list[str]:
    """
    Download SOHO LASCO C2 frames via sunpy Fido (VSO).

    start/end : ISO strings e.g. "2024-05-10T06:00"
    Returns sorted list of .fits paths written to output_dir/raw/.
    """
    try:
        from sunpy.net import Fido
        import sunpy.net.attrs as a
    except ImportError as exc:
        raise ImportError(
            "sunpy is required for LASCO download.  pip install sunpy"
        ) from exc

    raw_dir = Path(output_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    log.info("Querying LASCO C2 %s → %s", start, end)
    result = Fido.search(
        a.Time(start, end),
        a.Instrument("LASCO"),
        a.Detector("C2"),
    )

    if len(result) == 0:
        raise ValueError(f"No LASCO C2 frames found for {start} → {end}")

    log.info("Found %d files — fetching to %s", len(result), raw_dir)
    downloaded = Fido.fetch(result, path=str(raw_dir / "{file}"))

    paths = sorted(
        str(p) for p in raw_dir.iterdir()
        if p.suffix.lower() in (".fits", ".fts", ".fit")
    )
    log.info("LASCO fetch complete — %d files", len(paths))
    return paths


def list_fits_sequence(raw_dir: str) -> list[str]:
    """Return FITS paths in raw_dir sorted chronologically by filename."""
    d = Path(raw_dir)
    if not d.exists():
        return []
    return sorted(
        str(p) for p in d.iterdir()
        if p.suffix.lower() in (".fits", ".fts", ".fit")
    )


def list_s3_bucket(prefix: str = "") -> None:
    """Print the top-level CCOR-1 S3 structure — use to verify bucket layout."""
    path = f"{CCOR1_BUCKET}/{prefix}" if prefix else CCOR1_BUCKET
    cmd = ["aws", "s3", "ls", path, "--no-sign-request"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
    else:
        print(result.stdout)


def fetch_storm(storm_id: str, base_dir: str = ".") -> list[str]:
    """
    Download all raw FITS for a storm.

    Returns sorted list of downloaded FITS paths.
    Raises ValueError for unknown storm_id.
    """
    if storm_id not in OUTPUT_ROOTS:
        raise ValueError(f"Unknown storm_id '{storm_id}'. Known: {list(OUTPUT_ROOTS)}")

    output_dir = str(Path(base_dir) / OUTPUT_ROOTS[storm_id])
    paths: list[str] = []

    # CCOR-1 days
    for (year, month, day) in CCOR1_DAYS.get(storm_id, []):
        paths.extend(sync_ccor1(year, month, day, output_dir))

    # LASCO window
    lasco_window = LASCO_WINDOWS.get(storm_id)
    if lasco_window:
        paths.extend(fetch_lasco(lasco_window[0], lasco_window[1], output_dir))

    if not paths:
        log.warning("No FITS downloaded for %s — check CCOR1_DAYS / LASCO_WINDOWS config", storm_id)

    return sorted(set(paths))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    p = argparse.ArgumentParser(description="HelioOps FITS cache downloader")
    p.add_argument("--storm", choices=list(OUTPUT_ROOTS), help="Storm ID to download")
    p.add_argument("--list-bucket", action="store_true", help="List CCOR-1 S3 top level")
    p.add_argument("--prefix", default="", help="S3 prefix for --list-bucket")
    p.add_argument("--base-dir", default=".", help="Repo root (default: cwd)")
    args = p.parse_args()

    if args.list_bucket:
        list_s3_bucket(args.prefix)
        return

    if not args.storm:
        p.error("--storm is required unless using --list-bucket")

    paths = fetch_storm(args.storm, base_dir=args.base_dir)
    print(f"\nDownloaded {len(paths)} files for {args.storm}")
    for path in paths[:5]:
        print(f"  {path}")
    if len(paths) > 5:
        print(f"  ... and {len(paths) - 5} more")


if __name__ == "__main__":
    main()
