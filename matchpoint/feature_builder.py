from __future__ import annotations

from pathlib import Path
import difflib
from functools import lru_cache
import pandas as pd
import numpy as np

ELO_SCALE = 400.0
REST_DAYS_CAP = 3.0
REST_DAYS_TAU = 1.5
REST_RUST_START_DAYS = 10.0
REST_RUST_TAU = 12.0
REST_RUST_MAX_PENALTY = 2.0
RECENCY_WINDOW_DAYS = 730.0
RECENCY_HALFLIFE_DAYS = 365.0
SERVE_SHRINKAGE_POINTS = 120.0
BP_SHRINKAGE_POINTS = 30.0
DOMINANCE_SHRINKAGE_MATCHES = 20.0
DEFAULT_SERVE_PCT = 0.62
DEFAULT_BP_SAVE_PCT = 0.62
DEFAULT_DOMINANCE = 1.0


def _elo_expected_from_diff(diff: float, scale: float = ELO_SCALE) -> float:
    # clamp por estabilidad numérica
    x = float(np.clip(diff, -2000.0, 2000.0))
    return 1.0 / (1.0 + (10.0 ** (-x / scale)))


def _effective_rest_days(days: float) -> float:
    """
    Effective rest signal:
    - strong effect on first 1-3 days
    - plateau
    - soft penalty for long layoffs (match rust)
    Must match training-time transform in scripts/build_features.py.
    """
    d = max(float(days), 0.0)
    gain = REST_DAYS_CAP * (1.0 - np.exp(-d / REST_DAYS_TAU))
    rust_days = max(d - REST_RUST_START_DAYS, 0.0)
    rust_penalty = REST_RUST_MAX_PENALTY * (1.0 - np.exp(-rust_days / REST_RUST_TAU))
    eff = gain - rust_penalty
    return float(np.clip(eff, 0.0, REST_DAYS_CAP))


def _decay_weight(age_days: float) -> float:
    age = max(float(age_days), 0.0)
    return float(np.exp(-np.log(2.0) * age / RECENCY_HALFLIFE_DAYS))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _ratio(num: float, den: float, default: float) -> float:
    den = float(den)
    if den <= 0:
        return float(default)
    return float(num) / den


def _shrunk_rate(num: float, den: float, prior: float, prior_strength: float) -> float:
    den = max(float(den), 0.0)
    return float((float(num) + prior_strength * float(prior)) / (den + prior_strength))


def _serve_line(row: pd.Series, prefix: str, opp_prefix: str) -> dict[str, float]:
    svpt = _safe_float(row.get(f"{prefix}_svpt"), 0.0)
    first_won = _safe_float(row.get(f"{prefix}_1stWon"), 0.0)
    second_won = _safe_float(row.get(f"{prefix}_2ndWon"), 0.0)
    bp_saved = _safe_float(row.get(f"{prefix}_bpSaved"), 0.0)
    bp_faced = _safe_float(row.get(f"{prefix}_bpFaced"), 0.0)

    opp_svpt = _safe_float(row.get(f"{opp_prefix}_svpt"), 0.0)
    opp_first_won = _safe_float(row.get(f"{opp_prefix}_1stWon"), 0.0)
    opp_second_won = _safe_float(row.get(f"{opp_prefix}_2ndWon"), 0.0)

    service_won = first_won + second_won
    return_won = max(opp_svpt - opp_first_won - opp_second_won, 0.0)
    opp_return_won = max(svpt - service_won, 0.0)

    return {
        "service_won": service_won,
        "service_total": svpt,
        "bp_saved": bp_saved,
        "bp_faced": bp_faced,
        "dominance": _ratio(return_won, opp_return_won, DEFAULT_DOMINANCE),
        "has_dominance": 1.0 if svpt > 0 and opp_svpt > 0 else 0.0,
    }


@lru_cache(maxsize=4)
def _load_matches(proc_dir: Path) -> pd.DataFrame:
    df = pd.read_parquet(proc_dir / "matches_clean.parquet")
    if not np.issubdtype(df["tourney_date"].dtype, np.datetime64):
        df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    return df.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)


