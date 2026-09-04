# tests/test_simulate_service.py
"""
Unit tests for SimulateService.

Covers:
- Resultado tiene estructura correcta
- Reproducibilidad con seed
- Seeds diferentes → resultados distintos
- Jugadores iguales → ValueError
- best_of 3 y 5
- Modos de timeline: none, games, points
"""
import pytest
from conftest import PLAYER_A, PLAYER_B, SURFACE, AS_OF
from backend.services.simulate_service import SimulateService


class TestSimulateServiceBasic:
    """Tests básicos de simulación."""

    def test_simulation_returns_required_fields(self, simulate_service):
        """La simulación debe devolver todos los campos requeridos."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
        )
        required = ["player_a", "player_b", "surface", "model", "as_of_used",
                    "p_a", "p_b", "seed_used", "params", "result"]
        for field in required:
            assert field in result, f"Falta campo: {field}"

    def test_winner_is_valid(self, simulate_service):
        """El ganador debe ser 'A' o 'B'."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
        )
        assert result["result"]["winner"] in ("A", "B")

    def test_probabilities_in_range(self, simulate_service):
        """p_a y p_b deben estar en [0, 1]."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=1,
        )
        assert 0.0 <= result["p_a"] <= 1.0
        assert 0.0 <= result["p_b"] <= 1.0

    def test_result_has_sets(self, simulate_service):
        """El resultado debe incluir al menos 2 sets."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
        )
        sets = result["result"]["sets"]
        assert isinstance(sets, list)
        assert len(sets) >= 2

    def test_same_player_raises_error(self, simulate_service):
        """Usar el mismo jugador debe lanzar ValueError."""
        with pytest.raises(ValueError):
            simulate_service.simulate(
                player_a=PLAYER_A,
                player_b=PLAYER_A,
                surface=SURFACE,
            )


