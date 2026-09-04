# backend/services/simulate_service.py
"""
Service layer for match simulation.

This service:
1. Uses the existing MatchPredictor to get match-level probability
2. Converts match probability to point-level probabilities (proxy v0)
3. Runs the simulation engine
"""
from __future__ import annotations

import math
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Literal

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from matchpoint import MatchPredictor
from matchpoint.sim_engine import (
    _match_fatigue_factor,
    simulate_match,
    simulate_game,
    simulate_tiebreak,
)
from matchpoint.model_registry import DEFAULT_MODEL_ID, normalize_model_id
from backend.settings import (
    MATCHES_CLEAN_PATH,
    PROCESSED_DIR,
    MIN_PROBABILITY_OVERRIDE,
    MAX_PROBABILITY_OVERRIDE,
    INPLAY_STATE_TTL_SECONDS,
    INPLAY_MAX_STATES,
)
from backend.services.inference_utils import predict_pair_probabilities


# Surface-specific parameters for point probability proxy (v0)
SURFACE_PARAMS = {
    "Hard": {"base": 0.62, "delta_max": 0.06},
    "Clay": {"base": 0.60, "delta_max": 0.05},
    "Grass": {"base": 0.64, "delta_max": 0.07},
}
INPLAY_PRIOR_STRENGTH = 24.0


def _clamp(x: float, lo: float, hi: float) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, x))


def _logit(p: float) -> float:
    """Convert probability to log-odds."""
    p_clamped = _clamp(p, 0.02, 0.98)
    return math.log(p_clamped / (1.0 - p_clamped))


def compute_point_probabilities(
    p_match_a: float,
    surface: str,
) -> dict:
    """
    Convert match-level probability to point-level serve probabilities.
    
    This is a v0 proxy method. In the future, this should be replaced by
    a dedicated point-by-point model trained on actual point data.
    
    Method: logit + tanh + surface-specific clamp
    - Convert p_match_a to log-odds (strength)
    - Apply tanh saturation
    - Add/subtract from surface baseline
    - Clamp to realistic range [0.50, 0.75]
    
    Args:
        p_match_a: Probability of player A winning the match (from model)
        surface: "Hard", "Clay", or "Grass"
        
    Returns:
        {
            "proxy_method": "logit+tanh_surface_clamp_v0",
            "surface_base": float,
            "delta_max": float,
            "strength_a": float,
            "p_point_on_serve_a": float,
            "p_point_on_serve_b": float,
        }
    """
    params = SURFACE_PARAMS.get(surface, SURFACE_PARAMS["Hard"])
    base = params["base"]
    delta_max = params["delta_max"]
    
    strength = _logit(p_match_a)
    
    delta = delta_max * math.tanh(strength / 2.0)
    
    p_serve_a = _clamp(base + delta, 0.50, 0.75)
    p_serve_b = _clamp(base - delta, 0.50, 0.75)
    
    return {
        "proxy_method": "logit+tanh_surface_clamp_v0",
        "surface_base": base,
        "delta_max": delta_max,
        "strength_a": round(strength, 4),
        "p_point_on_serve_a": round(p_serve_a, 4),
        "p_point_on_serve_b": round(p_serve_b, 4),
    }


def _point_to_game_hold_prob(p_point_server: float) -> float:
    """
    Convert point-on-serve probability into game hold probability.

    Uses the closed-form tennis game model with deuce recursion.
    """
    p = _clamp(p_point_server, 1e-6, 1 - 1e-6)
    q = 1.0 - p
    pre_deuce = (p ** 4) * (1 + 4 * q + 10 * (q ** 2))
    deuce_reach = 20 * (p ** 3) * (q ** 3)
    deuce_win = (p ** 2) / max(1e-6, 1 - 2 * p * q)
    return _clamp(pre_deuce + deuce_reach * deuce_win, 0.0, 1.0)


