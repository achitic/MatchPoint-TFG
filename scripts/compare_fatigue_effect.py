"""
Compare tennis simulation output with fatigue disabled vs enabled.

This is a deterministic diagnostic script. It uses the pure simulation engine
directly so both variants share the same serve probabilities, seed, format and
first server.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from matchpoint.sim_engine import simulate_match


P_SERVE_A = 0.62
P_SERVE_B = 0.60
BEST_OF = 5
FIRST_SERVER = "A"
SEEDS = list(range(100, 130))


def iter_points(result: dict):
    for set_event in result["timeline"] or []:
        for game in set_event["games"] or []:
            for point in game["points"] or []:
                yield set_event, game, point


def summarize(result: dict) -> dict:
    points = list(iter_points(result))
    p_eff_values = [float(point["p_server_eff"]) for _, _, point in points]
    fatigue_values = [float(point.get("fatigue_factor", 0.0)) for _, _, point in points]
    pressure_values = [float(point.get("pressure", 0.0)) for _, _, point in points]
    key_points = [p for p in pressure_values if p >= 0.5]
    total_games = sum(
        int(score.split("-")[0]) + int(score.split("-")[1])
        for score in result["sets"]
    )
    return {
        "winner": result["winner"],
        "sets": " ".join(result["sets"]),
        "sets_a": result["sets_a"],
        "sets_b": result["sets_b"],
        "total_games": total_games,
        "total_points": len(points),
        "avg_p_server_eff": mean(p_eff_values) if p_eff_values else 0.0,
        "min_p_server_eff": min(p_eff_values) if p_eff_values else 0.0,
        "max_fatigue": max(fatigue_values) if fatigue_values else 0.0,
        "avg_fatigue": mean(fatigue_values) if fatigue_values else 0.0,
        "key_points": len(key_points),
    }


def run_one(seed: int, enable_fatigue: bool) -> dict:
    return simulate_match(
        p_serve_a=P_SERVE_A,
        p_serve_b=P_SERVE_B,
        rng=random.Random(seed),
        best_of=BEST_OF,
        first_server=FIRST_SERVER,
        timeline_mode="points",
        enable_fatigue=enable_fatigue,
    )


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def main() -> None:
    rows = []
    for seed in SEEDS:
        baseline = summarize(run_one(seed, enable_fatigue=False))
        fatigue = summarize(run_one(seed, enable_fatigue=True))
        rows.append((seed, baseline, fatigue))

    changed_winner = sum(1 for _, base, fat in rows if base["winner"] != fat["winner"])
    changed_score = sum(1 for _, base, fat in rows if base["sets"] != fat["sets"])
    avg_points_delta = mean(fat["total_points"] - base["total_points"] for _, base, fat in rows)
    avg_p_eff_delta = mean(fat["avg_p_server_eff"] - base["avg_p_server_eff"] for _, base, fat in rows)
    avg_max_fatigue = mean(fat["max_fatigue"] for _, _, fat in rows)
    avg_key_point_delta = mean(fat["key_points"] - base["key_points"] for _, base, fat in rows)

    print("Comparativa fatiga v1 vs comportamiento anterior")
    print(f"Seeds analizadas: {SEEDS[0]}..{SEEDS[-1]} ({len(SEEDS)} partidos)")
    print(f"Formato: best_of={BEST_OF}, first_server={FIRST_SERVER}")
    print(f"P saque base A/B: {fmt_pct(P_SERVE_A)} / {fmt_pct(P_SERVE_B)}")
    print()
    print("Resumen agregado")
    print(f"Ganador distinto: {changed_winner}/{len(SEEDS)} partidos")
    print(f"Marcador de sets distinto: {changed_score}/{len(SEEDS)} partidos")
    print(f"Delta medio de puntos totales: {avg_points_delta:+.2f}")
    print(f"Delta medio de P saque efectiva: {fmt_pct(avg_p_eff_delta)}")
    print(f"Fatiga maxima media alcanzada: {fmt_pct(avg_max_fatigue)}")
    print(f"Delta medio de puntos clave: {avg_key_point_delta:+.2f}")
    print()

    sample_seed, sample_base, sample_fat = rows[0]
    print(f"Ejemplo seed={sample_seed}")
    print(f"{'Metrica':28} {'Sin fatiga':>14} {'Con fatiga':>14}")
    print(f"{'Ganador':28} {sample_base['winner']:>14} {sample_fat['winner']:>14}")
    print(f"{'Sets':28} {sample_base['sets']:>14} {sample_fat['sets']:>14}")
    print(f"{'Puntos totales':28} {sample_base['total_points']:>14} {sample_fat['total_points']:>14}")
    print(f"{'P saque efectiva media':28} {fmt_pct(sample_base['avg_p_server_eff']):>14} {fmt_pct(sample_fat['avg_p_server_eff']):>14}")
    print(f"{'P saque efectiva minima':28} {fmt_pct(sample_base['min_p_server_eff']):>14} {fmt_pct(sample_fat['min_p_server_eff']):>14}")
    print(f"{'Fatiga maxima':28} {fmt_pct(sample_base['max_fatigue']):>14} {fmt_pct(sample_fat['max_fatigue']):>14}")
    print(f"{'Puntos clave':28} {sample_base['key_points']:>14} {sample_fat['key_points']:>14}")


if __name__ == "__main__":
    main()
