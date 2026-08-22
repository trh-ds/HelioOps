"""Shared test fixtures for HelioOps retrieval tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The repo root (parent of backend/) must be importable as `backend.*`.
# conftest.py runs before any test module, so this is the only place that needs it.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def g4_fixture() -> dict:
    """Oct 2024 G4 storm event fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "march_2024_g4.json"
    return json.loads(fixture_path.read_text())
