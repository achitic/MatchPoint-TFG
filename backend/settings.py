# backend/settings.py
"""
Configuration settings for the MatchPoint backend.
Uses paths relative to the repository root.
Supports .env files via python-dotenv (if installed).
"""
import os
from pathlib import Path
from matchpoint.model_registry import DEFAULT_MODEL_ID, get_available_model_ids

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

# Repo root is parent of backend/
REPO_ROOT = Path(__file__).resolve().parents[1]

# Data paths
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = REPO_ROOT / "models"

# Parquet files
MATCHES_CLEAN_PATH = PROCESSED_DIR / "matches_clean.parquet"
ELO_HISTORY_PATH = PROCESSED_DIR / "elo_history.csv"

# Available models
AVAILABLE_MODELS = get_available_model_ids(scope="predict", include_aliases=False)
DEFAULT_MODEL = DEFAULT_MODEL_ID

# Available surfaces
AVAILABLE_SURFACES = ["Hard", "Clay", "Grass"]

# Operational bounds used when a caller overrides the pre-match probability.
# The public contract accepts the full probability domain [0, 1], while the
# simulator keeps a small amount of uncertainty so point probabilities remain
# numerically stable.
MIN_PROBABILITY_OVERRIDE = 0.01
MAX_PROBABILITY_OVERRIDE = 0.99

# CORS allowed origins — configurable via CORS_ORIGINS env var
# Default: localhost dev ports for Vite and CRA
_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    CORS_ORIGINS: list[str] = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
else:
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]


def _float_env(name: str, default: float) -> float:
    """Read float from env var with safe fallback."""
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    """Read a positive integer from an env var with a safe fallback."""
    raw = os.environ.get(name)
    if raw is None:
        return max(int(default), minimum)
    try:
        return max(int(raw), minimum)
    except ValueError:
        return max(int(default), minimum)


# Guardrail config for extreme pre-match probabilities.
STACKING_TEMPERATURE = _float_env("STACKING_TEMPERATURE", 3.0)
ELITE_TOP_RANK_MAX = _float_env("ELITE_TOP_RANK_MAX", 10.0)
ELITE_RANK_GAP_MAX = _float_env("ELITE_RANK_GAP_MAX", 5.0)
ELITE_ELO_GAP_MAX = _float_env("ELITE_ELO_GAP_MAX", 120.0)
ELITE_CLAMP_LOW = _float_env("ELITE_CLAMP_LOW", 0.30)
ELITE_CLAMP_HIGH = _float_env("ELITE_CLAMP_HIGH", 0.70)

# In-memory live tracker lifecycle. These defaults cap memory growth while
# keeping an active match available for a normal playing session.
INPLAY_STATE_TTL_SECONDS = _int_env("INPLAY_STATE_TTL_SECONDS", 6 * 60 * 60)
INPLAY_MAX_STATES = _int_env("INPLAY_MAX_STATES", 1000)
