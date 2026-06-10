"""Shared test fixtures for HelioOps retrieval tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


@pytest.fixture(scope="session")
def g4_fixture() -> dict:
    """Oct 2024 G4 storm event fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "march_2024_g4.json"
    return json.loads(fixture_path.read_text())
