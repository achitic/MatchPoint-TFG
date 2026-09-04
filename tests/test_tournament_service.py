# tests/test_tournament_service.py
"""
Unit tests for TournamentService.

Covers:
- El campeón es uno de los jugadores iniciales
- El número de rondas es correcto para el tamaño del torneo
- Los partidos tienen estructura correcta
- Reproducibilidad con seed
- get_tournaments devuelve una lista con estructura correcta
"""
import math
import pytest
from conftest import SURFACE, AS_OF

PLAYERS_8 = [
    "Carlos Alcaraz", "Jannik Sinner", "Novak Djokovic", "Daniil Medvedev",
    "Alexander Zverev", "Holger Rune", "Andrey Rublev", "Stefanos Tsitsipas",
]


class TestTournamentServiceBasic:
    """Tests básicos de simulación de torneo."""

    def test_champion_is_one_of_players(self, tournament_service):
        """El campeón debe ser uno de los jugadores del torneo."""
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
        )
        assert result["champion"] in PLAYERS_8, \
            f"Campeón '{result['champion']}' no está en la lista de jugadores"

    def test_correct_number_of_rounds(self, tournament_service):
        """El número de rondas debe ser log2(size)."""
        size = 8
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=size,
            surface=SURFACE,
            seed=42,
        )
        expected_rounds = int(math.log2(size))
        assert len(result["rounds"]) == expected_rounds, \
            f"Esperado {expected_rounds} rondas, obtenido {len(result['rounds'])}"

    def test_result_has_required_fields(self, tournament_service):
        """El resultado debe contener los campos requeridos."""
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
        )
        required = ["champion", "rounds", "standings", "tournament", "size", "best_of"]
        for field in required:
            assert field in result, f"Falta campo: {field}"

    def test_standings_has_all_players(self, tournament_service):
        """standings debe incluir a todos los jugadores del torneo."""
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
        )
        for player in PLAYERS_8:
            assert player in result["standings"], \
                f"Jugador '{player}' no está en standings"

    def test_size_32_is_out_of_scope(self, tournament_service):
        """La versión entregada admite únicamente cuadros de 8 o 16 jugadores."""
        with pytest.raises(ValueError, match="8 or 16"):
            tournament_service.simulate_tournament(
                players=PLAYERS_8 * 4,
                size=32,
                surface=SURFACE,
                seed=42,
            )


class TestTournamentServiceMatches:
    """Tests de estructura de partidos."""

    def test_first_round_has_correct_matches(self, tournament_service):
        """La primera ronda debe tener size/2 partidos."""
        size = 8
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=size,
            surface=SURFACE,
            seed=42,
        )
        first_round_matches = len(result["rounds"][0]["matches"])
        expected = size // 2
        assert first_round_matches == expected, \
            f"Ronda 1: esperado {expected} partidos, obtenido {first_round_matches}"

    def test_match_probabilities_valid(self, tournament_service):
        """Las probabilidades de cada partido deben estar en [0, 1]."""
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
        )
        for rnd in result["rounds"]:
            for match in rnd["matches"]:
                assert 0.0 <= match["p_a"] <= 1.0, f"p_a inválido: {match['p_a']}"
                assert 0.0 <= match["p_b"] <= 1.0, f"p_b inválido: {match['p_b']}"

    def test_match_winner_is_valid(self, tournament_service):
        """El ganador de cada partido debe ser 'A' o 'B'."""
        result = tournament_service.simulate_tournament(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
        )
        for rnd in result["rounds"]:
            for match in rnd["matches"]:
                assert match["result"]["winner"] in ("A", "B")


class TestTournamentServiceSeed:
    """Tests de reproducibilidad."""

    def test_same_seed_produces_same_champion(self, tournament_service):
        """El mismo seed debe producir el mismo campeón."""
        kwargs = dict(players=PLAYERS_8, size=8, surface=SURFACE, seed=777)
        r1 = tournament_service.simulate_tournament(**kwargs)
        r2 = tournament_service.simulate_tournament(**kwargs)
        assert r1["champion"] == r2["champion"], \
            f"Champions differ: {r1['champion']} vs {r2['champion']}"

    def test_different_seeds_vary(self, tournament_service):
        """Seeds diferentes deben producir champions variados en múltiples runs."""
        champions = set()
        for seed in range(10):  # 10 seeds es suficiente para verificar variabilidad
            r = tournament_service.simulate_tournament(
                players=PLAYERS_8, size=8, surface=SURFACE, seed=seed,
            )
            champions.add(r["champion"])
        assert len(champions) > 1, "Todos los seeds produjeron el mismo campeón"


class TestTournamentMonteCarlo:
    """Tests de Monte Carlo de torneo."""

    def test_monte_carlo_returns_odds_for_all_players(self, tournament_service):
        result = tournament_service.simulate_monte_carlo(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=42,
            n_simulations=5,
        )
        assert result["n_simulations"] == 5
        assert len(result["odds"]) == len(PLAYERS_8)
        assert sum(item["wins"] for item in result["odds"]) == 5
        for item in result["odds"]:
            assert item["player"] in PLAYERS_8
            assert 0.0 <= item["win_pct"] <= 100.0
            assert 0.0 <= item["final_pct"] <= 100.0

    def test_monte_carlo_same_seed_is_reproducible(self, tournament_service):
        kwargs = dict(
            players=PLAYERS_8,
            size=8,
            surface=SURFACE,
            seed=123,
            n_simulations=5,
        )
        r1 = tournament_service.simulate_monte_carlo(**kwargs)
        r2 = tournament_service.simulate_monte_carlo(**kwargs)
        assert r1["odds"] == r2["odds"]


class TestTournamentServiceCatalog:
    """Tests del catálogo de torneos."""

    def test_get_tournaments_returns_list(self, tournament_service):
        """get_tournaments debe devolver una lista."""
        tournaments = tournament_service.get_tournaments(limit=10)
        assert isinstance(tournaments, list)

    def test_tournament_has_required_fields(self, tournament_service):
        """Cada torneo debe tener los campos requeridos."""
        tournaments = tournament_service.get_tournaments(limit=5)
        if not tournaments:
            pytest.skip("No hay torneos en el catálogo")
        for t in tournaments:
            for field in ["id", "name", "surface", "date", "level", "year"]:
                assert field in t, f"Falta campo '{field}' en torneo: {t}"
