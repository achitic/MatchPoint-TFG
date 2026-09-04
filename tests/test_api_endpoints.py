# tests/test_api_endpoints.py
"""
Integration tests for FastAPI endpoints using TestClient.

Covers:
- GET /health
- GET /players
- GET /models
- GET /surfaces
- POST /predict — happy path + error cases
- POST /simulate_match — happy path + error cases
- GET /tournaments
- POST /tournament/simulate
"""
import pytest


class TestHealthEndpoint:
    """Tests del endpoint /health."""

    def test_health_returns_ok(self, client):
        """GET /health debe devolver status=ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPlayersEndpoint:
    """Tests del endpoint /players."""

    def test_players_returns_200(self, client):
        """GET /players debe devolver 200."""
        response = client.get("/players")
        assert response.status_code == 200

    def test_players_response_structure(self, client):
        """La respuesta debe tener 'players' y 'count'."""
        response = client.get("/players")
        data = response.json()
        assert "players" in data
        assert "count" in data
        assert isinstance(data["players"], list)
        assert data["count"] == len(data["players"])

    def test_players_list_is_nonempty(self, client):
        """Debe haber al menos un jugador."""
        response = client.get("/players")
        data = response.json()
        assert len(data["players"]) > 0


class TestPlayerSearchEndpoint:
    """Tests del endpoint /players/search."""

    def test_player_search_returns_matches(self, client):
        response = client.get("/players/search?q=Alcaraz&limit=5")
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert data["query"] == "Alcaraz"
        assert data["count"] == len(data["results"])
        assert "Carlos Alcaraz" in data["results"]

    def test_player_search_limit_is_respected(self, client):
        response = client.get("/players/search?q=a&limit=3")
        assert response.status_code == 200
        assert len(response.json()["results"]) <= 3


class TestPlayerProfileEndpoints:
    """Tests de endpoints de perfil de jugador."""

    PLAYER = "Carlos Alcaraz"

    def test_player_profile_structure(self, client):
        response = client.get(f"/player/{self.PLAYER}/profile")
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert data["name"] == self.PLAYER
        assert "elo_by_surface" in data
        assert "record" in data
        assert "current_streak" in data
        assert data["record"]["wins"] + data["record"]["losses"] > 0

    def test_player_history_structure(self, client):
        response = client.get(f"/player/{self.PLAYER}/history?limit=5")
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert data["player"] == self.PLAYER
        assert len(data["matches"]) <= 5
        assert isinstance(data["elo_evolution"], list)
        if data["matches"]:
            match = data["matches"][0]
            for field in ["date", "tournament", "surface", "opponent", "result", "score"]:
                assert field in match

    def test_player_serve_stats_structure(self, client):
        response = client.get(f"/player/{self.PLAYER}/serve_stats?surface=Hard")
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert data["player"] == self.PLAYER
        assert data["surface"] == "Hard"
        assert data["matches_counted"] >= 0
        for field in ["first_serve_pct", "ace_rate", "bp_saved_pct", "return_points_won_pct"]:
            assert field in data

    def test_unknown_player_returns_404(self, client):
        """Un jugador desconocido debe devolver 404."""
        response = client.get("/player/No%20Existe/profile")
        assert response.status_code == 404


class TestModelsEndpoint:
    """Tests del endpoint /models."""

    def test_models_returns_200(self, client):
        """GET /models debe devolver 200."""
        response = client.get("/models")
        assert response.status_code == 200

    def test_models_response_has_models_list(self, client):
        """La respuesta debe tener una lista 'models'."""
        response = client.get("/models")
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_each_model_has_required_fields(self, client):
        """Cada modelo debe tener id, label_es y description_es."""
        response = client.get("/models")
        models = response.json()["models"]
        for model in models:
            assert "id" in model
            assert "label_es" in model
            assert "description_es" in model


class TestSurfacesEndpoint:
    """Tests del endpoint /surfaces."""

    def test_surfaces_returns_200(self, client):
        """GET /surfaces debe devolver 200."""
        response = client.get("/surfaces")
        assert response.status_code == 200

    def test_surfaces_includes_standard_surfaces(self, client):
        """Debe incluir Hard, Clay y Grass."""
        response = client.get("/surfaces")
        surfaces = response.json()["surfaces"]
        for s in ["Hard", "Clay", "Grass"]:
            assert s in surfaces, f"Superficie '{s}' no encontrada"


class TestPredictEndpoint:
    """Tests del endpoint POST /predict."""

    VALID_PAYLOAD = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "as_of": "2024-01-01",
        "model": "calibrated_logreg",
        "debug": False,
    }

    def test_predict_returns_200(self, client):
        """POST /predict con datos válidos debe devolver 200."""
        response = client.post("/predict", json=self.VALID_PAYLOAD)
        assert response.status_code == 200, f"Error: {response.text}"

    def test_predict_probabilities_in_range(self, client):
        """p_a y p_b deben estar en [0, 1]."""
        response = client.post("/predict", json=self.VALID_PAYLOAD)
        data = response.json()
        assert 0.0 <= data["p_a"] <= 1.0
        assert 0.0 <= data["p_b"] <= 1.0

    def test_predict_probabilities_sum_to_one(self, client):
        """p_a + p_b debe ser ≈ 1."""
        response = client.post("/predict", json=self.VALID_PAYLOAD)
        data = response.json()
        assert abs(data["p_a"] + data["p_b"] - 1.0) < 0.01

    def test_predict_same_player_returns_400(self, client):
        """Mismo jugador A y B debe devolver 400."""
        payload = {**self.VALID_PAYLOAD, "player_b": self.VALID_PAYLOAD["player_a"]}
        response = client.post("/predict", json=payload)
        assert response.status_code == 400

    def test_predict_with_debug_returns_debug_info(self, client):
        """debug=True debe devolver información de debug."""
        payload = {**self.VALID_PAYLOAD, "debug": True}
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["debug"] is not None
        assert "features_a" in data["debug"]

    @pytest.mark.parametrize("model", ["baseline_logreg", "surface_logreg", "calibrated_logreg", "stacking_ensemble"])
    def test_predict_all_models(self, client, model):
        """Todos los modelos de regresión logística deben funcionar."""
        payload = {**self.VALID_PAYLOAD, "model": model}
        response = client.post("/predict", json=payload)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        ("legacy_model", "canonical_model"),
        [
            ("core", "baseline_logreg"),
            ("core_elop", "surface_logreg"),
            ("core_calibrated", "calibrated_logreg"),
            ("stacking", "stacking_ensemble"),
        ],
    )
    def test_predict_legacy_aliases(self, client, legacy_model, canonical_model):
        payload = {**self.VALID_PAYLOAD, "model": legacy_model}
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        assert response.json()["model"] == canonical_model


class TestSimulateMatchEndpoint:
    """Tests del endpoint POST /simulate_match."""

    VALID_PAYLOAD = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "as_of": "2024-01-01",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 42,
        "first_server": "random",
        "timeline_mode": "games",
    }

    def test_simulate_returns_200(self, client):
        """POST /simulate_match con datos válidos debe devolver 200."""
        response = client.post("/simulate_match", json=self.VALID_PAYLOAD)
        assert response.status_code == 200, f"Error: {response.text}"

    def test_simulate_result_structure(self, client):
        """El resultado debe tener winner, sets, sets_a, sets_b."""
        response = client.post("/simulate_match", json=self.VALID_PAYLOAD)
        result = response.json()["result"]
        assert "winner" in result
        assert "sets" in result
        assert result["winner"] in ("A", "B")

    def test_simulate_seed_reproducibility(self, client):
        """El mismo seed debe producir resultados idénticos."""
        r1 = client.post("/simulate_match", json=self.VALID_PAYLOAD).json()
        r2 = client.post("/simulate_match", json=self.VALID_PAYLOAD).json()
        assert r1["result"] == r2["result"]

    def test_simulate_same_player_returns_400(self, client):
        """Mismo jugador A y B debe devolver 400."""
        payload = {**self.VALID_PAYLOAD, "player_b": self.VALID_PAYLOAD["player_a"]}
        response = client.post("/simulate_match", json=payload)
        assert response.status_code == 400

    def test_simulate_timeline_none(self, client):
        """timeline_mode='none' debe devolver timeline=null."""
        payload = {**self.VALID_PAYLOAD, "timeline_mode": "none"}
        response = client.post("/simulate_match", json=payload)
        assert response.json()["timeline"] is None

    def test_simulate_bayes_mode_returns_live_params(self, client):
        payload = {**self.VALID_PAYLOAD, "engine_mode": "bayes_live_v1"}
        response = client.post("/simulate_match", json=payload)
        assert response.status_code == 200, f"Error: {response.text}"
        params = response.json()["params"]
        assert params["proxy_method"] == "bayes_live_v1+fatigue_v1"
        assert "p_live_ci_low" in params
        assert "p_live_ci_high" in params

    def test_simulate_bayes_points_returns_point_trace(self, client):
        payload = {
            **self.VALID_PAYLOAD,
            "engine_mode": "bayes_live_v1",
            "timeline_mode": "points",
        }
        response = client.post("/simulate_match", json=payload)
        assert response.status_code == 200, f"Error: {response.text}"
        first_point = response.json()["timeline"][0]["games"][0]["points"][0]
        assert "p_server_bayes_before" in first_point
        assert "p_server_bayes_after" in first_point
        assert len(first_point["trace_factors"]) >= 4

    @pytest.mark.parametrize(
        ("override", "effective"),
        [
            (0.0, 0.01),
            (0.005, 0.01),
            (0.01, 0.01),
            (0.99, 0.99),
            (0.995, 0.99),
            (1.0, 0.99),
        ],
    )
    def test_probability_override_accepts_full_domain_and_applies_bounds(
        self, client, override, effective
    ):
        """Coach Mode accepts [0, 1] and reports the effective probability."""
        payload = {
            **self.VALID_PAYLOAD,
            "p_a_override": override,
            "timeline_mode": "none",
        }
        response = client.post("/simulate_match", json=payload)

        assert response.status_code == 200, f"Error: {response.text}"
        assert response.json()["p_a"] == pytest.approx(effective)
        assert response.json()["p_b"] == pytest.approx(1.0 - effective)

    @pytest.mark.parametrize("override", [-0.001, 1.001])
    def test_probability_override_rejects_values_outside_probability_domain(
        self, client, override
    ):
        payload = {**self.VALID_PAYLOAD, "p_a_override": override}
        response = client.post("/simulate_match", json=payload)

        assert response.status_code == 422


class TestInPlayEndpoints:
    """Tests de endpoints in-play bayesianos."""

    INIT_PAYLOAD = {
        "player_a": "Carlos Alcaraz",
        "player_b": "Jannik Sinner",
        "surface": "Hard",
        "as_of": "2024-01-01",
        "model": "calibrated_logreg",
        "best_of": 3,
        "first_server": "A",
    }

    def test_inplay_init_returns_state(self, client):
        response = client.post("/inplay/init", json=self.INIT_PAYLOAD)
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert "match_id" in data
        assert data["status"] == "in_progress"
        assert 0.0 <= data["p_live_a"] <= 1.0

    def test_inplay_update_and_state_flow(self, client):
        init_resp = client.post("/inplay/init", json=self.INIT_PAYLOAD)
        assert init_resp.status_code == 200, f"Error init: {init_resp.text}"
        match_id = init_resp.json()["match_id"]

        update_payload = {
            "match_id": match_id,
            "server": "A",
            "game_winner": "A",
            "server_points_won": 4,
            "server_points_lost": 2,
            "is_tiebreak": False,
        }
        update_resp = client.post("/inplay/update", json=update_payload)
        assert update_resp.status_code == 200, f"Error update: {update_resp.text}"
        updated = update_resp.json()
        assert updated["games_a"] == 1
        assert updated["n_observations"] >= 6

        state_resp = client.get(f"/inplay/state/{match_id}")
        assert state_resp.status_code == 200, f"Error state: {state_resp.text}"
        state = state_resp.json()
        assert state["match_id"] == match_id
        assert state["games_a"] == updated["games_a"]

    def test_inplay_rejects_inconsistent_server_and_game_score(self, client):
        init_resp = client.post("/inplay/init", json=self.INIT_PAYLOAD)
        match_id = init_resp.json()["match_id"]

        wrong_server = client.post("/inplay/update", json={
            "match_id": match_id,
            "server": "B",
            "game_winner": "B",
            "server_points_won": 4,
            "server_points_lost": 2,
        })
        assert wrong_server.status_code == 400
        assert "server mismatch" in wrong_server.json()["detail"]

        impossible_score = client.post("/inplay/update", json={
            "match_id": match_id,
            "server": "A",
            "game_winner": "A",
            "server_points_won": 4,
            "server_points_lost": 3,
        })
        assert impossible_score.status_code == 400
        assert "diferencia de dos puntos" in impossible_score.json()["detail"]

    def test_inplay_derives_tiebreak_from_six_all(self, client):
        init_resp = client.post("/inplay/init", json=self.INIT_PAYLOAD)
        match_id = init_resp.json()["match_id"]

        state = init_resp.json()
        for index in range(12):
            server = "A" if index % 2 == 0 else "B"
            response = client.post("/inplay/update", json={
                "match_id": match_id,
                "server": server,
                "game_winner": server,
                "server_points_won": 4,
                "server_points_lost": 2,
            })
            assert response.status_code == 200, response.text
            state = response.json()

        assert (state["games_a"], state["games_b"]) == (6, 6)
        tiebreak = client.post("/inplay/update", json={
            "match_id": match_id,
            "server": "A",
            "game_winner": "A",
            "server_points_won": 7,
            "server_points_lost": 5,
        })
        assert tiebreak.status_code == 200, tiebreak.text
        data = tiebreak.json()
        assert (data["sets_a"], data["games_a"], data["games_b"]) == (1, 0, 0)
        assert data["events"][-1]["is_tiebreak"] is True

    def test_inplay_delete_releases_state(self, client):
        init_resp = client.post("/inplay/init", json=self.INIT_PAYLOAD)
        match_id = init_resp.json()["match_id"]

        deleted = client.delete(f"/inplay/{match_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"match_id": match_id, "deleted": True}
        assert client.get(f"/inplay/state/{match_id}").status_code == 400
        assert client.delete(f"/inplay/{match_id}").status_code == 404


class TestTournamentsEndpoint:
    """Tests del endpoint GET /tournaments."""

    def test_tournaments_returns_200(self, client):
        """GET /tournaments debe devolver 200."""
        response = client.get("/tournaments")
        assert response.status_code == 200

    def test_tournaments_response_structure(self, client):
        """La respuesta debe tener 'tournaments' y 'count'."""
        response = client.get("/tournaments")
        data = response.json()
        assert "tournaments" in data
        assert "count" in data

    def test_tournaments_limit_parameter(self, client):
        """El parámetro limit debe funcionar correctamente."""
        response = client.get("/tournaments?limit=5")
        data = response.json()
        assert data["count"] <= 5


class TestTournamentSimulateEndpoint:
    """Tests del endpoint POST /tournament/simulate."""

    VALID_PAYLOAD = {
        "tournament_id": None,
        "players": [
            "Carlos Alcaraz", "Jannik Sinner", "Novak Djokovic", "Daniil Medvedev",
            "Alexander Zverev", "Holger Rune", "Andrey Rublev", "Stefanos Tsitsipas",
        ],
        "size": 8,
        "surface": "Hard",
        "as_of": "2024-01-01",
        "model": "calibrated_logreg",
        "best_of": 3,
        "seed": 42,
        "timeline_mode": "none",
        "seeding": "elo",
    }

    def test_tournament_returns_200(self, client):
        """POST /tournament/simulate con datos válidos debe devolver 200."""
        response = client.post("/tournament/simulate", json=self.VALID_PAYLOAD)
        assert response.status_code == 200, f"Error: {response.text}"

    def test_tournament_champion_is_valid(self, client):
        """El campeón debe ser uno de los jugadores."""
        response = client.post("/tournament/simulate", json=self.VALID_PAYLOAD)
        data = response.json()
        assert data["champion"] in self.VALID_PAYLOAD["players"]

    def test_tournament_has_3_rounds_for_size_8(self, client):
        """Un torneo de 8 jugadores debe tener 3 rondas."""
        response = client.post("/tournament/simulate", json=self.VALID_PAYLOAD)
        data = response.json()
        assert len(data["rounds"]) == 3

    def test_tournament_size_32_is_rejected(self, client):
        """El contrato público limita el torneo a 8 o 16 participantes."""
        payload = {**self.VALID_PAYLOAD, "players": self.VALID_PAYLOAD["players"] * 4, "size": 32}
        response = client.post("/tournament/simulate", json=payload)
        assert response.status_code == 422

    def test_tournament_monte_carlo_returns_odds(self, client):
        """Monte Carlo debe devolver odds agregadas por jugador."""
        mc_payload = {**self.VALID_PAYLOAD, "n_simulations": 5}
        response = client.post("/tournament/simulate_mc", json=mc_payload)
        assert response.status_code == 200, f"Error: {response.text}"
        data = response.json()
        assert data["n_simulations"] == 5
        assert "odds" in data
        assert len(data["odds"]) == len(self.VALID_PAYLOAD["players"])
        assert sum(item["wins"] for item in data["odds"]) == 5
        for item in data["odds"]:
            assert 0.0 <= item["win_pct"] <= 100.0
