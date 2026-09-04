"""
Service layer for tournaments and model catalog.
"""
from __future__ import annotations

import logging
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, Literal
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from matchpoint import MatchPredictor
from matchpoint.sim_engine import simulate_match as sim_match_engine
from matchpoint.model_registry import (
    DEFAULT_MODEL_ID,
    get_models_catalog as get_models_catalog_from_registry,
    normalize_model_id,
)
from backend.settings import MATCHES_CLEAN_PATH, PROCESSED_DIR
from backend.services.inference_utils import predict_pair_probabilities


logger = logging.getLogger(__name__)


# ========== MODEL CATALOG ==========


def get_models_catalog() -> list[dict]:
    """Return the catalog of available models with Spanish labels."""
    return get_models_catalog_from_registry(scope="tournament")


# ========== SURFACE PARAMS FOR POINT PROXY ==========

SURFACE_PARAMS = {
    "Hard": {"base": 0.62, "delta_max": 0.06},
    "Clay": {"base": 0.60, "delta_max": 0.05},
    "Grass": {"base": 0.64, "delta_max": 0.07},
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _logit(p: float) -> float:
    p_clamped = _clamp(p, 0.02, 0.98)
    return math.log(p_clamped / (1.0 - p_clamped))


def _compute_point_probs(p_match_a: float, surface: str) -> dict:
    """Convert match probability to point-level serve probabilities."""
    params = SURFACE_PARAMS.get(surface, SURFACE_PARAMS["Hard"])
    base = params["base"]
    delta_max = params["delta_max"]
    
    strength = _logit(p_match_a)
    delta = delta_max * math.tanh(strength / 2.0)
    
    p_serve_a = _clamp(base + delta, 0.50, 0.75)
    p_serve_b = _clamp(base - delta, 0.50, 0.75)
    
    return {
        "p_point_on_serve_a": round(p_serve_a, 4),
        "p_point_on_serve_b": round(p_serve_b, 4),
    }


# ========== TOURNAMENT SERVICE ==========

class TournamentService:
    """Service for tournament catalog and simulation."""

    def __init__(self):
        self._tournaments_cache: Optional[pd.DataFrame] = None
        self._players_cache: Optional[list[str]] = None
        self._predictors: dict[str, MatchPredictor] = {}
        self._elo_cache: Optional[pd.DataFrame] = None
        self._probability_cache: dict[tuple[str, str, str, str, str | None], tuple[float, float]] = {}

    def _load_tournaments(self) -> pd.DataFrame:
        """Load unique tournaments from matches dataset."""
        if self._tournaments_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            
            cols = ['tourney_id', 'tourney_name', 'surface', 'tourney_date', 'tourney_level']
            tournaments = df[cols].drop_duplicates()
            
            tournaments['tourney_date'] = pd.to_datetime(tournaments['tourney_date'])
            
            tournaments['year'] = tournaments['tourney_date'].dt.year
            
            tournaments = tournaments.sort_values('tourney_date', ascending=False)
            
            self._tournaments_cache = tournaments
        
        return self._tournaments_cache

    def get_tournaments(
        self,
        year: Optional[int] = None,
        surface: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get list of real tournaments with optional filters."""
        df = self._load_tournaments()
        
        if year is not None:
            df = df[df['year'] == year]
        if surface is not None:
            df = df[df['surface'] == surface]
        if level is not None:
            df = df[df['tourney_level'] == level]
        
        df = df.head(limit)

        result = []
        for _, row in df.iterrows():
            result.append({
                "id": row['tourney_id'],
                "name": row['tourney_name'],
                "surface": row['surface'],
                "date": row['tourney_date'].strftime('%Y-%m-%d'),
                "level": row['tourney_level'],
                "year": int(row['year']),
            })
        
        return result

    def get_tournament_by_id(self, tournament_id: str) -> Optional[dict]:
        """Get a specific tournament by ID."""
        df = self._load_tournaments()
        match = df[df['tourney_id'] == tournament_id]
        
        if match.empty:
            return None
        
        row = match.iloc[0]
        return {
            "id": row['tourney_id'],
            "name": row['tourney_name'],
            "surface": row['surface'],
            "date": row['tourney_date'].strftime('%Y-%m-%d'),
            "level": row['tourney_level'],
            "year": int(row['year']),
        }

    def get_players(self) -> list[str]:
        """Get sorted list of unique player names."""
        if self._players_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            winners = set(df["winner_name"].dropna().unique())
            losers = set(df["loser_name"].dropna().unique())
            self._players_cache = sorted(winners | losers)
        return self._players_cache

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

    def _load_elo_data(self) -> Optional[pd.DataFrame]:
        """Load latest ELO ratings if available."""
        if self._elo_cache is not None:
            return self._elo_cache
        
        elo_path = PROCESSED_DIR / "elo_latest.parquet"
        if elo_path.exists():
            try:
                self._elo_cache = pd.read_parquet(elo_path)
                return self._elo_cache
            except Exception as exc:
                logger.warning("Could not load %s: %s", elo_path, exc)
        
        elo_csv = PROCESSED_DIR / "elo_latest.csv"
        if elo_csv.exists():
            try:
                self._elo_cache = pd.read_csv(elo_csv)
                return self._elo_cache
            except Exception as exc:
                logger.warning("Could not load %s: %s", elo_csv, exc)
        
        return None

    def _seed_players_by_elo(self, players: list[str], rng: random.Random) -> list[str]:
        """Order players by ELO rating (best ELO first), with random tiebreaking."""
        elo_df = self._load_elo_data()
        
        if elo_df is None:
            shuffled = players.copy()
            rng.shuffle(shuffled)
            return shuffled
        
        player_elos = []
        for p in players:
            match = elo_df[elo_df['player'] == p] if 'player' in elo_df.columns else pd.DataFrame()
            if not match.empty:
                elo = match.iloc[0].get('elo_global', match.iloc[0].get('elo', 1500))
            else:
                elo = 1500  # Default
            player_elos.append((p, elo, rng.random()))
        
        player_elos.sort(key=lambda x: (-x[1], x[2]))
        
        return [p[0] for p in player_elos]

    def simulate_tournament(
        self,
        players: list[str],
        size: int,
        surface: str,
        model: str = DEFAULT_MODEL_ID,
        as_of: Optional[str] = None,
        best_of: int = 3,
        seed: Optional[int] = None,
        timeline_mode: Literal["none", "games"] = "none",
        seeding: Literal["elo", "random"] = "random",
        tournament_id: Optional[str] = None,
    ) -> dict:
        """
        Simulate a single-elimination tournament.
        
        Args:
            players: List of player names (8 or 16)
            size: Tournament size (must match len(players))
            surface: Hard, Clay, or Grass
            model: Model variant for predictions
            as_of: Date for predictions
            best_of: 3 or 5 sets per match
            seed: Random seed for reproducibility
            timeline_mode: none or games
            seeding: elo (by ELO) or random
            tournament_id: Optional real tournament ID
        """
        warnings = []
        canonical_model = normalize_model_id(model, scope="tournament")
        
        if size not in {8, 16}:
            raise ValueError("Tournament size must be 8 or 16")
        
        if len(players) != size:
            raise ValueError(f"Expected {size} players, got {len(players)}")
        
        if len(set(players)) != len(players):
            raise ValueError("Duplicate players in list")
        
        surface = surface.strip().title()
        if surface not in {"Hard", "Clay", "Grass"}:
            raise ValueError("Surface must be Hard, Clay, or Grass")
        
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        rng = random.Random(seed)
        
        tournament_meta = None
        if tournament_id:
            tournament_meta = self.get_tournament_by_id(tournament_id)
            if tournament_meta is None:
                warnings.append(f"Tournament ID '{tournament_id}' not found in catalog")
        
        if tournament_meta is None:
            tournament_meta = {
                "id": None,
                "name": "Torneo personalizado",
                "surface": surface,
                "date": as_of or "latest",
                "level": "Custom",
                "year": None,
            }
        
        predictor = self._get_predictor(canonical_model)
        if as_of is None:
            # Use latest date from model's data
            as_of_used = None  # Will use model's default
        else:
            as_of_used = as_of
        
        if seeding == "elo":
            elo_df = self._load_elo_data()
            if elo_df is None:
                warnings.append("ELO data not available, using random seeding")
                seeded_players = players.copy()
                rng.shuffle(seeded_players)
            else:
                seeded_players = self._seed_players_by_elo(players, rng)
        else:
            seeded_players = players.copy()
            rng.shuffle(seeded_players)
        
        bracket = seeded_players.copy()
        rounds = []
        round_names = self._get_round_names(size)
        
        standings = {p: {"wins": 0, "losses": 0} for p in players}
        
        round_num = 0
        while len(bracket) > 1:
            round_matches = []
            next_bracket = []
            
            for i in range(0, len(bracket), 2):
                player_a = bracket[i]
                player_b = bracket[i + 1]
                
                try:
                    p_a, p_b = self._predict_pair_cached(
                        predictor=predictor,
                        model_id=canonical_model,
                        player_a=player_a,
                        player_b=player_b,
                        surface=surface,
                        as_of=as_of_used,
                    )
                except Exception as e:
                    warnings.append(f"Prediction error for {player_a} vs {player_b}: {str(e)[:50]}")
                    p_a = 0.5  # Fallback to 50/50
                    p_b = 0.5
                
                point_probs = _compute_point_probs(p_a, surface)

                match_result = sim_match_engine(
                    p_serve_a=point_probs["p_point_on_serve_a"],
                    p_serve_b=point_probs["p_point_on_serve_b"],
                    rng=rng,
                    best_of=best_of,
                    first_server="random",
                    timeline_mode=timeline_mode,
                )
                
                winner = player_a if match_result["winner"] == "A" else player_b
                loser = player_b if winner == player_a else player_a
                
                standings[winner]["wins"] += 1
                standings[loser]["losses"] += 1
                
                match_record = {
                    "player_a": player_a,
                    "player_b": player_b,
                    "p_a": round(p_a, 4),
                    "p_b": round(p_b, 4),
                    "params": point_probs,
                    "result": {
                        "winner": match_result["winner"],
                        "winner_name": winner,
                        "sets": match_result["sets"],
                        "sets_a": match_result["sets_a"],
                        "sets_b": match_result["sets_b"],
                    },
                }
                
                if timeline_mode == "games" and match_result.get("timeline"):
                    match_record["timeline"] = match_result["timeline"]
                
                round_matches.append(match_record)
                next_bracket.append(winner)
            
            rounds.append({
                "round": round_num + 1,
                "name": round_names[round_num] if round_num < len(round_names) else f"Round {round_num + 1}",
                "matches": round_matches,
            })
            
            bracket = next_bracket
            round_num += 1
        
        champion = bracket[0]
        
        return {
            "tournament": tournament_meta,
            "surface": surface,
            "model": canonical_model,
            "as_of_used": as_of_used or "latest",
            "seed_used": seed,
            "seeding": seeding,
            "size": size,
            "best_of": best_of,
            "warnings": warnings,
            "bracket_order": seeded_players,
            "rounds": rounds,
            "champion": champion,
            "standings": standings,
        }

    def simulate_monte_carlo(
        self,
        players: list[str],
        size: int,
        surface: str,
        model: str = DEFAULT_MODEL_ID,
        as_of: Optional[str] = None,
        best_of: int = 3,
        seed: Optional[int] = None,
        seeding: Literal["elo", "random"] = "random",
        tournament_id: Optional[str] = None,
        n_simulations: int = 200,
    ) -> dict:
        """
        Run repeated tournament simulations and aggregate championship odds.

        Timeline is forced to "none" because Monte Carlo needs aggregate outcomes,
        not per-game traces.
        """
        if n_simulations < 1 or n_simulations > 1000:
            raise ValueError("n_simulations must be between 1 and 1000")

        base_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        champion_counts: Counter[str] = Counter()
        round_reached_counts: dict[str, Counter[str]] = defaultdict(Counter)
        round_appearance_counts: dict[str, Counter[str]] = defaultdict(Counter)
        warnings_counter: Counter[str] = Counter()
        round_names = self._get_round_names(size)

        sample_meta = None
        as_of_used = "latest"
        canonical_model = normalize_model_id(model, scope="tournament")

        for i in range(n_simulations):
            result = self.simulate_tournament(
                players=players,
                size=size,
                surface=surface,
                model=canonical_model,
                as_of=as_of,
                best_of=best_of,
                seed=base_seed + i,
                timeline_mode="none",
                seeding=seeding,
                tournament_id=tournament_id,
            )

            if sample_meta is None:
                sample_meta = result["tournament"]
                as_of_used = result["as_of_used"]

            champion = result["champion"]
            champion_counts[champion] += 1

            for warning in result.get("warnings", []):
                warnings_counter[warning] += 1

            for round_data in result["rounds"]:
                round_name = round_data["name"]
                for match in round_data["matches"]:
                    round_appearance_counts[match["player_a"]][round_name] += 1
                    round_appearance_counts[match["player_b"]][round_name] += 1

            for player, standing in result["standings"].items():
                wins = int(standing["wins"])
                reached_label = "Campeon" if wins >= len(round_names) else round_names[wins]
                round_reached_counts[player][reached_label] += 1

        final_round = round_names[-1] if round_names else "Final"
        semifinal_round = round_names[-2] if len(round_names) >= 2 else final_round

        odds = []
        for player in players:
            wins = champion_counts[player]
            odds.append({
                "player": player,
                "wins": int(wins),
                "win_pct": round(wins / n_simulations * 100.0, 1),
                "final_pct": round(round_appearance_counts[player][final_round] / n_simulations * 100.0, 1),
                "semifinal_pct": round(round_appearance_counts[player][semifinal_round] / n_simulations * 100.0, 1),
                "round_reached_counts": dict(round_reached_counts[player]),
                "round_appearance_counts": dict(round_appearance_counts[player]),
            })

        odds.sort(key=lambda item: (-item["wins"], item["player"]))

        return {
            "n_simulations": n_simulations,
            "seed_start": base_seed,
            "tournament": sample_meta or {
                "id": None,
                "name": "Torneo personalizado",
                "surface": surface,
                "date": as_of or "latest",
                "level": "Custom",
                "year": None,
            },
            "surface": surface.strip().title(),
            "model": canonical_model,
            "as_of_used": as_of_used,
            "seeding": seeding,
            "size": size,
            "best_of": best_of,
            "odds": odds,
            "warnings": [f"{text} ({count} simulaciones)" for text, count in warnings_counter.most_common()],
        }

    def _get_round_names(self, size: int) -> list[str]:
        """Get round names for tournament size."""
        if size == 8:
            return ["Cuartos de Final", "Semifinal", "Final"]
        elif size == 16:
            return ["Octavos de Final", "Cuartos de Final", "Semifinal", "Final"]
        else:
            return []


# Singleton instance
_service: Optional[TournamentService] = None


def get_tournament_service() -> TournamentService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = TournamentService()
    return _service

