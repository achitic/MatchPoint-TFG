from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

from matchpoint import MatchPredictor
from matchpoint.feature_builder import build_match_features
from matchpoint.model_registry import uses_dual_pass
from backend.settings import (
    STACKING_TEMPERATURE,
    ELITE_TOP_RANK_MAX,
    ELITE_RANK_GAP_MAX,
    ELITE_ELO_GAP_MAX,
    ELITE_CLAMP_LOW,
    ELITE_CLAMP_HIGH,
)


logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _logit(p: float) -> float:
    p_safe = _clamp(float(p), 1e-6, 1.0 - 1e-6)
    return math.log(p_safe / (1.0 - p_safe))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _temperature_scale_prob(p: float, temperature: float) -> float:
    if temperature <= 1.0:
        return float(p)
    return _sigmoid(_logit(p) / temperature)


def _to_float(x, default: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=4)
def _load_matches_clean(proc_dir_str: str) -> pd.DataFrame:
    """Load matches_clean.parquet once per processed directory path."""
    path = Path(proc_dir_str) / "matches_clean.parquet"
    df = pd.read_parquet(path)
    if "tourney_date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["tourney_date"]):
        df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
    return df


def _latest_rank_asof(
    df_matches: pd.DataFrame,
    player_name: str,
    as_of: str | None,
) -> float:
    """Return latest known ATP rank for a player as of the given date."""
    if "winner_rank" not in df_matches.columns or "loser_rank" not in df_matches.columns:
        return 0.0

    player = str(player_name).strip().lower()
    mask_player = (
        df_matches["winner_name"].astype(str).str.lower().eq(player)
        | df_matches["loser_name"].astype(str).str.lower().eq(player)
    )
    df = df_matches.loc[mask_player]
    if df.empty:
        return 0.0

    if as_of:
        try:
            as_of_ts = pd.Timestamp(as_of)
            if pd.notna(as_of_ts):
                df = df[df["tourney_date"] <= as_of_ts]
        except (TypeError, ValueError):
            logger.warning("Invalid as_of value for rank lookup: %r", as_of)

    if df.empty:
        return 0.0

    row = df.sort_values("tourney_date").iloc[-1]
    if str(row.get("winner_name", "")).strip().lower() == player:
        return _to_float(row.get("winner_rank"), default=0.0)
    return _to_float(row.get("loser_rank"), default=0.0)


def _is_elite_vs_elite_close_matchup(
    predictor: MatchPredictor,
    player_a: str,
    player_b: str,
    surface: str,
    as_of: str | None,
) -> bool:
    """
    Elite guardrail trigger:
    - both players top-10
    - and ranking gap or ELO gap is small.
    """
    try:
        matches = _load_matches_clean(str(predictor.proc_dir))
        rank_a = _latest_rank_asof(matches, player_a, as_of)
        rank_b = _latest_rank_asof(matches, player_b, as_of)
    except Exception as exc:
        logger.warning("Rank guardrail data unavailable: %s", exc)
        rank_a = 0.0
        rank_b = 0.0

    elo_gap = 9_999.0
    try:
        X = build_match_features(
            player_a=player_a,
            player_b=player_b,
            surface=surface,
            as_of=as_of,
            feature_schema=predictor.feature_names,
            proc_dir=predictor.proc_dir,
        )
        row = X.iloc[0]
        if "elo_diff_global" in row:
            elo_gap = abs(_to_float(row.get("elo_diff_global", 0.0), default=0.0))
    except Exception as exc:
        logger.warning("ELO guardrail features unavailable: %s", exc)

    if rank_a <= 0.0 or rank_b <= 0.0:
        return False

    both_top_elite = rank_a <= ELITE_TOP_RANK_MAX and rank_b <= ELITE_TOP_RANK_MAX
    rank_gap_small = abs(rank_a - rank_b) <= ELITE_RANK_GAP_MAX
    elo_gap_small = elo_gap <= ELITE_ELO_GAP_MAX
    return both_top_elite and (rank_gap_small or elo_gap_small)


def predict_pair_probabilities(
    predictor: MatchPredictor,
    model_id: str,
    player_a: str,
    player_b: str,
    surface: str,
    as_of: str | None,
) -> tuple[float, float]:
    """
    Return coherent pair probabilities for A/B.

    For directional models (for now: stacking_ensemble), run A->B and B->A
    and normalize to avoid asymmetric outputs being interpreted as final probs.
    """
    p_a_raw = float(predictor.predict_proba(player_a, player_b, surface, as_of=as_of))

    if not uses_dual_pass(model_id):
        if _is_elite_vs_elite_close_matchup(
            predictor=predictor,
            player_a=player_a,
            player_b=player_b,
            surface=surface,
            as_of=as_of,
        ):
            p_a_raw = _clamp(p_a_raw, ELITE_CLAMP_LOW, ELITE_CLAMP_HIGH)
        return p_a_raw, 1.0 - p_a_raw

    p_b_raw = float(predictor.predict_proba(player_b, player_a, surface, as_of=as_of))
    denom = p_a_raw + p_b_raw
    if denom <= 0:
        return 0.5, 0.5

    p_a = p_a_raw / denom

    if model_id == "stacking_ensemble":
        # Confidence compression via temperature scaling.
        p_a = _temperature_scale_prob(p_a, STACKING_TEMPERATURE)

    # Product guardrail for elite-vs-elite close matchups (all model outputs).
    if _is_elite_vs_elite_close_matchup(
        predictor=predictor,
        player_a=player_a,
        player_b=player_b,
        surface=surface,
        as_of=as_of,
    ):
        p_a = _clamp(p_a, ELITE_CLAMP_LOW, ELITE_CLAMP_HIGH)

    return p_a, 1.0 - p_a