class TestSimulateServiceSeed:
    """Tests de reproducibilidad con semilla."""

    def test_same_seed_produces_same_result(self, simulate_service):
        """El mismo seed debe producir resultados idénticos."""
        kwargs = dict(player_a=PLAYER_A, player_b=PLAYER_B, surface=SURFACE, seed=99999)
        r1 = simulate_service.simulate(**kwargs)
        r2 = simulate_service.simulate(**kwargs)
        assert r1["result"] == r2["result"], "Resultados difieren con el mismo seed"

    def test_different_seeds_produce_variety(self, simulate_service):
        """Seeds diferentes deben producir resultados variados."""
        results = []
        for seed in range(20):
            r = simulate_service.simulate(
                player_a=PLAYER_A,
                player_b=PLAYER_B,
                surface=SURFACE,
                seed=seed,
            )
            results.append(tuple(r["result"]["sets"]))
        unique = len(set(results))
        assert unique > 1, f"Todos los seeds produjeron el mismo resultado: {results[0]}"

    def test_seed_used_matches_requested(self, simulate_service):
        """El seed_used del resultado debe coincidir con el seed solicitado."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=12345,
        )
        assert result["seed_used"] == 12345


class TestSimulateServiceBestOf:
    """Tests de formato best_of."""

    def test_best_of_3_max_3_sets(self, simulate_service):
        """best_of=3 no puede tener más de 3 sets."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            best_of=3,
            seed=42,
        )
        sets_count = len(result["result"]["sets"])
        assert sets_count <= 3, f"best_of=3 devolvió {sets_count} sets"

    def test_best_of_5_max_5_sets(self, simulate_service):
        """best_of=5 no puede tener más de 5 sets."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            best_of=5,
            seed=42,
        )
        sets_count = len(result["result"]["sets"])
        assert sets_count <= 5, f"best_of=5 devolvió {sets_count} sets"


class TestSimulateServiceTimeline:
    """Tests de modos de timeline."""

    def test_timeline_none(self, simulate_service):
        """timeline_mode='none' debe devolver timeline=None."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
            timeline_mode="none",
        )
        assert result.get("timeline") is None

    def test_timeline_games(self, simulate_service):
        """timeline_mode='games' debe devolver una lista de sets con games."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
            timeline_mode="games",
        )
        timeline = result.get("timeline")
        assert timeline is not None
        assert isinstance(timeline, list)
        assert len(timeline) >= 2


class TestSimulateServiceBayes:
    """Tests del modo bayes_live_v1."""

    def test_bayes_mode_returns_live_fields(self, simulate_service):
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
            timeline_mode="games",
            engine_mode="bayes_live_v1",
        )
        params = result["params"]
        assert params["proxy_method"] == "bayes_live_v1+fatigue_v1"
        assert params["p_live_a"] in (0.0, 1.0)
        assert 0.0 <= params["p_live_ci_low"] <= 1.0
        assert 0.0 <= params["p_live_ci_high"] <= 1.0
        assert params["n_observations"] > 0

    def test_bayes_mode_is_seed_reproducible(self, simulate_service):
        kwargs = dict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=2026,
            engine_mode="bayes_live_v1",
        )
        r1 = simulate_service.simulate(**kwargs)
        r2 = simulate_service.simulate(**kwargs)
        assert r1["result"] == r2["result"]

    def test_bayes_points_timeline_exposes_point_trace(self, simulate_service):
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=42,
            timeline_mode="points",
            engine_mode="bayes_live_v1",
        )
        first_point = result["timeline"][0]["games"][0]["points"][0]
        assert first_point["server"] in ("A", "B")
        assert 0.0 <= first_point["p_server_bayes_before"] <= 1.0
        assert 0.0 <= first_point["p_server_bayes_after"] <= 1.0
        assert "p_server_bayes_delta" in first_point
        assert first_point["observations_after"] >= 1
        assert len(first_point["trace_factors"]) >= 4

    def test_seven_five_set_is_not_marked_as_tiebreak(self, simulate_service):
        """Regression: a normal 7-5 set must never be labelled as a tie-break."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=3,
            timeline_mode="games",
            engine_mode="bayes_live_v1",
            p_a_override=0.61,
        )

        seven_five_sets = [
            set_event
            for set_event in result["timeline"]
            if set_event["score"] in {"7-5", "5-7"}
        ]
        assert seven_five_sets, "La semilla de regresión debe producir un set 7-5/5-7"
        assert all(set_event["tiebreak"] is False for set_event in seven_five_sets)
        assert all(set_event["games"][-1]["type"] == "game" for set_event in seven_five_sets)

    @pytest.mark.parametrize("seed", range(20))
    def test_tiebreak_metadata_matches_set_score(self, simulate_service, seed):
        """The set flag and final event must agree with a 7-6/6-7 score."""
        result = simulate_service.simulate(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            seed=seed,
            timeline_mode="games",
            engine_mode="bayes_live_v1",
            p_a_override=0.61,
        )

        for set_event in result["timeline"]:
            expected = set_event["score"] in {"7-6", "6-7"}
            assert set_event["tiebreak"] is expected
            assert (set_event["games"][-1]["type"] == "tiebreak") is expected


class TestInPlayStateLifecycle:
    def test_expired_states_are_pruned(self):
        now = [100.0]
        service = SimulateService(clock=lambda: now[0])
        service._inplay_ttl_seconds = 10
        service._inplay_states = {
            "expired": {"last_activity": 89.9},
            "active": {"last_activity": 95.0},
        }

        service._prune_inplay_states()

        assert set(service._inplay_states) == {"active"}

    def test_oldest_states_are_evicted_at_capacity(self):
        service = SimulateService(clock=lambda: 100.0)
        service._inplay_ttl_seconds = 1000
        service._inplay_max_states = 2
        service._inplay_states = {
            "oldest": {"last_activity": 10.0},
            "newer": {"last_activity": 20.0},
        }

        service._reserve_inplay_slot(100.0)

        assert set(service._inplay_states) == {"newer"}
