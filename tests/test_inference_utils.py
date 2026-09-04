"""
Unit tests for probability post-processing guardrails in inference_utils.
"""
from __future__ import annotations

import backend.services.inference_utils as iu


class DummyPredictor:
    """Minimal predictor stub with deterministic probabilities."""

    def __init__(self, mapping: dict[tuple[str, str], float]):
        self.mapping = mapping
        self.feature_names = []
        self.proc_dir = "."

    def predict_proba(self, player_a: str, player_b: str, surface: str, as_of: str | None = None) -> float:
        return float(self.mapping[(player_a, player_b)])


def test_elite_guardrail_clamps_single_pass_prob(monkeypatch):
    predictor = DummyPredictor({("A", "B"): 0.91})
    monkeypatch.setattr(iu, "uses_dual_pass", lambda model_id: False)
    monkeypatch.setattr(iu, "_is_elite_vs_elite_close_matchup", lambda **kwargs: True)

    p_a, p_b = iu.predict_pair_probabilities(
        predictor=predictor,
        model_id="calibrated_logreg",
        player_a="A",
        player_b="B",
        surface="Hard",
        as_of="2024-01-01",
    )
    assert p_a == iu.ELITE_CLAMP_HIGH
    assert p_b == 1.0 - iu.ELITE_CLAMP_HIGH


def test_non_elite_match_keeps_single_pass_prob(monkeypatch):
    predictor = DummyPredictor({("A", "B"): 0.91})
    monkeypatch.setattr(iu, "uses_dual_pass", lambda model_id: False)
    monkeypatch.setattr(iu, "_is_elite_vs_elite_close_matchup", lambda **kwargs: False)

    p_a, p_b = iu.predict_pair_probabilities(
        predictor=predictor,
        model_id="calibrated_logreg",
        player_a="A",
        player_b="B",
        surface="Hard",
        as_of="2024-01-01",
    )
    assert abs(p_a - 0.91) < 1e-12
    assert abs(p_b - 0.09) < 1e-12


def test_stacking_dual_pass_still_clamped_for_elite(monkeypatch):
    predictor = DummyPredictor({("A", "B"): 0.9, ("B", "A"): 0.1})
    monkeypatch.setattr(iu, "uses_dual_pass", lambda model_id: True)
    monkeypatch.setattr(iu, "_is_elite_vs_elite_close_matchup", lambda **kwargs: True)

    p_a, p_b = iu.predict_pair_probabilities(
        predictor=predictor,
        model_id="stacking_ensemble",
        player_a="A",
        player_b="B",
        surface="Hard",
        as_of="2024-01-01",
    )
    assert iu.ELITE_CLAMP_LOW <= p_a <= iu.ELITE_CLAMP_HIGH
    assert abs((p_a + p_b) - 1.0) < 1e-12
    # Stacking applies temperature scaling first, so it should be less extreme than 0.9.
    assert p_a < 0.9
