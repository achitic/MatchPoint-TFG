from pathlib import Path
import sys
import pandas as pd
from collections import defaultdict

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.validation import (
    check_file_exists,
    validate_not_empty,
    validate_columns,
    validate_datetime,
)

CONFIG = {
    "elo_start": 1500,          # ELO inicial asignado a cada jugador
    "scale": 400,
    "default_K": 30,            # Valor por defecto si el nivel del torneo no está definido
    "k_levels": {               # Factores K según el tipo de torneo
        "G": 42,  # Grand Slam
        "F": 38,  # ATP Finals
        "M": 36,  # Masters 1000
        "A": 30,  # ATP 500 / 250
        "D": 28,  # Davis Cup
        "C": 24,  # Challenger
    },
}

AUSENCIA_UMBRAL_DIAS = 90
AUSENCIA_PENALIZACION_POR_MES = 2.0  # Puntos ELO restados por cada mes de ausencia
AUSENCIA_MAX_REDUCCION = 50        # Máximo de puntos ELO que se pueden quitar
RETORNO_N_PARTIDOS = 5             # Partidos con K factor elevado tras el retorno
RETORNO_K_MULTIPLICADOR = 1.5     # K factor × 1.5 en partidos de retorno


BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)


def expected_score(elo_a: float, elo_b: float, scale: float) -> float:
    """Calcula la probabilidad esperada de que el jugador A gane a B."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / scale))


def update_elo(elo_a: float, elo_b: float, score_a: float, K: float, scale: float) -> tuple[float, float]:
    """
    Actualiza los valores ELO de dos jugadores tras un partido.

    Args:
        elo_a, elo_b: valores ELO actuales
        score_a: 1 si gana A, 0 si pierde A
    """
    exp_a = expected_score(elo_a, elo_b, scale)
    exp_b = 1 - exp_a
    new_a = elo_a + K * (score_a - exp_a)
    new_b = elo_b + K * ((1 - score_a) - exp_b)
    return new_a, new_b


def _aplicar_penalizacion_ausencia(
    player: str,
    fecha_actual: pd.Timestamp,
    elo_actual: float,
    last_played: dict,
    retorno_counter: dict,
) -> float:
    """Penaliza ausencias largas y activa un K mayor al regreso."""
    if player not in last_played:
        return elo_actual

    dias_ausente = (fecha_actual - last_played[player]).days

    if dias_ausente < AUSENCIA_UMBRAL_DIAS:
        return elo_actual

    meses_ausente = dias_ausente / 30.0
    penalizacion = min(meses_ausente * AUSENCIA_PENALIZACION_POR_MES, AUSENCIA_MAX_REDUCCION)

    retorno_counter[player] = RETORNO_N_PARTIDOS

    return elo_actual - penalizacion


def main():
    cfg = CONFIG
    START_ELO = cfg["elo_start"]
    SCALE = cfg["scale"]
    K_LEVELS = cfg["k_levels"]
    DEFAULT_K = cfg["default_K"]

    path = PROC_DIR / "matches_clean.parquet"

    check_file_exists(path)

    df = pd.read_parquet(path)
    validate_not_empty(df, "matches_clean")
    validate_columns(df, {"winner_name", "loser_name", "tourney_date", "surface", "tourney_level"})
    validate_datetime(df, "tourney_date")

    print(f"Dataset cargado: {len(df):,} partidos ({df['year'].min()}–{df['year'].max()})")

    df = df.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    elo = defaultdict(lambda: START_ELO)
    elo_surface = defaultdict(lambda: defaultdict(lambda: START_ELO))

    last_played = {}
    retorno_counter = {}
    penalty_count = 0

    history = []

    for match_row_id, row in df.iterrows():
        w, l = row["winner_name"], row["loser_name"]
        surface, level = row["surface"], row["tourney_level"]
        fecha = row["tourney_date"]

        # La penalización se aplica antes de guardar la instantánea prepartido.
        w_elo_pre = elo[w]
        l_elo_pre = elo[l]

        w_elo_adj = _aplicar_penalizacion_ausencia(w, fecha, elo[w], last_played, retorno_counter)
        l_elo_adj = _aplicar_penalizacion_ausencia(l, fecha, elo[l], last_played, retorno_counter)

        if w_elo_adj != elo[w]:
            penalty_count += 1
            penalty_ratio = (elo[w] - w_elo_adj) / max(elo[w] - START_ELO, 1.0) if elo[w] != START_ELO else 0.0
            elo[w] = w_elo_adj
            for surf_key in elo_surface[w]:
                surf_val = elo_surface[w][surf_key]
                elo_surface[w][surf_key] = surf_val - (surf_val - START_ELO) * min(penalty_ratio, 0.3)

        if l_elo_adj != elo[l]:
            penalty_count += 1
            penalty_ratio = (elo[l] - l_elo_adj) / max(elo[l] - START_ELO, 1.0) if elo[l] != START_ELO else 0.0
            elo[l] = l_elo_adj
            for surf_key in elo_surface[l]:
                surf_val = elo_surface[l][surf_key]
                elo_surface[l][surf_key] = surf_val - (surf_val - START_ELO) * min(penalty_ratio, 0.3)

        w_elo, l_elo = elo[w], elo[l]
        w_surf, l_surf = elo_surface[w][surface], elo_surface[l][surface]

        K_base = K_LEVELS.get(level, DEFAULT_K)
        K_w = K_base * RETORNO_K_MULTIPLICADOR if retorno_counter.get(w, 0) > 0 else K_base
        K_l = K_base * RETORNO_K_MULTIPLICADOR if retorno_counter.get(l, 0) > 0 else K_base
        # Un único K medio mantiene la actualización de ambos jugadores simétrica.
        K = (K_w + K_l) / 2.0

        new_w, new_l = update_elo(w_elo, l_elo, 1, K, SCALE)
        elo[w], elo[l] = new_w, new_l

        new_ws, new_ls = update_elo(w_surf, l_surf, 1, K, SCALE)
        elo_surface[w][surface], elo_surface[l][surface] = new_ws, new_ls

        # La mezcla reduce la varianza con pocos partidos en la superficie.
        w_blended = 0.5 * w_elo + 0.5 * w_surf
        l_blended = 0.5 * l_elo + 0.5 * l_surf

        # match_row_id alinea este snapshot con matches_clean sin ambigüedad.
        history.append({
            "match_row_id": int(match_row_id),
            "date": fecha,
            "surface": surface,
            "level": level,
            "winner": w,
            "loser": l,
            "elo_w_before": w_elo,
            "elo_l_before": l_elo,
            "elo_w_after": new_w,
            "elo_l_after": new_l,
            "elo_w_surface_before": w_surf,
            "elo_l_surface_before": l_surf,
            "elo_w_surface_after": new_ws,
            "elo_l_surface_after": new_ls,
            "elo_w_blended_before": w_blended,
            "elo_l_blended_before": l_blended,
        })

        if w in retorno_counter and retorno_counter[w] > 0:
            retorno_counter[w] -= 1
        if l in retorno_counter and retorno_counter[l] > 0:
            retorno_counter[l] -= 1
        last_played[w] = fecha
        last_played[l] = fecha

    df_hist = pd.DataFrame(history)
    out_hist = PROC_DIR / "elo_history.csv"
    df_hist.to_csv(out_hist, index=False)

    latest = []
    for player, global_elo in elo.items():
        record = {"player": player, "elo_global": global_elo}
        for surf, surf_elo in elo_surface[player].items():
            record[f"elo_{surf}"] = surf_elo
        latest.append(record)

    df_latest = pd.DataFrame(latest)
    out_latest = PROC_DIR / "elo_latest.csv"
    df_latest.to_csv(out_latest, index=False)

    print(f"Guardado histórico: {out_hist} ({len(df_hist):,} filas)")
    print(f"Guardado ELO más reciente: {out_latest} ({len(df_latest):,} jugadores)")
    print(f"Parámetros: START={START_ELO}, SCALE={SCALE}, DEFAULT_K={DEFAULT_K}")
    print(f"Penalizaciones por ausencia aplicadas: {penalty_count}")
    print("Top 10 jugadores por ELO global:")
    print(df_latest.sort_values('elo_global', ascending=False).head(10))


if __name__ == "__main__":
    main()
