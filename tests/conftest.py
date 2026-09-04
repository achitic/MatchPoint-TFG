# tests/conftest.py
"""
Pytest configuration and shared fixtures for MatchPoint tests.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add repo root to path so imports work
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient — loads app once per test session."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def predict_service():
    """PredictService singleton — loads data once per test session."""
    from backend.services.predict_service import get_service
    return get_service()


@pytest.fixture(scope="session")
def simulate_service():
    """SimulateService singleton — loads data once per test session."""
    from backend.services.simulate_service import get_simulate_service
    return get_simulate_service()


@pytest.fixture(scope="session")
def tournament_service():
    """TournamentService singleton — loads data once per test session."""
    from backend.services.tournament_service import get_tournament_service
    return get_tournament_service()


# ── Common test data ────────────────────────────────────────────────────────
PLAYER_A = "Carlos Alcaraz"
PLAYER_B = "Jannik Sinner"
SURFACE = "Hard"
AS_OF = "2024-01-01"
