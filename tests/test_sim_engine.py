"""
Unit tests for clutch-aware simulation helpers in sim_engine.
"""
import random

from matchpoint.sim_engine import (
    _apply_clutch_adjustment,
    _apply_fatigue_adjustment,
    _game_pressure_factor,
    _match_fatigue_factor,
    _tiebreak_pressure_factor,
    simulate_match,
)


def test_clutch_boosts_stronger_server():
    p = 0.65
    p_adj = _apply_clutch_adjustment(p_server=p, pressure=1.0)
    assert p_adj > p


def test_clutch_penalizes_weaker_server():
    p = 0.45
    p_adj = _apply_clutch_adjustment(p_server=p, pressure=1.0)
    assert p_adj < p


def test_clutch_pressure_zero_keeps_probability():
    p = 0.61
    p_adj = _apply_clutch_adjustment(p_server=p, pressure=0.0)
    assert p_adj == p


def test_game_pressure_is_max_at_deuce():
    assert _game_pressure_factor(3, 3) == 1.0
    assert _game_pressure_factor(4, 4) == 1.0


def test_tiebreak_pressure_is_max_at_set_point():
    assert _tiebreak_pressure_factor(6, 5) == 1.0
    assert _tiebreak_pressure_factor(5, 6) == 1.0


def test_fatigue_factor_grows_smoothly_and_caps():
    assert _match_fatigue_factor(0) == 0.0
    assert 0.0 < _match_fatigue_factor(18) < 1.0
    assert _match_fatigue_factor(72) == 1.0


def test_fatigue_penalizes_serve_probability_softly():
    p = 0.64
    p_adj = _apply_fatigue_adjustment(p_server=p, fatigue_factor=1.0)
    assert p_adj < p
    assert p - p_adj <= 0.025 + 1e-9


def test_points_timeline_exposes_fatigue_factor():
    result = simulate_match(
        p_serve_a=0.62,
        p_serve_b=0.60,
        rng=random.Random(42),
        best_of=3,
        first_server="A",
        timeline_mode="points",
    )
    point_events = [
        point
        for set_event in result["timeline"]
        for game in set_event["games"]
        for point in (game["points"] or [])
    ]
    assert point_events
    assert all("fatigue_factor" in point for point in point_events)
    assert any(point["fatigue_factor"] > 0 for point in point_events)


def test_fatigue_can_be_disabled_for_regression_comparison():
    result = simulate_match(
        p_serve_a=0.62,
        p_serve_b=0.60,
        rng=random.Random(42),
        best_of=5,
        first_server="A",
        timeline_mode="points",
        enable_fatigue=False,
    )
    point_events = [
        point
        for set_event in result["timeline"]
        for game in set_event["games"]
        for point in (game["points"] or [])
    ]
    assert point_events
    assert all(point["fatigue_factor"] == 0.0 for point in point_events)


def test_fatigue_lowers_late_effective_serve_probability_vs_baseline():
    base = simulate_match(
        p_serve_a=0.62,
        p_serve_b=0.60,
        rng=random.Random(7),
        best_of=5,
        first_server="A",
        timeline_mode="points",
        enable_fatigue=False,
    )
    fatigue = simulate_match(
        p_serve_a=0.62,
        p_serve_b=0.60,
        rng=random.Random(7),
        best_of=5,
        first_server="A",
        timeline_mode="points",
        enable_fatigue=True,
    )
    base_points = [
        point
        for set_event in base["timeline"]
        for game in set_event["games"]
        for point in (game["points"] or [])
    ]
    fatigue_points = [
        point
        for set_event in fatigue["timeline"]
        for game in set_event["games"]
        for point in (game["points"] or [])
    ]
    comparable_len = min(len(base_points), len(fatigue_points))
    assert comparable_len > 20
    late_index = comparable_len - 1
    assert fatigue_points[late_index]["fatigue_factor"] > base_points[late_index]["fatigue_factor"]
    assert fatigue_points[late_index]["p_server_eff"] < base_points[late_index]["p_server_eff"]
