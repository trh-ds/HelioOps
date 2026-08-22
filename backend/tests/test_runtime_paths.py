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
