"""
backend/preflight.py — read-only pre-run conflict check.

Predicts, without running the pipeline, which fallbacks a run will hit,
which cached data sources physically disagree, and whether the system or
Groq quota is degraded. Served by GET /api/preflight/{storm_id}.

Hard rule: this module never fetches, never writes, never mkdirs. Every
cache file is stat'ed before any parser touches it, because the ingestion
clients are cache-first-then-NETWORK and create directories on entry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.cv.storm_event_generator.detect import STORM_CONFIGS
from backend.health import _requester_metrics, health_collector
from backend.middleware import peek_rate_limit
from backend.paths import BACKEND_DIR

log = logging.getLogger(__name__)

DEFAULT_DURATION_S = 70
TPM_LOW_THRESHOLD = 4000  # ~one full advisory pass

_CHECK_CONSEQUENCE = {
    "detection": "Detection layer unavailable - the run will fail.",
    "ml_models": "ML checkpoints missing - impact prediction falls back to defaults.",
    "genai_module": "GenAI layer broken - advisory generation will fail.",
    "knowledge_base": "Knowledge base empty - advisories will be ungrounded (no citations).",
}


def _finding(fid: str, severity: str, title: str, detail: str) -> dict:
    return {"id": fid, "severity": severity, "title": title, "detail": detail}


# ── Cache existence + parsing ───────────────────────────────────────────────

def _cache_findings(cfg: dict, base: Path):
    """
    Returns (findings, stub, cme, flare, l1). stub is always the committed
    JSON dict; cme/flare/l1 are parsed run-identical values or None.
    Parsers are only invoked when their cache file already exists on disk.
    """
    findings: list[dict] = []
    stub = json.loads((base / cfg["stub_path"]).read_text())

    png_root = base / cfg["png_dir"]
    have_frames = any((png_root / "png").glob("*.png")) and any(
        (png_root / "diff").glob("*.png")
    )
    if not have_frames:
        findings.append(_finding(
            "cv_stub_replay", "warn",
            "Detection will replay the committed stub",
            f"No preprocessed frames under {cfg['png_dir']}/png + /diff. "
            "detect() returns the stub StormEvent wholesale - the DONKI, flare, "
            "L1 and alert caches below will not even be read. Run cache_fits + "
            "preprocessing to detect from real frames.",
        ))

    cme = flare = l1 = None

    donki_path = base / cfg["donki_cache"]
    if not donki_path.exists():
        findings.append(_finding(
            "donki_cache_missing", "info",
            "DONKI CME cache missing",
            "The run will attempt a live DONKI fetch; if that fails it uses "
            "the stub speed/width.",
        ))
    else:
        try:
            from backend.cv.data_ingestion.donki_client import (
                cme_to_fields, select_best_cme,
            )
            best = select_best_cme(json.loads(donki_path.read_text()), cfg["storm_date"])
            if best:
                cme = cme_to_fields(best)
            else:
                findings.append(_finding(
                    "donki_no_match", "info",
                    "DONKI cache holds no matching CME",
                    "No record within the storm window - the run uses the stub "
                    "speed/width.",
                ))
        except Exception as exc:
            findings.append(_finding(
                "donki_cache_missing", "info",
                "DONKI cache unreadable",
                f"Parse failed ({exc}) - the run will refetch or fall back to stub values.",
            ))

    flare_path = base / cfg["flare_cache"]
    if not flare_path.exists():
        findings.append(_finding(
            "flare_cache_missing", "info",
            "GOES XRS flare cache missing",
            "The run will attempt a live GOES fetch; if that fails the flare "
            "block reports no detection (R0).",
        ))
    else:
        try:
            from backend.cv.data_ingestion.flare_classifier import fetch_and_classify_flare
            flare = fetch_and_classify_flare(cfg["storm_date"], str(flare_path))
        except Exception as exc:
            findings.append(_finding(
                "flare_cache_missing", "info",
                "GOES XRS flare cache unreadable",
                f"Parse failed ({exc}) - the run will refetch or report no flare.",
            ))

    l1_path = base / cfg["l1_cache"]
    if not l1_path.exists():
        findings.append(_finding(
            "l1_cache_missing", "info",
            "DSCOVR L1 solar wind cache missing",
            "The run will attempt a live DSCOVR fetch; if that fails it uses "
            "fallback defaults (400 km/s, Bz 0).",
        ))
    else:
        try:
            from backend.cv.data_ingestion.l1_client import fetch_l1_wind
            l1 = fetch_l1_wind(str(l1_path))
            if l1.get("source") == "DSCOVR (fallback defaults)":
                findings.append(_finding(
                    "l1_fallback_data", "warn",
                    "L1 cache parses to fallback defaults",
                    "The cached DSCOVR file holds no usable reading - the run "
                    "proceeds on 400 km/s / Bz 0 placeholders.",
                ))
        except Exception as exc:
            findings.append(_finding(
                "l1_cache_missing", "info",
                "DSCOVR L1 cache unreadable",
                f"Parse failed ({exc}) - the run will refetch or use fallback defaults.",
            ))

    if not (base / cfg["alert_cache"]).exists():
        findings.append(_finding(
            "alert_cache_missing", "info",
            "NOAA alert cache missing",
            "The run proceeds with an empty alert text block.",
        ))

    return findings, stub, cme, flare, l1


# ── Cross-source physical conflict rules ────────────────────────────────────

def _parse_ts(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def _conflict_findings(stub: dict, cme: dict | None, flare: dict | None,
                       l1: dict | None) -> list[dict]:
    findings: list[dict] = []

    if cme and l1:
        launch, arrive = cme["speed_km_s"], l1["speed_km_s"]
        if arrive > launch * 1.10:
            findings.append(_finding(
                "speed_disagreement", "warn",
                "L1 wind is faster than the CME launch speed",
                f"DSCOVR measures {arrive:.0f} km/s at L1 but DONKI launched this "
                f"CME at {launch:.0f} km/s - arriving faster than launch is "
                "unphysical; one of the two sources is off.",
            ))
        elif arrive < launch * 0.30:
            findings.append(_finding(
                "speed_disagreement", "warn",
                "L1 wind is far slower than the CME launch speed",
                f"{arrive:.0f} km/s at L1 vs {launch:.0f} km/s at launch exceeds "
                "plausible drag-model deceleration - the sources may describe "
                "different events.",
            ))

        arrival_dt = _parse_ts(cme.get("arrival_estimate", ""))
        measured_dt = _parse_ts(l1.get("measured_at", ""))
        if arrival_dt and measured_dt:
            from datetime import timedelta
            l1_eta = measured_dt + timedelta(minutes=l1.get("eta_minutes", 0))
            gap_h = abs((arrival_dt - l1_eta).total_seconds()) / 3600.0
            if gap_h > 12.0:
                findings.append(_finding(
                    "arrival_eta_mismatch", "warn",
                    "DONKI arrival and L1 ETA disagree",
                    f"DONKI's ballistic arrival estimate and the L1-derived ETA "
                    f"are {gap_h:.0f}h apart (ballistic estimates carry ~10h MAE, "
                    "so beyond 12h the sources genuinely conflict).",
                ))

    stub_g = stub.get("scales", {}).get("G", 0)
    if l1 and stub_g >= 3 and l1.get("bz_nt", -1) >= 0:
        findings.append(_finding(
            "bz_northward_strong_g", "warn",
            f"Northward Bz contradicts the G{stub_g} severity",
            f"Cached L1 shows Bz {l1['bz_nt']:+.1f} nT (northward) - northward "
            "IMF does not drive strong geomagnetic storms, and fuse() will drop "
            "its Bz confidence term.",
        ))

    stub_r = stub.get("scales", {}).get("R", 0)
    if flare is not None:
        flare_r = flare.get("r_scale", 0)
        if stub_r >= 2 and flare_r == 0:
            findings.append(_finding(
                "flare_r_mismatch", "warn",
                f"Cached XRS data shows no flare behind the R{stub_r} scale",
                "The GOES cache classifies below M-class in the storm window - "
                "the radio-blackout severity is unsupported by the flux record.",
            ))
        elif abs(stub_r - flare_r) >= 2:
            findings.append(_finding(
                "flare_r_mismatch", "info",
                f"Flare classification R{flare_r} vs expected R{stub_r}",
                "The cached GOES flux classifies two or more R-levels away from "
                "the reference severity for this storm.",
            ))

    return findings


# ── System + quota state ────────────────────────────────────────────────────

def _system_findings() -> list[dict]:
    findings = []
    for name, ok in health_collector.run().items():
        if not ok:
            findings.append(_finding(
                f"check_{name}_degraded", "warn",
                f"Health check '{name}' is degraded",
                _CHECK_CONSEQUENCE.get(name, "This dependency layer is degraded."),
            ))
    return findings


async def _quota_findings(storm_id: str) -> list[dict]:
    findings = []

    wait = peek_rate_limit(storm_id)
    if wait > 0:
        findings.append(_finding(
            "rate_limited", "block",
            "Rate limited - the run will be rejected right now",
            f"One pipeline run per storm per 30s: wait {wait:.0f}s before "
            "running this storm again, or the request returns 429.",
        ))

    from backend.genai.config import GROQ_API_KEYS, GROQ_MODEL
    if GROQ_API_KEYS == [""]:
        findings.append(_finding(
            "no_groq_key", "warn",
            "No Groq API key configured",
            "GROQ_API_KEY / GROQ_API_KEYS is empty - advisory generation will "
            "fail and the run falls back to template advisories.",
        ))
        return findings

    # Never probe the Groq API itself: that spends the quota this check
    # protects. Headroom is this process's own TPM accounting - a soft signal.
    try:
        from backend.genai.llm import _bucket_for
        total = 0
        for key in GROQ_API_KEYS:
            total += await _bucket_for(GROQ_MODEL, key).headroom()
        if total < TPM_LOW_THRESHOLD:
            findings.append(_finding(
                "groq_tpm_low", "warn",
                "Groq token budget nearly exhausted",
                f"~{total} tokens of local TPM headroom left across "
                f"{len(GROQ_API_KEYS)} key(s) for {GROQ_MODEL}. The run will not "
                "fail - it will STALL waiting for the rolling window to clear. "
                "(Process-local accounting; other clients are invisible.)",
            ))
    except Exception as exc:
        log.warning("preflight headroom probe failed: %s", exc)

    return findings


def _estimate_duration() -> int:
    durations = _requester_metrics.get("pipeline_duration_seconds") or []
    return round(sum(durations) / len(durations)) if durations else DEFAULT_DURATION_S


# ── Entry point ─────────────────────────────────────────────────────────────

async def run_preflight(storm_id: str, base_dir: Path | None = None) -> dict:
    """
    Read-only preview of what a pipeline run for storm_id would do.
    base_dir mirrors detect()'s parameter so tests can point at tmp_path.
    """
    cfg = STORM_CONFIGS[storm_id]
    base = Path(base_dir) if base_dir else BACKEND_DIR

    findings = list(await _quota_findings(storm_id))
    cache_findings, stub, cme, flare, l1 = _cache_findings(cfg, base)
    findings += cache_findings
    findings += _conflict_findings(stub, cme, flare, l1)
    findings += _system_findings()

    return {
        "storm_id": storm_id,
        "ready": not any(f["severity"] == "block" for f in findings),
        "estimated_duration_s": _estimate_duration(),
        "findings": findings,
    }
