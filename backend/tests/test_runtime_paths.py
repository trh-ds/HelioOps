"""
Runtime path resolution — the failure mode both of these pin is silent.

A misresolved Chroma path does not raise: chromadb creates the directory,
every collection comes back empty, retrieve_chunks() swallows it, and the
advisories still look well-formed. This actually happened — the
`backend/data/chroma_db` shipped in .env and .env.example resolved against
the backend *package* instead of the repo root, giving
`backend/backend/data/chroma_db`, and every advisory was ungrounded.

Same class for the ML checkpoints: predict() falls back to hardcoded
"conservative defaults" when they are missing, so a wrong CHECKPOINT_DIR in a
container reads as a working model that always returns the same numbers.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestChromaPathResolution:
    def test_relative_override_resolves_against_repo_root(self):
        with patch.dict(os.environ, {"HELIOOPS_CHROMA_PERSIST_PATH": "backend/data/chroma_db"}):
            cfg = importlib.reload(importlib.import_module("backend.embeddings.config"))
            assert Path(cfg.CHROMA_PERSIST_PATH) == REPO_ROOT / "backend" / "data" / "chroma_db"
        importlib.reload(importlib.import_module("backend.embeddings.config"))

    def test_shipped_env_example_value_points_at_the_committed_db(self):
        """.env.example is what a fresh deploy copies — its value must be the real DB."""
        line = next(
            line for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
            if line.startswith("HELIOOPS_CHROMA_PERSIST_PATH=")
        )
        value = line.split("=", 1)[1].strip()
        with patch.dict(os.environ, {"HELIOOPS_CHROMA_PERSIST_PATH": value}):
            cfg = importlib.reload(importlib.import_module("backend.embeddings.config"))
            assert (Path(cfg.CHROMA_PERSIST_PATH) / "chroma.sqlite3").exists()
        importlib.reload(importlib.import_module("backend.embeddings.config"))

    def test_every_knowledge_base_is_populated(self):
        from backend.embeddings.collections import COLLECTION_NAMES, count_collection

        counts = {name: count_collection(name) for name in COLLECTION_NAMES}
        assert all(counts.values()), f"empty KB(s): {counts}"

    def test_readiness_reports_the_knowledge_base(self):
        from backend.health import health_collector

        assert health_collector.run()["knowledge_base"] is True


class TestCheckpointPathResolution:
    def test_inference_uses_backend_paths(self):
        from backend.ml import inference
        from backend.paths import CHECKPOINT_DIR

        assert inference._CHECKPOINT_DIR == CHECKPOINT_DIR

    def test_the_six_synthetic_checkpoints_load(self):
        """The synthetic-trained LightGBM layer is what serves; no fallback allowed."""
        from backend.ml.inference import _MODELS, _load_models

        _load_models()
        assert len(_MODELS) == 6, "predict() would silently return conservative defaults"

    def test_prediction_is_driven_by_the_model_not_the_fallback(self):
        from backend.ml.inference import predict

        quiet = predict({"scales": {"G": 0, "R": 0}, "cme": {"speed_km_s": 400.0},
                         "l1_solar_wind": {"bz_nt": 2.0, "speed_km_s": 350.0}})
        severe = predict({"scales": {"G": 5, "R": 3}, "cme": {"speed_km_s": 2200.0},
                          "l1_solar_wind": {"bz_nt": -40.0, "speed_km_s": 900.0}})
        assert severe.gps_error_m > quiet.gps_error_m
        assert severe.hf_blackout_prob > quiet.hf_blackout_prob
        assert severe.gps_error_ci_low <= severe.gps_error_m <= severe.gps_error_ci_high

        # Magnitude floors, not just ordering — a uniformly weak model orders
        # correctly and is still useless. Same thresholds as
        # backend/ml/03_anchor_test.py; keep the two in step.
        assert severe.gps_error_m > 15.0, "G5 anchor below the severe GPS floor"
        assert severe.hf_blackout_prob > 0.80, "G5 anchor below the severe HF floor"
        assert quiet.gps_error_m < 2.0, "quiet baseline is not quiet"


class TestIngestCachePathResolution:
    """
    Third instance of the same silent class: the ingest CLIs defaulted their
    cache roots to the CWD while detect() resolves them from backend.paths, so
    the documented `PYTHONPATH=. python -m backend.cv...` commands wrote FITS
    and JSON into <repo>/data/cached/ where the detector never looks. Nothing
    raised -- detect() just fell back to the stub for every run, forever.
    """

    def test_fits_cache_defaults_under_the_backend_package(self):
        from backend.cv.data_ingestion import cache_fits
        from backend.paths import BACKEND_DIR

        captured = {}

        def fake_sync(year, month, day, output_dir):
            captured["dir"] = output_dir
            return []

        with patch.object(cache_fits, "sync_ccor1", fake_sync):
            cache_fits.fetch_storm("2024-10-G4")
        assert Path(captured["dir"]).is_relative_to(BACKEND_DIR)

    def test_no_ingest_cli_defaults_an_argument_to_the_cwd(self):
        """
        Source check, not a call: these defaults are argparse literals, so the
        only way to reach them is to run the CLI, which downloads. `default="."`
        and a bare `default="data/..."` are both cwd-relative and both wrong.
        """
        from backend.cv import data_ingestion, image_threshold_algorithm

        offenders = []
        for pkg in (data_ingestion, image_threshold_algorithm):
            for src_file in Path(pkg.__file__).parent.glob("*.py"):
                for i, line in enumerate(src_file.read_text(encoding="utf-8").splitlines(), 1):
                    if "add_argument" not in line or "default=" not in line:
                        continue
                    if 'default="."' in line or 'default="data/' in line:
                        offenders.append(f"{src_file.name}:{i}")
        assert not offenders, f"cwd-relative CLI defaults: {offenders}"