def _build_point_trace(
    *,
    point: dict,
    server: Literal["A", "B"],
    sets_a: int,
    sets_b: int,
    games_a: int,
    games_b: int,
    alpha_before: float,
    beta_before: float,
    alpha_after: float,
    beta_after: float,
    observations: int,
) -> dict:
    """Build compact point-level trace for bayesian simulation timelines."""
    p_before = alpha_before / (alpha_before + beta_before)
    p_after = alpha_after / (alpha_after + beta_after)
    delta = p_after - p_before
    pressure = float(point.get("pressure", 0.0) or 0.0)
    fatigue = float(point.get("fatigue_factor", 0.0) or 0.0)
    p_server_eff = float(point.get("p_server_eff", p_after) or p_after)

    if abs(delta) < 0.0005:
        posterior_text = "Posterior bayesiano estable tras el punto"
    else:
        direction = "sube" if delta > 0 else "baja"
        posterior_text = f"Posterior bayesiano del saque de {server} {direction} {abs(delta) * 100:.1f} pp"

    return {
        "server": server,
        "p_server_bayes_before": round(p_before, 4),
        "p_server_bayes_after": round(p_after, 4),
        "p_server_bayes_delta": round(delta, 4),
        "p_server_eff": round(p_server_eff, 4),
        "observations_after": observations,
        "trace_factors": [
            f"Marcador: sets {sets_a}-{sets_b}, juegos {games_a}-{games_b}, punto {point.get('score', 'n/d')}",
            f"Presion: {pressure:.2f}",
            f"Fatiga: {fatigue * 100:.0f}%",
            posterior_text,
        ],
    }


def _quantile(sorted_values: list[float], q: float) -> float:
    """Simple linear-interpolated quantile for sorted arrays."""
    if not sorted_values:
        return 0.5
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = _clamp(q, 0.0, 1.0) * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    w = pos - lo
    return sorted_values[lo] * (1 - w) + sorted_values[hi] * w