@lru_cache(maxsize=4)
def _load_elo_latest(proc_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(proc_dir / "elo_latest.csv")
    if "player" not in df.columns:
        raise ValueError("elo_latest.csv debe tener columna 'player'")
    return df


@lru_cache(maxsize=4)
def _load_elo_history(proc_dir: Path) -> pd.DataFrame:
    """
    Tu elo_history.csv es un log por partido con columnas winner/loser y elo_*_after.
    """
    path = proc_dir / "elo_history.csv"
    df = pd.read_csv(path)

    required = {
        "date", "surface", "winner", "loser",
        "elo_w_after", "elo_l_after",
        "elo_w_surface_after", "elo_l_surface_after",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"elo_history.csv no tiene columnas requeridas: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["surface"] = df["surface"].astype(str).str.title()
    return df.sort_values("date", kind="mergesort").reset_index(drop=True)


def _elo_asof_from_matchlog(
    elo_hist: pd.DataFrame,
    player: str,
    as_of_ts: pd.Timestamp,
    surface: str,
) -> tuple[float, float]:
    """
    Devuelve (elo_global_asof, elo_surface_asof) a partir del log por partido:
    - global: último elo_*_after del jugador (como winner o loser) antes de as_of_ts
    - surface: último elo_*_surface_after del jugador en ESA superficie antes de as_of_ts
    """
    m = elo_hist[
        (elo_hist["date"] <= as_of_ts)
        & ((elo_hist["winner"] == player) | (elo_hist["loser"] == player))
    ]
    if m.empty:
        elo_g = 0.0
    else:
        r = m.iloc[-1]
        elo_g = float(r["elo_w_after"]) if r["winner"] == player else float(r["elo_l_after"])

    ms = elo_hist[
        (elo_hist["date"] <= as_of_ts)
        & (elo_hist["surface"] == surface)
        & ((elo_hist["winner"] == player) | (elo_hist["loser"] == player))
    ]
    if ms.empty:
        elo_s = 0.0
    else:
        rs = ms.iloc[-1]
        elo_s = float(rs["elo_w_surface_after"]) if rs["winner"] == player else float(rs["elo_l_surface_after"])

    return elo_g, elo_s


def _resolve_player(name: str, all_names: list[str]) -> str:
    name = str(name).strip()
    lookup = {n.lower(): n for n in all_names}
    if name.lower() in lookup:
        return lookup[name.lower()]
    close = difflib.get_close_matches(name, all_names, n=5, cutoff=0.75)
    if close:
        return close[0]
    raise ValueError(f"Jugador no encontrado: '{name}'")


def _recent_form_ratio(
    hist: pd.DataFrame,
    player: str,
    as_of_ts: pd.Timestamp,
) -> float:
    """Exponentially decayed win-rate in the last RECENCY_WINDOW_DAYS."""
    m = hist[
        ((hist["winner_name"] == player) | (hist["loser_name"] == player))
        & (hist["tourney_date"] <= as_of_ts)
        & (hist["tourney_date"] >= (as_of_ts - pd.Timedelta(days=RECENCY_WINDOW_DAYS)))
    ]
    if m.empty:
        return 0.5

    weights = []
    outcomes = []
    for _, r in m.iterrows():
        age = max((as_of_ts - pd.Timestamp(r["tourney_date"])).days, 0)
        w = _decay_weight(age)
        weights.append(w)
        outcomes.append(1.0 if str(r["winner_name"]) == player else 0.0)

    total_w = float(np.sum(weights))
    if total_w <= 0:
        return 0.5
    return float(np.dot(weights, outcomes) / total_w)


def _service_snapshot(hist: pd.DataFrame, player: str) -> tuple[float, float, float]:
    required = {
        "w_svpt", "w_1stWon", "w_2ndWon", "w_bpSaved", "w_bpFaced",
        "l_svpt", "l_1stWon", "l_2ndWon", "l_bpSaved", "l_bpFaced",
    }
    if not required.issubset(hist.columns):
        return DEFAULT_SERVE_PCT, DEFAULT_BP_SAVE_PCT, DEFAULT_DOMINANCE

    def aggregate(frame: pd.DataFrame, prefix: str, opp_prefix: str) -> dict[str, float]:
        if frame.empty:
            return {key: 0.0 for key in (
                "service_won", "service_total", "bp_saved", "bp_faced",
                "dominance_sum", "dominance_n",
            )}

        def numeric(name: str) -> pd.Series:
            return pd.to_numeric(frame[name], errors="coerce").fillna(0.0)

        svpt = numeric(f"{prefix}_svpt")
        first_won = numeric(f"{prefix}_1stWon")
        second_won = numeric(f"{prefix}_2ndWon")
        service_won = first_won + second_won
        opp_svpt = numeric(f"{opp_prefix}_svpt")
        opp_service_won = numeric(f"{opp_prefix}_1stWon") + numeric(f"{opp_prefix}_2ndWon")
        return_won = (opp_svpt - opp_service_won).clip(lower=0.0)
        opp_return_won = (svpt - service_won).clip(lower=0.0)
        valid_dominance = (svpt > 0.0) & (opp_svpt > 0.0)
        dominance = pd.Series(DEFAULT_DOMINANCE, index=frame.index, dtype=float)
        ratio_mask = valid_dominance & (opp_return_won > 0.0)
        dominance.loc[ratio_mask] = return_won.loc[ratio_mask] / opp_return_won.loc[ratio_mask]

        return {
            "service_won": float(service_won.sum()),
            "service_total": float(svpt.sum()),
            "bp_saved": float(numeric(f"{prefix}_bpSaved").sum()),
            "bp_faced": float(numeric(f"{prefix}_bpFaced").sum()),
            "dominance_sum": float(dominance.loc[valid_dominance].sum()),
            "dominance_n": float(valid_dominance.sum()),
        }

    def combine(*states: dict[str, float]) -> dict[str, float]:
        return {key: sum(state[key] for state in states) for key in states[0]}

    global_state = combine(aggregate(hist, "w", "l"), aggregate(hist, "l", "w"))
    player_state = combine(
        aggregate(hist.loc[hist["winner_name"] == player], "w", "l"),
        aggregate(hist.loc[hist["loser_name"] == player], "l", "w"),
    )

    serve_prior = _ratio(global_state["service_won"], global_state["service_total"], DEFAULT_SERVE_PCT)
    bp_prior = _ratio(global_state["bp_saved"], global_state["bp_faced"], DEFAULT_BP_SAVE_PCT)
    dom_prior = _ratio(global_state["dominance_sum"], global_state["dominance_n"], DEFAULT_DOMINANCE)

    serve_pct = _shrunk_rate(
        player_state["service_won"], player_state["service_total"], serve_prior, SERVE_SHRINKAGE_POINTS
    )
    bp_save_pct = _shrunk_rate(
        player_state["bp_saved"], player_state["bp_faced"], bp_prior, BP_SHRINKAGE_POINTS
    )
    dominance = _shrunk_rate(
        player_state["dominance_sum"], player_state["dominance_n"], dom_prior, DOMINANCE_SHRINKAGE_MATCHES
    )
    return serve_pct, bp_save_pct, dominance


def _player_snapshot(hist: pd.DataFrame, player: str) -> dict:
    """
    Devuelve un dict con atributos del jugador (sin prefijo winner_/loser_),
    extraídos del último partido <= as_of.
    Si en ese partido fue winner, usa columnas winner_*; si fue loser, usa loser_*.
    """
    m = hist[(hist["winner_name"] == player) | (hist["loser_name"] == player)]
    if m.empty:
        return {}

    r = m.iloc[-1]
    prefix = "winner_" if r["winner_name"] == player else "loser_"

    snap = {}
    for col in r.index:
        if col.startswith(prefix):
            attr = col[len(prefix):]
            val = r[col]
            if pd.api.types.is_number(val) or isinstance(val, (int, float, np.number)):
                snap[attr] = 0 if pd.isna(val) else val
    return snap


def build_match_features(
    *,
    player_a: str,
    player_b: str,
    surface: str,
    feature_schema: list[str],
    proc_dir: Path,
    as_of: str | None = None,
) -> pd.DataFrame:
    surface = str(surface).strip().title()
    if surface not in {"Hard", "Clay", "Grass"}:
        raise ValueError("surface debe ser Hard, Clay o Grass")

    matches = _load_matches(proc_dir)
    # mantenemos esto por compatibilidad (stacking puede usarlo en el futuro),
    # aunque el core ya no depende de elo_latest
    _ = _load_elo_latest(proc_dir)

    all_players = sorted(set(matches["winner_name"]).union(set(matches["loser_name"])))
    A = _resolve_player(player_a, all_players)
    B = _resolve_player(player_b, all_players)

    # ============================================================
    # DEFAULT AS-OF (MUY IMPORTANTE)
    # Antes: as_of_ts = max global del dataset -> puede dar 95%+
    # Ahora: si no pasan as_of, usamos una fecha "común" razonable:
    #        as_of_ts = min(último partido de A, último partido de B)
    # Esto evita snapshots extremos por defecto.
    # ============================================================
    if as_of:
        as_of_ts = pd.Timestamp(as_of)
    else:
        lastA = matches.loc[
            (matches["winner_name"] == A) | (matches["loser_name"] == A),
            "tourney_date",
        ].max()
        lastB = matches.loc[
            (matches["winner_name"] == B) | (matches["loser_name"] == B),
            "tourney_date",
        ].max()

        if pd.isna(lastA) or pd.isna(lastB):
            as_of_ts = pd.Timestamp(matches["tourney_date"].max())
        else:
            as_of_ts = pd.Timestamp(min(lastA, lastB))

    hist = matches[matches["tourney_date"] <= as_of_ts]

    row = {c: 0 for c in feature_schema}

    def set_if_exists(k, v):
        if k in row:
            row[k] = v

    # --- rellenar winner_* y loser_* desde snapshot del último partido ---
    snapA = _player_snapshot(hist, A)
    snapB = _player_snapshot(hist, B)

    for feat in feature_schema:
        if feat.startswith("winner_"):
            attr = feat[len("winner_"):]
            if attr in snapA:
                set_if_exists(feat, snapA[attr])
        elif feat.startswith("loser_"):
            attr = feat[len("loser_"):]
            if attr in snapB:
                set_if_exists(feat, snapB[attr])

    # (algunas features derivadas)
    if "age_diff" in row:
        # For core schemas winner_age/loser_age may not be present in feature_schema.
        # Use snapshot ages directly so age_diff stays consistent with training data.
        a_age = snapA.get("age", row.get("winner_age", 0))
        b_age = snapB.get("age", row.get("loser_age", 0))
        row["age_diff"] = float(a_age - b_age)

    # match-level simples si están en schema
    if "best_of" in row:
        row["best_of"] = 3
    if "year" in row:
        row["year"] = int(as_of_ts.year)

    # --- ELO AS-OF desde elo_history.csv (log por partido) ---
    elo_hist = _load_elo_history(proc_dir)
    eloA_g, eloA_s = _elo_asof_from_matchlog(elo_hist, A, as_of_ts, surface)
    eloB_g, eloB_s = _elo_asof_from_matchlog(elo_hist, B, as_of_ts, surface)

    # saneo NaN/inf para evitar que elo_p_* acabe en 0 por fillna(0)
    def _nz(x, default=0.0):
        try:
            if pd.isna(x) or np.isinf(x):
                return float(default)
            return float(x)
        except Exception:
            return float(default)

    eloA_g = _nz(eloA_g, 0.0)
    eloB_g = _nz(eloB_g, 0.0)
    eloA_s = _nz(eloA_s, 0.0)
    eloB_s = _nz(eloB_s, 0.0)

    diff_g = float(eloA_g - eloB_g)
    diff_s = float(eloA_s - eloB_s)

    # diffs directos (CORE)
    if "elo_diff_global" in row:
        row["elo_diff_global"] = diff_g
    if "elo_diff_surface" in row:
        row["elo_diff_surface"] = diff_s

    # elo_p_* (CORE_ELOP / CORE_CALIBRATED)
    if "elo_p_global" in row:
        row["elo_p_global"] = 0.5 if (eloA_g == 0.0 and eloB_g == 0.0) else _elo_expected_from_diff(diff_g, ELO_SCALE)
    if "elo_p_surface" in row:
        row["elo_p_surface"] = 0.5 if (eloA_s == 0.0 and eloB_s == 0.0) else _elo_expected_from_diff(diff_s, ELO_SCALE)

    set_if_exists("elo_w_global", float(eloA_g))
    set_if_exists("elo_l_global", float(eloB_g))
    set_if_exists(f"elo_w_{surface}", float(eloA_s))
    set_if_exists(f"elo_l_{surface}", float(eloB_s))
    set_if_exists("elo_w_before", float(eloA_g))
    set_if_exists("elo_l_before", float(eloB_g))
    set_if_exists("elo_w_surface_before", float(eloA_s))
    set_if_exists("elo_l_surface_before", float(eloB_s))

    # La mezcla 50/50 regulariza el Elo de superficies con pocas observaciones.
    eloA_blended = 0.5 * eloA_g + 0.5 * eloA_s
    eloB_blended = 0.5 * eloB_g + 0.5 * eloB_s
    diff_blended = float(eloA_blended - eloB_blended)

    set_if_exists("elo_w_blended_before", float(eloA_blended))
    set_if_exists("elo_l_blended_before", float(eloB_blended))
    if "elo_diff_blended" in row:
        row["elo_diff_blended"] = diff_blended
    if "elo_p_blended" in row:
        both_zero = (eloA_g == 0.0 and eloB_g == 0.0)
        row["elo_p_blended"] = 0.5 if both_zero else _elo_expected_from_diff(diff_blended, ELO_SCALE)

    # --- last5, h2h, rest_days ---
    def last5(player: str):
        m = hist[(hist["winner_name"] == player) | (hist["loser_name"] == player)]
        if m.empty:
            return 0, 0.0
        res = (m["winner_name"] == player).astype(int).tolist()
        last = res[-5:]
        wins = int(sum(last))
        ratio = float(wins / 5) if len(last) > 0 else 0.0
        return wins, ratio

    A_wins5, A_ratio5 = last5(A)
    B_wins5, B_ratio5 = last5(B)
    set_if_exists("w_last5_wins", A_wins5)
    set_if_exists("w_last5_ratio", A_ratio5)
    set_if_exists("l_last5_wins", B_wins5)
    set_if_exists("l_last5_ratio", B_ratio5)

    h2h = hist[
        ((hist["winner_name"] == A) & (hist["loser_name"] == B)) |
        ((hist["winner_name"] == B) & (hist["loser_name"] == A))
    ]
    total = int(len(h2h))
    a_wins = int(((h2h["winner_name"] == A) & (h2h["loser_name"] == B)).sum()) if total else 0
    ratio = float(a_wins / total) if total else 0.5  # neutro si no hay historial
    set_if_exists("h2h_total", total)
    set_if_exists("h2h_wins", a_wins)
    set_if_exists("h2h_ratio", ratio)

    h2h_surface = h2h[h2h["surface"] == surface]
    s_total = int(len(h2h_surface))
    s_a_wins = int(((h2h_surface["winner_name"] == A) & (h2h_surface["loser_name"] == B)).sum()) if s_total else 0
    s_ratio = (s_a_wins + 1.0) / (s_total + 2.0)
    set_if_exists("h2h_surface_total", s_total)
    set_if_exists("h2h_surface_wins", s_a_wins)
    set_if_exists("h2h_surface_ratio", float(s_ratio))

    def rest_days(player: str):
        m = hist[(hist["winner_name"] == player) | (hist["loser_name"] == player)]
        if m.empty:
            return 0.0
        last_date = pd.Timestamp(m.iloc[-1]["tourney_date"])
        return _effective_rest_days(float((as_of_ts - last_date).days))

    set_if_exists("w_rest_days", rest_days(A))
    set_if_exists("l_rest_days", rest_days(B))

    set_if_exists("w_recent_form", _recent_form_ratio(hist, A, as_of_ts))
    set_if_exists("l_recent_form", _recent_form_ratio(hist, B, as_of_ts))

    service_features = {
        "w_serve_pct",
        "l_serve_pct",
        "w_bp_save_pct",
        "l_bp_save_pct",
        "w_dominance",
        "l_dominance",
        "serve_pct_diff",
        "bp_save_pct_diff",
        "dominance_diff",
    }
    if service_features.intersection(row):
        a_serve_pct, a_bp_save_pct, a_dominance = _service_snapshot(hist, A)
        b_serve_pct, b_bp_save_pct, b_dominance = _service_snapshot(hist, B)
        set_if_exists("w_serve_pct", a_serve_pct)
        set_if_exists("l_serve_pct", b_serve_pct)
        set_if_exists("w_bp_save_pct", a_bp_save_pct)
        set_if_exists("l_bp_save_pct", b_bp_save_pct)
        set_if_exists("w_dominance", a_dominance)
        set_if_exists("l_dominance", b_dominance)
        set_if_exists("serve_pct_diff", a_serve_pct - b_serve_pct)
        set_if_exists("bp_save_pct_diff", a_bp_save_pct - b_bp_save_pct)
        set_if_exists("dominance_diff", a_dominance - b_dominance)

    X = pd.DataFrame([row]).replace([np.inf, -np.inf], 0).fillna(0)
    return X
