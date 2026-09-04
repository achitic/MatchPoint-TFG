# tests/test_predict_service.py
"""
Unit tests for PredictService.

Covers:
- Predicciones dentro del rango [0, 1]
- Suma de probabilidades ≈ 1
- Jugadores iguales → ValueError
- Superficie inválida (graceful handling)
- Modelos disponibles
- Fecha as_of clamping
"""
import pytest
from conftest import PLAYER_A, PLAYER_B, SURFACE, AS_OF


class TestPredictServiceBasic:
    """Tests básicos de predicción."""

    def test_prediction_range(self, predict_service):
        """Las probabilidades deben estar en [0, 1]."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            model="calibrated_logreg",
            as_of=AS_OF,
        )
        assert 0.0 <= result["p_a"] <= 1.0, f"p_a fuera de rango: {result['p_a']}"
        assert 0.0 <= result["p_b"] <= 1.0, f"p_b fuera de rango: {result['p_b']}"

    def test_probabilities_sum_to_one(self, predict_service):
        """p_a + p_b debe ser aproximadamente 1."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            model="calibrated_logreg",
            as_of=AS_OF,
        )
        total = result["p_a"] + result["p_b"]
        assert abs(total - 1.0) < 0.01, f"p_a + p_b = {total} (esperado ≈ 1)"

    def test_same_player_raises_error(self, predict_service):
        """Usar el mismo jugador como A y B debe lanzar ValueError."""
        with pytest.raises(ValueError, match="different"):
            predict_service.predict(
                player_a=PLAYER_A,
                player_b=PLAYER_A,
                surface=SURFACE,
            )

    def test_result_contains_required_fields(self, predict_service):
        """El resultado debe contener todos los campos requeridos."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
        )
        required_fields = ["player_a", "player_b", "surface", "model",
                           "as_of_used", "p_a", "p_b", "warnings"]
        for field in required_fields:
            assert field in result, f"Falta campo: {field}"

    def test_player_names_preserved(self, predict_service):
        """Los nombres de jugadores deben preservarse en el resultado."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
        )
        assert result["player_a"] == PLAYER_A
        assert result["player_b"] == PLAYER_B
        assert result["surface"] == SURFACE


class TestPredictServiceModels:
    """Tests con diferentes modelos."""

    @pytest.mark.parametrize("model", ["baseline_logreg", "surface_logreg", "calibrated_logreg"])
    def test_all_logreg_models(self, predict_service, model):
        """Los modelos de regresión logística deben producir predicciones válidas."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            model=model,
            as_of=AS_OF,
        )
        assert 0.0 <= result["p_a"] <= 1.0
        assert result["model"] == model

    @pytest.mark.parametrize(
        ("legacy_model", "canonical_model"),
        [
            ("core", "baseline_logreg"),
            ("core_elop", "surface_logreg"),
            ("core_calibrated", "calibrated_logreg"),
        ],
    )
    def test_legacy_model_aliases_are_supported(self, predict_service, legacy_model, canonical_model):
        """Los alias legacy deben seguir funcionando y resolverse al ID canónico."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            model=legacy_model,
            as_of=AS_OF,
        )
        assert 0.0 <= result["p_a"] <= 1.0
        assert result["model"] == canonical_model

    @pytest.mark.parametrize("surface", ["Hard", "Clay", "Grass"])
    def test_all_surfaces(self, predict_service, surface):
        """La predicción debe funcionar en las 3 superficies disponibles."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=surface,
        )
        assert 0.0 <= result["p_a"] <= 1.0


class TestPredictServiceDate:
    """Tests de manejo de fechas as_of."""

    def test_future_date_clamped(self, predict_service):
        """Una fecha futura debe clampear al máximo del dataset con aviso."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            as_of="2099-01-01",
        )
        # Debe haber un warning de clamping
        warnings_text = " ".join(result["warnings"])
        assert "clamped" in warnings_text.lower() or "max_date" in warnings_text.lower()

    def test_none_date_uses_latest(self, predict_service):
        """as_of=None debe usar la fecha más reciente del dataset."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            as_of=None,
        )
        assert result["as_of_used"] is not None
        assert len(result["as_of_used"]) == 10  # YYYY-MM-DD


class TestPredictServicePlayers:
    """Tests de listado de jugadores."""

    def test_get_players_returns_list(self, predict_service):
        """get_players debe devolver una lista no vacía."""
        players = predict_service.get_players()
        assert isinstance(players, list)
        assert len(players) > 0

    def test_players_are_strings(self, predict_service):
        """Todos los jugadores deben ser strings."""
        players = predict_service.get_players()
        assert all(isinstance(p, str) for p in players)

    def test_players_are_sorted(self, predict_service):
        """La lista de jugadores debe estar ordenada."""
        players = predict_service.get_players()
        assert players == sorted(players)


class TestPredictServiceDebug:
    """Tests del modo debug."""

    def test_debug_mode_returns_features(self, predict_service):
        """El modo debug debe devolver features_a, features_b y top_diffs."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            debug=True,
        )
        assert result["debug"] is not None
        assert "features_a" in result["debug"]
        assert "features_b" in result["debug"]
        assert "top_diffs" in result["debug"]

    def test_debug_features_are_numeric(self, predict_service):
        """Los features en debug deben ser valores numéricos."""
        result = predict_service.predict(
            player_a=PLAYER_A,
            player_b=PLAYER_B,
            surface=SURFACE,
            debug=True,
        )
        features_a = result["debug"]["features_a"]
        for key, val in features_a.items():
            assert isinstance(val, (int, float)), f"Feature '{key}' no es numérico: {val}"