class SimulateService:
    """Service for simulating tennis matches."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._players_cache: Optional[list[str]] = None
        self._max_date_cache: Optional[pd.Timestamp] = None
        self._min_date_cache: Optional[pd.Timestamp] = None
        self._predictors: dict[str, MatchPredictor] = {}
        self._probability_cache: dict[tuple[str, str, str, str, str | None], tuple[float, float]] = {}
        self._inplay_states: dict[str, dict] = {}
        self._clock = clock
        self._inplay_ttl_seconds = INPLAY_STATE_TTL_SECONDS
        self._inplay_max_states = INPLAY_MAX_STATES

    def _prune_inplay_states(self, now: Optional[float] = None) -> None:
        """Remove expired states and enforce the configured memory bound."""
        current = self._clock() if now is None else now
        expired = [
            match_id
            for match_id, state in self._inplay_states.items()
            if current - float(state.get("last_activity", current)) >= self._inplay_ttl_seconds
        ]
        for match_id in expired:
            self._inplay_states.pop(match_id, None)

        while len(self._inplay_states) > self._inplay_max_states:
            oldest_id = min(
                self._inplay_states,
                key=lambda key: float(self._inplay_states[key].get("last_activity", current)),
            )
            self._inplay_states.pop(oldest_id, None)

    def _reserve_inplay_slot(self, now: float) -> None:
        self._prune_inplay_states(now)
        while len(self._inplay_states) >= self._inplay_max_states:
            oldest_id = min(
                self._inplay_states,
                key=lambda key: float(self._inplay_states[key].get("last_activity", now)),
            )
            self._inplay_states.pop(oldest_id, None)

    def get_players(self) -> list[str]:
        """Get sorted list of unique player names."""
        if self._players_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            winners = set(df["winner_name"].dropna().unique())
            losers = set(df["loser_name"].dropna().unique())
            self._players_cache = sorted(winners | losers)
        return self._players_cache

    def _load_date_bounds(self):
        """Load min and max dates from dataset."""
        if self._max_date_cache is None or self._min_date_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            df["tourney_date"] = pd.to_datetime(df["tourney_date"])
            self._max_date_cache = df["tourney_date"].max()
            self._min_date_cache = df["tourney_date"].min()

    def get_max_date(self) -> pd.Timestamp:
        self._load_date_bounds()
        return self._max_date_cache

    def get_min_date(self) -> pd.Timestamp:
        self._load_date_bounds()
        return self._min_date_cache

    def _get_predictor(self, model: str) -> MatchPredictor:
        """Get or create predictor for the given model variant."""
        if model not in self._predictors:
            self._predictors[model] = MatchPredictor.load(
                base_dir=REPO_ROOT,
                variant=model
            )
        return self._predictors[model]

    def _predict_pair_cached(
        self,
        *,
        predictor: MatchPredictor,
        model_id: str,
        player_a: str,
        player_b: str,
        surface: str,
        as_of: str | None,
    ) -> tuple[float, float]:
        key = (model_id, player_a.strip().lower(), player_b.strip().lower(), surface, as_of)
        reverse_key = (model_id, key[2], key[1], surface, as_of)
        if key in self._probability_cache:
            return self._probability_cache[key]
        if reverse_key in self._probability_cache:
            p_b, p_a = self._probability_cache[reverse_key]
            self._probability_cache[key] = (p_a, p_b)
            return p_a, p_b

        p_a, p_b = predict_pair_probabilities(
            predictor=predictor,
            model_id=model_id,
            player_a=player_a,
            player_b=player_b,
            surface=surface,
            as_of=as_of,
        )
        self._probability_cache[key] = (p_a, p_b)
        return p_a, p_b

    def _resolve_as_of(self, as_of: Optional[str], warnings: list[str]) -> str:
        """Resolve as_of date with dataset min/max clamping."""
        max_date = self.get_max_date()
        min_date = self.get_min_date()

        if as_of is None:
            return max_date.strftime("%Y-%m-%d")

        try:
            as_of_dt = pd.Timestamp(as_of)
            if as_of_dt > max_date:
                warnings.append(
                    f"as_of clamped to dataset max_date: {max_date.strftime('%Y-%m-%d')}"
                )
                return max_date.strftime("%Y-%m-%d")
            if as_of_dt < min_date:
                warnings.append(
                    f"as_of clamped to dataset min_date: {min_date.strftime('%Y-%m-%d')}"
                )
                return min_date.strftime("%Y-%m-%d")
            return as_of
        except Exception:
            warnings.append(f"Invalid date format '{as_of}'. Using max date.")
            return max_date.strftime("%Y-%m-%d")

    def _build_inplay_snapshot(self, state: dict) -> dict:
        """Return API-safe in-play state snapshot."""
        sets_to_win = (state["best_of"] + 1) // 2
        finished = state["sets_a"] >= sets_to_win or state["sets_b"] >= sets_to_win
        winner = None
        if finished:
            winner = "A" if state["sets_a"] > state["sets_b"] else "B"
        return {
            "match_id": state["match_id"],
            "player_a": state["player_a"],
            "player_b": state["player_b"],
            "surface": state["surface"],
            "model": state["model"],
            "as_of_used": state["as_of_used"],
            "best_of": state["best_of"],
            "current_server": state["current_server"],
            "sets_a": state["sets_a"],
            "sets_b": state["sets_b"],
            "games_a": state["games_a"],
            "games_b": state["games_b"],
            "status": "finished" if finished else "in_progress",
            "winner": winner,
            "p_prior_a": round(state["p_prior_a"], 4),
            "p_prior_b": round(1.0 - state["p_prior_a"], 4),
            "p_live_a": round(state["p_live_a"], 4),
            "p_live_ci_low": round(state["p_live_ci_low"], 4),
            "p_live_ci_high": round(state["p_live_ci_high"], 4),
            "uncertainty": round(state["uncertainty"], 4),
            "n_observations": int(state["n_observations"]),
            "warnings": list(state.get("warnings", [])),
            "events": [dict(e) for e in state.get("events", [])],
        }

    def _refresh_inplay_live_probs(self, state: dict) -> None:
        """Recompute live probability + CI from current in-play state."""
        sets_to_win = (state["best_of"] + 1) // 2
        if state["sets_a"] >= sets_to_win:
            state["p_live_a"] = 1.0
            state["p_live_ci_low"] = 1.0
            state["p_live_ci_high"] = 1.0
            state["uncertainty"] = 0.0
            return
        if state["sets_b"] >= sets_to_win:
            state["p_live_a"] = 0.0
            state["p_live_ci_low"] = 0.0
            state["p_live_ci_high"] = 0.0
            state["uncertainty"] = 0.0
            return

        p_live, ci_low, ci_high = self._estimate_live_match_prob(
            alpha_a=state["alpha_a"],
            beta_a=state["beta_a"],
            alpha_b=state["alpha_b"],
            beta_b=state["beta_b"],
            sets_a=state["sets_a"],
            sets_b=state["sets_b"],
            games_a=state["games_a"],
            games_b=state["games_b"],
            next_server=state["current_server"],
            best_of=state["best_of"],
        )
        state["p_live_a"] = p_live
        state["p_live_ci_low"] = ci_low
        state["p_live_ci_high"] = ci_high
        state["uncertainty"] = max(0.0, ci_high - ci_low)

    def init_inplay(
        self,
        player_a: str,
        player_b: str,
        surface: str,
        model: str = DEFAULT_MODEL_ID,
        as_of: Optional[str] = None,
        best_of: int = 3,
        first_server: Literal["A", "B", "random"] = "random",
    ) -> dict:
        """Initialize a persistent in-play bayesian state."""
        warnings: list[str] = []
        canonical_model = normalize_model_id(model, scope="simulate")

        if player_a.strip().lower() == player_b.strip().lower():
            raise ValueError("player_a and player_b must be different")

        as_of_used = self._resolve_as_of(as_of, warnings)
        predictor = self._get_predictor(canonical_model)
        p_a, _ = self._predict_pair_cached(
            predictor=predictor,
            model_id=canonical_model,
            player_a=player_a,
            player_b=player_b,
            surface=surface,
            as_of=as_of_used,
        )
        point_params = compute_point_probabilities(p_a, surface)
        alpha_a = INPLAY_PRIOR_STRENGTH * float(point_params["p_point_on_serve_a"])
        beta_a = INPLAY_PRIOR_STRENGTH * (1.0 - float(point_params["p_point_on_serve_a"]))
        alpha_b = INPLAY_PRIOR_STRENGTH * float(point_params["p_point_on_serve_b"])
        beta_b = INPLAY_PRIOR_STRENGTH * (1.0 - float(point_params["p_point_on_serve_b"]))

        if first_server == "random":
            current_server: Literal["A", "B"] = "A" if random.random() < 0.5 else "B"
        else:
            current_server = first_server

        now = self._clock()
        self._reserve_inplay_slot(now)
        match_id = f"inplay_{uuid.uuid4().hex[:12]}"
        state = {
            "match_id": match_id,
            "player_a": player_a,
            "player_b": player_b,
            "surface": surface,
            "model": canonical_model,
            "as_of_used": as_of_used,
            "best_of": best_of,
            "current_server": current_server,
            "sets_a": 0,
            "sets_b": 0,
            "games_a": 0,
            "games_b": 0,
            "alpha_a": alpha_a,
            "beta_a": beta_a,
            "alpha_b": alpha_b,
            "beta_b": beta_b,
            "p_prior_a": float(p_a),
            "p_live_a": float(p_a),
            "p_live_ci_low": 0.0,
            "p_live_ci_high": 1.0,
            "uncertainty": 1.0,
            "n_observations": 0,
            "warnings": warnings,
            "events": [],
            "created_at": now,
            "last_activity": now,
        }
        self._refresh_inplay_live_probs(state)
        self._inplay_states[match_id] = state
        return self._build_inplay_snapshot(state)

    def update_inplay(
        self,
        match_id: str,
        server: Literal["A", "B"],
        game_winner: Literal["A", "B"],
        server_points_won: int = 0,
        server_points_lost: int = 0,
        is_tiebreak: Optional[bool] = None,
    ) -> dict:
        """Apply one completed game update to an in-play state."""
        now = self._clock()
        self._prune_inplay_states(now)
        state = self._inplay_states.get(match_id)
        if state is None:
            raise ValueError(f"match_id '{match_id}' not found")

        sets_to_win = (state["best_of"] + 1) // 2
        if state["sets_a"] >= sets_to_win or state["sets_b"] >= sets_to_win:
            return self._build_inplay_snapshot(state)

        if server != state["current_server"]:
            raise ValueError(
                f"server mismatch: expected {state['current_server']}, received {server}"
            )

        effective_is_tiebreak = state["games_a"] == 6 and state["games_b"] == 6
        if is_tiebreak is not None and is_tiebreak != effective_is_tiebreak:
            expected = "a tie-break" if effective_is_tiebreak else "a regular game"
            raise ValueError(f"score requires {expected}; is_tiebreak cannot override it")

        won = max(int(server_points_won), 0)
        lost = max(int(server_points_lost), 0)
        winner_points = won if game_winner == server else lost
        loser_points = lost if game_winner == server else won
        minimum_points = 7 if effective_is_tiebreak else 4
        if winner_points < minimum_points or winner_points - loser_points < 2:
            game_type = "tie-break" if effective_is_tiebreak else "juego"
            raise ValueError(
                f"Marcador de {game_type} completado no válido: el ganador necesita "
                f"al menos {minimum_points} puntos y una diferencia de dos puntos"
            )
        if server == "A":
            state["alpha_a"] += won
            state["beta_a"] += lost
        else:
            state["alpha_b"] += won
            state["beta_b"] += lost
        state["n_observations"] += won + lost

        if game_winner == "A":
            state["games_a"] += 1
        else:
            state["games_b"] += 1

        set_winner: Optional[Literal["A", "B"]] = None
        if effective_is_tiebreak:
            set_winner = "A" if state["games_a"] > state["games_b"] else "B"
        elif state["games_a"] >= 6 and state["games_a"] - state["games_b"] >= 2:
            set_winner = "A"
        elif state["games_b"] >= 6 and state["games_b"] - state["games_a"] >= 2:
            set_winner = "B"

        if set_winner is not None:
            if set_winner == "A":
                state["sets_a"] += 1
            else:
                state["sets_b"] += 1
            state["games_a"] = 0
            state["games_b"] = 0

        state["current_server"] = "B" if server == "A" else "A"

        self._refresh_inplay_live_probs(state)
        state["events"].append(
            {
                "server": server,
                "game_winner": game_winner,
                "server_points_won": won,
                "server_points_lost": lost,
                "is_tiebreak": effective_is_tiebreak,
                "sets_a": state["sets_a"],
                "sets_b": state["sets_b"],
                "games_a": state["games_a"],
                "games_b": state["games_b"],
                "p_live_a": state["p_live_a"],
                "p_live_ci_low": state["p_live_ci_low"],
                "p_live_ci_high": state["p_live_ci_high"],
            }
        )
        state["last_activity"] = now
        return self._build_inplay_snapshot(state)

    def get_inplay_state(self, match_id: str) -> dict:
        """Get current in-play state by id."""
        now = self._clock()
        self._prune_inplay_states(now)
        state = self._inplay_states.get(match_id)
        if state is None:
            raise ValueError(f"match_id '{match_id}' not found")
        state["last_activity"] = now
        return self._build_inplay_snapshot(state)

    def delete_inplay_state(self, match_id: str) -> bool:
        """Delete an in-play state explicitly and release its memory."""
        self._prune_inplay_states()
        if match_id not in self._inplay_states:
            raise ValueError(f"match_id '{match_id}' not found")
        del self._inplay_states[match_id]
        return True

    def _estimate_live_match_prob(
        self,
        alpha_a: float,
        beta_a: float,
        alpha_b: float,
        beta_b: float,
        sets_a: int,
        sets_b: int,
        games_a: int,
        games_b: int,
        next_server: Literal["A", "B"],
        best_of: int,
        n_samples: int = 200,
    ) -> tuple[float, float, float]:
        """Monte Carlo estimate of P(A wins) from current state + posterior uncertainty."""
        sets_to_win = (best_of + 1) // 2
        if sets_a >= sets_to_win:
            return 1.0, 1.0, 1.0
        if sets_b >= sets_to_win:
            return 0.0, 0.0, 0.0

        rng = random.Random(17_424_211)  # deterministic CI estimates for reproducibility
        outcomes: list[float] = []

        for _ in range(max(50, n_samples)):
            p_serve_a = rng.betavariate(alpha_a, beta_a)
            p_serve_b = rng.betavariate(alpha_b, beta_b)
            hold_a = _point_to_game_hold_prob(p_serve_a)
            hold_b = _point_to_game_hold_prob(p_serve_b)

            sim_sets_a = sets_a
            sim_sets_b = sets_b
            sim_games_a = games_a
            sim_games_b = games_b
            sim_server: Literal["A", "B"] = next_server

            while sim_sets_a < sets_to_win and sim_sets_b < sets_to_win:
                while True:
                    if sim_games_a == 6 and sim_games_b == 6:
                        tb_a = 0
                        tb_b = 0
                        tb_server: Literal["A", "B"] = sim_server
                        pts_this_server = 0
                        first_done = False
                        while True:
                            p_server = p_serve_a if tb_server == "A" else p_serve_b
                            server_wins = rng.random() < p_server
                            if tb_server == "A":
                                tb_a += 1 if server_wins else 0
                                tb_b += 0 if server_wins else 1
                            else:
                                tb_b += 1 if server_wins else 0
                                tb_a += 0 if server_wins else 1

                            if tb_a >= 7 and tb_a - tb_b >= 2:
                                sim_games_a += 1
                                break
                            if tb_b >= 7 and tb_b - tb_a >= 2:
                                sim_games_b += 1
                                break

                            pts_this_server += 1
                            if not first_done:
                                if pts_this_server == 1:
                                    first_done = True
                                    pts_this_server = 0
                                    tb_server = "B" if tb_server == "A" else "A"
                            else:
                                if pts_this_server == 2:
                                    pts_this_server = 0
                                    tb_server = "B" if tb_server == "A" else "A"
                        break

                    if sim_server == "A":
                        game_a = rng.random() < hold_a
                        if game_a:
                            sim_games_a += 1
                        else:
                            sim_games_b += 1
                    else:
                        game_b = rng.random() < hold_b
                        if game_b:
                            sim_games_b += 1
                        else:
                            sim_games_a += 1

                    if sim_games_a >= 6 and sim_games_a - sim_games_b >= 2:
                        break
                    if sim_games_b >= 6 and sim_games_b - sim_games_a >= 2:
                        break
                    sim_server = "B" if sim_server == "A" else "A"

                if sim_games_a > sim_games_b:
                    sim_sets_a += 1
                else:
                    sim_sets_b += 1

                total_games = sim_games_a + sim_games_b
                if total_games % 2 == 1:
                    sim_server = "B" if sim_server == "A" else "A"

                sim_games_a = 0
                sim_games_b = 0

            outcomes.append(1.0 if sim_sets_a > sim_sets_b else 0.0)

        outcomes.sort()
        mean = sum(outcomes) / len(outcomes)
        lo = _quantile(outcomes, 0.05)
        hi = _quantile(outcomes, 0.95)
        return round(mean, 4), round(lo, 4), round(hi, 4)

    def _simulate_bayes_live(
        self,
        p_match_a: float,
        surface: str,
        rng: random.Random,
        best_of: int,
        first_server: Literal["A", "B", "random"],
        timeline_mode: Literal["none", "games", "points"],
    ) -> tuple[dict, dict]:
        """
        Simulate match with bayesian in-play updates of serve point probabilities.

        Returns:
            (match_result, params)
        """
        base_params = compute_point_probabilities(p_match_a, surface)
        prior_strength = INPLAY_PRIOR_STRENGTH
        p_a0 = float(base_params["p_point_on_serve_a"])
        p_b0 = float(base_params["p_point_on_serve_b"])

        alpha_a = prior_strength * p_a0
        beta_a = prior_strength * (1.0 - p_a0)
        alpha_b = prior_strength * p_b0
        beta_b = prior_strength * (1.0 - p_b0)

        sets_to_win = (best_of + 1) // 2
        sets_a = 0
        sets_b = 0
        set_scores: list[str] = []
        timeline = [] if timeline_mode != "none" else None

        if first_server == "random":
            current_server: Literal["A", "B"] = "A" if rng.random() < 0.5 else "B"
        else:
            current_server = first_server

        set_num = 0
        observations = 0
        last_live = 0.5
        last_ci_low = 0.05
        last_ci_high = 0.95
        completed_games_total = 0

        while sets_a < sets_to_win and sets_b < sets_to_win:
            set_num += 1
            games_a = 0
            games_b = 0
            set_games_log = [] if timeline_mode != "none" else None
            game_num = 0

            while True:
                game_num += 1

                if games_a == 6 and games_b == 6:
                    fatigue_factor = _match_fatigue_factor(completed_games_total + games_a + games_b)
                    p_serve_a = alpha_a / (alpha_a + beta_a)
                    p_serve_b = alpha_b / (alpha_b + beta_b)
                    tb_winner, tb_points = simulate_tiebreak(
                        p_serve_a=p_serve_a,
                        p_serve_b=p_serve_b,
                        rng=rng,
                        first_server=current_server,
                        track_points=True,
                        fatigue_factor=fatigue_factor,
                    )
                    for pt in tb_points or []:
                        srv = pt["server"]
                        srv_won = pt["winner"] == srv
                        if srv == "A":
                            alpha_before, beta_before = alpha_a, beta_a
                        else:
                            alpha_before, beta_before = alpha_b, beta_b

                        if srv == "A":
                            alpha_a += 1 if srv_won else 0
                            beta_a += 0 if srv_won else 1
                            alpha_after, beta_after = alpha_a, beta_a
                        else:
                            alpha_b += 1 if srv_won else 0
                            beta_b += 0 if srv_won else 1
                            alpha_after, beta_after = alpha_b, beta_b
                        observations += 1
                        if timeline_mode == "points":
                            pt.update(_build_point_trace(
                                point=pt,
                                server=srv,
                                sets_a=sets_a,
                                sets_b=sets_b,
                                games_a=games_a,
                                games_b=games_b,
                                alpha_before=alpha_before,
                                beta_before=beta_before,
                                alpha_after=alpha_after,
                                beta_after=beta_after,
                                observations=observations,
                            ))

                    if tb_winner == "A":
                        games_a += 1
                    else:
                        games_b += 1

                    last_live, last_ci_low, last_ci_high = self._estimate_live_match_prob(
                        alpha_a=alpha_a,
                        beta_a=beta_a,
                        alpha_b=alpha_b,
                        beta_b=beta_b,
                        sets_a=sets_a,
                        sets_b=sets_b,
                        games_a=games_a,
                        games_b=games_b,
                        next_server=current_server,
                        best_of=best_of,
                    )

                    if set_games_log is not None:
                        set_games_log.append({
                            "game": game_num,
                            "type": "tiebreak",
                            "server": current_server,
                            "winner": tb_winner,
                            "score": f"{games_a}-{games_b}",
                            "points": tb_points if timeline_mode == "points" else None,
                            "p_live_a": last_live,
                            "p_live_ci_low": last_ci_low,
                            "p_live_ci_high": last_ci_high,
                            "fatigue_factor": round(fatigue_factor, 3),
                        })
                    break

                fatigue_factor = _match_fatigue_factor(completed_games_total + games_a + games_b)
                p_server = (
                    alpha_a / (alpha_a + beta_a)
                    if current_server == "A"
                    else alpha_b / (alpha_b + beta_b)
                )
                server_won, pts_log = simulate_game(
                    p_server=p_server,
                    rng=rng,
                    track_points=True,
                    fatigue_factor=fatigue_factor,
                )
                for pt in pts_log or []:
                    srv_won = pt["winner"] == "server"
                    if current_server == "A":
                        alpha_before, beta_before = alpha_a, beta_a
                    else:
                        alpha_before, beta_before = alpha_b, beta_b

                    if current_server == "A":
                        alpha_a += 1 if srv_won else 0
                        beta_a += 0 if srv_won else 1
                        alpha_after, beta_after = alpha_a, beta_a
                    else:
                        alpha_b += 1 if srv_won else 0
                        beta_b += 0 if srv_won else 1
                        alpha_after, beta_after = alpha_b, beta_b
                    observations += 1
                    if timeline_mode == "points":
                        pt.update(_build_point_trace(
                            point=pt,
                            server=current_server,
                            sets_a=sets_a,
                            sets_b=sets_b,
                            games_a=games_a,
                            games_b=games_b,
                            alpha_before=alpha_before,
                            beta_before=beta_before,
                            alpha_after=alpha_after,
                            beta_after=beta_after,
                            observations=observations,
                        ))

                if current_server == "A":
                    if server_won:
                        games_a += 1
                    else:
                        games_b += 1
                else:
                    if server_won:
                        games_b += 1
                    else:
                        games_a += 1

                last_live, last_ci_low, last_ci_high = self._estimate_live_match_prob(
                    alpha_a=alpha_a,
                    beta_a=beta_a,
                    alpha_b=alpha_b,
                    beta_b=beta_b,
                    sets_a=sets_a,
                    sets_b=sets_b,
                    games_a=games_a,
                    games_b=games_b,
                    next_server="B" if current_server == "A" else "A",
                    best_of=best_of,
                )

                if set_games_log is not None:
                    game_winner = current_server if server_won else ("B" if current_server == "A" else "A")
                    set_games_log.append({
                        "game": game_num,
                        "type": "game",
                        "server": current_server,
                        "winner": game_winner,
                        "score": f"{games_a}-{games_b}",
                        "points": pts_log if timeline_mode == "points" else None,
                        "p_live_a": last_live,
                        "p_live_ci_low": last_ci_low,
                        "p_live_ci_high": last_ci_high,
                        "fatigue_factor": round(fatigue_factor, 3),
                    })

                if games_a >= 6 and games_a - games_b >= 2:
                    break
                if games_b >= 6 and games_b - games_a >= 2:
                    break

                current_server = "B" if current_server == "A" else "A"

            set_scores.append(f"{games_a}-{games_b}")
            completed_games_total += games_a + games_b
            set_winner = "A" if games_a > games_b else "B"
            if set_winner == "A":
                sets_a += 1
            else:
                sets_b += 1

            if timeline is not None:
                timeline.append({
                    "set": set_num,
                    "score": f"{games_a}-{games_b}",
                    "winner": set_winner,
                    "tiebreak": (games_a, games_b) in {(7, 6), (6, 7)},
                    "games": set_games_log,
                })

            total_games = games_a + games_b
            if total_games % 2 == 1:
                current_server = "B" if current_server == "A" else "A"

        final_live = 1.0 if sets_a > sets_b else 0.0
        params = {
            "proxy_method": "bayes_live_v1+fatigue_v1",
            "surface_base": base_params["surface_base"],
            "delta_max": base_params["delta_max"],
            "strength_a": base_params["strength_a"],
            "p_point_on_serve_a": round(alpha_a / (alpha_a + beta_a), 4),
            "p_point_on_serve_b": round(alpha_b / (alpha_b + beta_b), 4),
            "prior_strength": prior_strength,
            "p_live_a": round(final_live, 4),
            "p_live_ci_low": round(last_ci_low if final_live in (0.0, 1.0) else 0.0, 4),
            "p_live_ci_high": round(last_ci_high if final_live in (0.0, 1.0) else 1.0, 4),
            "uncertainty": round(max(0.0, last_ci_high - last_ci_low), 4),
            "n_observations": observations,
        }

        match_result = {
            "winner": "A" if sets_a > sets_b else "B",
            "sets_a": sets_a,
            "sets_b": sets_b,
            "sets": set_scores,
            "timeline": timeline,
        }
        return match_result, params

    def simulate(
        self,
        player_a: str,
        player_b: str,
        surface: str,
        model: str = DEFAULT_MODEL_ID,
        as_of: Optional[str] = None,
        best_of: int = 3,
        seed: Optional[int] = None,
        first_server: Literal["A", "B", "random"] = "random",
        timeline_mode: Literal["none", "games", "points"] = "games",
        engine_mode: Literal["proxy_v0", "bayes_live_v1"] = "proxy_v0",
        p_a_override: Optional[float] = None,
    ) -> dict:
        """
        Simulate a tennis match.
        
        Args:
            player_a, player_b: Player names
            surface: "Hard", "Clay", "Grass"
            model: Model variant for match probability
            as_of: Date for prediction (None = latest)
            best_of: 3 or 5 sets
            seed: Random seed for reproducibility
            first_server: Who serves first
            timeline_mode: Detail level of timeline
            p_a_override: Optional user-defined adjusted win probability (from Coach Mode)
            
        Returns:
            Complete simulation result with params and timeline
        """
        warnings = []
        canonical_model = normalize_model_id(model, scope="simulate")

        if player_a.strip().lower() == player_b.strip().lower():
            raise ValueError("player_a and player_b must be different")

        as_of_used = self._resolve_as_of(as_of, warnings)

        if p_a_override is not None:
            p_a = _clamp(
                float(p_a_override),
                MIN_PROBABILITY_OVERRIDE,
                MAX_PROBABILITY_OVERRIDE,
            )
            p_b = 1.0 - p_a
            warnings.append(f"What-If: Usando probabilidad de victoria personalizada ({p_a*100:.1f}%) del modo entrenador.")
        else:
            predictor = self._get_predictor(canonical_model)
            try:
                p_a, p_b = self._predict_pair_cached(
                    predictor=predictor,
                    model_id=canonical_model,
                    player_a=player_a,
                    player_b=player_b,
                    surface=surface,
                    as_of=as_of_used,
                )
            except ValueError as e:
                raise ValueError(str(e))

        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        rng = random.Random(seed)

        if engine_mode == "proxy_v0":
            # Legacy simulation mode with static serve probabilities.
            point_params = compute_point_probabilities(p_a, surface)
            point_params["proxy_method"] = f"{point_params['proxy_method']}+clutch_v1+fatigue_v1"
            match_result = simulate_match(
                p_serve_a=point_params["p_point_on_serve_a"],
                p_serve_b=point_params["p_point_on_serve_b"],
                rng=rng,
                best_of=best_of,
                first_server=first_server,
                timeline_mode=timeline_mode,
            )
        elif engine_mode == "bayes_live_v1":
            match_result, point_params = self._simulate_bayes_live(
                p_match_a=p_a,
                surface=surface,
                rng=rng,
                best_of=best_of,
                first_server=first_server,
                timeline_mode=timeline_mode,
            )
        else:
            raise ValueError(f"engine_mode '{engine_mode}' no soportado")

        return {
            "player_a": player_a,
            "player_b": player_b,
            "surface": surface,
            "model": canonical_model,
            "as_of_used": as_of_used,
            "p_a": round(p_a, 4),
            "p_b": round(p_b, 4),
            "seed_used": seed,
            "warnings": warnings,
            "params": point_params,
            "result": {
                "winner": match_result["winner"],
                "sets": match_result["sets"],
                "sets_a": match_result["sets_a"],
                "sets_b": match_result["sets_b"],
            },
            "timeline": match_result["timeline"],
        }


# Singleton instance
_service: Optional[SimulateService] = None


def get_simulate_service() -> SimulateService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = SimulateService()
    return _service
