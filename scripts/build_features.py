from pathlib import Path
import pandas as pd
import numpy as np
from collections import defaultdict, deque

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"

INIT_ELO = 1500.0
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


def _effective_rest_days(days: float) -> float:
    """
    Convert raw calendar days into an "effective rest" signal:
    - Fast gain on first 1-3 days
    - Plateau
    - Soft rust penalty for long layoffs
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


def _extract_serve_line(row: pd.Series, prefix: str, opp_prefix: str) -> dict[str, float]:
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
    dominance = _ratio(return_won, opp_return_won, DEFAULT_DOMINANCE)

    return {
        "service_won": service_won,
        "service_total": svpt,
        "bp_saved": bp_saved,
        "bp_faced": bp_faced,
        "dominance": dominance,
        "has_dominance": 1.0 if svpt > 0 and opp_svpt > 0 else 0.0,
    }


def load_matches() -> pd.DataFrame:
    path = PROC_DIR / "matches_clean.parquet"
    df = pd.read_parquet(path)
    if "tourney_date" not in df.columns:
        raise ValueError("matches_clean.parquet debe tener columna 'tourney_date'")
    df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    df["surface"] = df["surface"].astype(str).str.title()
    df = df.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)
    df["match_row_id"] = np.arange(len(df), dtype=np.int64)
    return df


def load_elo_history() -> pd.DataFrame:
    path = PROC_DIR / "elo_history.csv"
    df = pd.read_csv(path)

    required = {
        "date", "surface", "winner", "loser",
        "elo_w_before", "elo_l_before",
        "elo_w_after", "elo_l_after",
        "elo_w_surface_after", "elo_l_surface_after",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"elo_history.csv no tiene columnas requeridas: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df["surface"] = df["surface"].astype(str).str.title()
    df = df.sort_values("date", kind="mergesort").reset_index(drop=True)

    for c in ["elo_w_before", "elo_l_before", "elo_w_surface_after", "elo_l_surface_after"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def reconstruct_surface_before(elo_hist: pd.DataFrame) -> pd.DataFrame:
    """
    elo_history.csv tiene elo_*_surface_after pero no before.
    Reconstruimos before trackeando el último 'after' por (player, surface).
    """
    last_surf = defaultdict(lambda: INIT_ELO)

    w_before = np.zeros(len(elo_hist), dtype=float)
    l_before = np.zeros(len(elo_hist), dtype=float)

    winners = elo_hist["winner"].tolist()
    losers = elo_hist["loser"].tolist()
    surfs = elo_hist["surface"].tolist()
    w_after = elo_hist["elo_w_surface_after"].to_numpy()
    l_after = elo_hist["elo_l_surface_after"].to_numpy()

    for i in range(len(elo_hist)):
        w = winners[i]
        l = losers[i]
        s = surfs[i]

        w_before[i] = float(last_surf[(w, s)])
        l_before[i] = float(last_surf[(l, s)])

        # El estado se actualiza después de guardar la observación prepartido.
        if not np.isnan(w_after[i]):
            last_surf[(w, s)] = float(w_after[i])
        if not np.isnan(l_after[i]):
            last_surf[(l, s)] = float(l_after[i])

        if (i + 1) % 50000 == 0:
            print(f"   ... reconstruyendo surface_before {i+1:,}/{len(elo_hist):,}")

    out = elo_hist.copy()
    out["elo_w_surface_before"] = w_before
    out["elo_l_surface_before"] = l_before
    return out


def compute_last5(df: pd.DataFrame) -> pd.DataFrame:
    recent = defaultdict(list)
    w_last5_wins = np.zeros(len(df), dtype=int)
    l_last5_wins = np.zeros(len(df), dtype=int)

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()

    for i in range(len(df)):
        w = winners[i]
        l = losers[i]

        # Instantánea estrictamente prepartido: el resultado actual se añade después.
        w_last5_wins[i] = int(sum(recent[w][-5:]))
        l_last5_wins[i] = int(sum(recent[l][-5:]))

        recent[w].append(1)
        recent[l].append(0)

        if (i + 1) % 50000 == 0:
            print(f"   ... last5 {i+1:,}/{len(df):,}")

    df["w_last5_wins"] = w_last5_wins
    df["l_last5_wins"] = l_last5_wins
    df["w_last5_ratio"] = df["w_last5_wins"] / 5.0
    df["l_last5_ratio"] = df["l_last5_wins"] / 5.0
    return df


def compute_h2h(df: pd.DataFrame) -> pd.DataFrame:
    h2h = defaultdict(lambda: defaultdict(int))
    h2h_total = np.zeros(len(df), dtype=int)
    h2h_wins = np.zeros(len(df), dtype=int)

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()

    for i in range(len(df)):
        A = winners[i]
        B = losers[i]

        total = h2h[A][B] + h2h[B][A]
        winsA = h2h[A][B]

        h2h_total[i] = total
        h2h_wins[i] = winsA

        h2h[A][B] += 1

        if (i + 1) % 50000 == 0:
            print(f"   ... h2h {i+1:,}/{len(df):,}")

    df["h2h_total"] = h2h_total
    df["h2h_wins"] = h2h_wins
    df["h2h_ratio"] = np.where(df["h2h_total"] > 0, df["h2h_wins"] / df["h2h_total"], 0.5)
    return df


def compute_h2h_surface(df: pd.DataFrame) -> pd.DataFrame:
    """
    Surface-specific H2H with Laplace smoothing:
    ratio = (wins + 1) / (total + 2)
    """
    h2h_surface = defaultdict(int)
    totals = np.zeros(len(df), dtype=int)
    wins = np.zeros(len(df), dtype=int)

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()
    surfaces = df["surface"].astype(str).str.title().tolist()

    for i in range(len(df)):
        A = winners[i]
        B = losers[i]
        s = surfaces[i]

        key_ab = (s, A, B)
        key_ba = (s, B, A)
        total = h2h_surface[key_ab] + h2h_surface[key_ba]
        win_a = h2h_surface[key_ab]

        totals[i] = total
        wins[i] = win_a

        h2h_surface[key_ab] += 1

        if (i + 1) % 50000 == 0:
            print(f"   ... h2h_surface {i+1:,}/{len(df):,}")

    df["h2h_surface_total"] = totals
    df["h2h_surface_wins"] = wins
    df["h2h_surface_ratio"] = (df["h2h_surface_wins"] + 1.0) / (df["h2h_surface_total"] + 2.0)
    return df


def compute_rest_days(df: pd.DataFrame) -> pd.DataFrame:
    last_played = {}
    w_rest = np.zeros(len(df), dtype=float)
    l_rest = np.zeros(len(df), dtype=float)

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()
    dates = df["tourney_date"].tolist()

    for i in range(len(df)):
        w = winners[i]
        l = losers[i]
        d = dates[i]

        w_days = (d - last_played[w]).days if w in last_played else 0.0
        l_days = (d - last_played[l]).days if l in last_played else 0.0
        w_rest[i] = _effective_rest_days(w_days)
        l_rest[i] = _effective_rest_days(l_days)

        last_played[w] = d
        last_played[l] = d

        if (i + 1) % 50000 == 0:
            print(f"   ... rest_days {i+1:,}/{len(df):,}")

    df["w_rest_days"] = w_rest
    df["l_rest_days"] = l_rest
    return df


def compute_recent_form(df: pd.DataFrame) -> pd.DataFrame:
    """
    Exponentially decayed win-rate over the last RECENCY_WINDOW_DAYS.
    Uses half-life RECENCY_HALFLIFE_DAYS so recent matches weigh more.
    """
    history = defaultdict(deque)  # player -> deque[(date, win_flag)]
    w_recent = np.zeros(len(df), dtype=float)
    l_recent = np.zeros(len(df), dtype=float)

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()
    dates = df["tourney_date"].tolist()

    def _ratio(player: str, current_date: pd.Timestamp) -> float:
        entries = history[player]
        while entries and (current_date - entries[0][0]).days > RECENCY_WINDOW_DAYS:
            entries.popleft()
        if not entries:
            return 0.5

        w_sum = 0.0
        p_sum = 0.0
        for dt, win_flag in entries:
            w = _decay_weight((current_date - dt).days)
            w_sum += w
            p_sum += w * float(win_flag)
        return p_sum / w_sum if w_sum > 0 else 0.5

    for i in range(len(df)):
        w = winners[i]
        l = losers[i]
        d = dates[i]

        w_recent[i] = _ratio(w, d)
        l_recent[i] = _ratio(l, d)

        history[w].append((d, 1))
        history[l].append((d, 0))

        if (i + 1) % 50000 == 0:
            print(f"   ... recent_form {i+1:,}/{len(df):,}")

    df["w_recent_form"] = w_recent
    df["l_recent_form"] = l_recent
    return df


def compute_serve_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling service features without leakage.

    For each player, rates are computed before the current match and shrunk
    toward the historical global prior available at that point. The match is
    added to the rolling state only after both player snapshots are stored.
    """
    required = {
        "w_svpt", "w_1stWon", "w_2ndWon", "w_bpSaved", "w_bpFaced",
        "l_svpt", "l_1stWon", "l_2ndWon", "l_bpSaved", "l_bpFaced",
    }
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        print(f"   Serve stats: faltan columnas {missing}; se usan priors neutros")
        df["w_serve_pct"] = DEFAULT_SERVE_PCT
        df["l_serve_pct"] = DEFAULT_SERVE_PCT
        df["w_bp_save_pct"] = DEFAULT_BP_SAVE_PCT
        df["l_bp_save_pct"] = DEFAULT_BP_SAVE_PCT
        df["w_dominance"] = DEFAULT_DOMINANCE
        df["l_dominance"] = DEFAULT_DOMINANCE
        df["serve_pct_diff"] = 0.0
        df["bp_save_pct_diff"] = 0.0
        df["dominance_diff"] = 0.0
        return df

    player_state = defaultdict(lambda: {
        "service_won": 0.0,
        "service_total": 0.0,
        "bp_saved": 0.0,
        "bp_faced": 0.0,
        "dominance_sum": 0.0,
        "dominance_n": 0.0,
    })
    global_state = {
        "service_won": 0.0,
        "service_total": 0.0,
        "bp_saved": 0.0,
        "bp_faced": 0.0,
        "dominance_sum": 0.0,
        "dominance_n": 0.0,
    }

    w_serve = np.zeros(len(df), dtype=float)
    l_serve = np.zeros(len(df), dtype=float)
    w_bp = np.zeros(len(df), dtype=float)
    l_bp = np.zeros(len(df), dtype=float)
    w_dom = np.zeros(len(df), dtype=float)
    l_dom = np.zeros(len(df), dtype=float)

    def priors() -> tuple[float, float, float]:
        serve_prior = _ratio(global_state["service_won"], global_state["service_total"], DEFAULT_SERVE_PCT)
        bp_prior = _ratio(global_state["bp_saved"], global_state["bp_faced"], DEFAULT_BP_SAVE_PCT)
        dom_prior = _ratio(global_state["dominance_sum"], global_state["dominance_n"], DEFAULT_DOMINANCE)
        return serve_prior, bp_prior, dom_prior

    def snapshot(player: str) -> tuple[float, float, float]:
        st = player_state[player]
        serve_prior, bp_prior, dom_prior = priors()
        serve_pct = _shrunk_rate(
            st["service_won"], st["service_total"], serve_prior, SERVE_SHRINKAGE_POINTS
        )
        bp_save_pct = _shrunk_rate(
            st["bp_saved"], st["bp_faced"], bp_prior, BP_SHRINKAGE_POINTS
        )
        dominance = _shrunk_rate(
            st["dominance_sum"], st["dominance_n"], dom_prior, DOMINANCE_SHRINKAGE_MATCHES
        )
        return serve_pct, bp_save_pct, dominance

    def update(player: str, line: dict[str, float]) -> None:
        st = player_state[player]
        st["service_won"] += line["service_won"]
        st["service_total"] += line["service_total"]
        st["bp_saved"] += line["bp_saved"]
        st["bp_faced"] += line["bp_faced"]
        if line["has_dominance"]:
            st["dominance_sum"] += line["dominance"]
            st["dominance_n"] += 1.0

        global_state["service_won"] += line["service_won"]
        global_state["service_total"] += line["service_total"]
        global_state["bp_saved"] += line["bp_saved"]
        global_state["bp_faced"] += line["bp_faced"]
        if line["has_dominance"]:
            global_state["dominance_sum"] += line["dominance"]
            global_state["dominance_n"] += 1.0

    winners = df["winner_name"].tolist()
    losers = df["loser_name"].tolist()

    for i, (_, row) in enumerate(df.iterrows()):
        w = winners[i]
        l = losers[i]

        w_serve[i], w_bp[i], w_dom[i] = snapshot(w)
        l_serve[i], l_bp[i], l_dom[i] = snapshot(l)

        update(w, _extract_serve_line(row, "w", "l"))
        update(l, _extract_serve_line(row, "l", "w"))

        if (i + 1) % 50000 == 0:
            print(f"   ... serve_stats {i+1:,}/{len(df):,}")

    df["w_serve_pct"] = w_serve
    df["l_serve_pct"] = l_serve
    df["w_bp_save_pct"] = w_bp
    df["l_bp_save_pct"] = l_bp
    df["w_dominance"] = w_dom
    df["l_dominance"] = l_dom
    df["serve_pct_diff"] = df["w_serve_pct"] - df["l_serve_pct"]
    df["bp_save_pct_diff"] = df["w_bp_save_pct"] - df["l_bp_save_pct"]
    df["dominance_diff"] = df["w_dominance"] - df["l_dominance"]
    return df


def main():
    out_path = PROC_DIR / "features_full.parquet"

    print("[1/6] Cargando matches_clean.parquet")
    df = load_matches()
    print(f"   OK: filas={len(df):,}")

    print("[2/6] Cargando elo_history.csv")
    elo_hist = load_elo_history()
    print(f"   OK: filas={len(elo_hist):,}")

    print("[3/6] Reconstruyendo elo_surface_before (pre-partido)")
    elo_hist = reconstruct_surface_before(elo_hist)
    print("   OK: surface_before listo")

    print("[4/6] Alineando ELO pre-match uno-a-uno (sin leakage)")
    if "match_row_id" not in elo_hist.columns:
        raise ValueError("elo_history.csv debe regenerarse con match_row_id")
    if len(df) != len(elo_hist):
        raise ValueError(f"Desalineación matches/ELO: {len(df)} != {len(elo_hist)}")

    aligned = (
        df["match_row_id"].to_numpy() == elo_hist["match_row_id"].to_numpy()
    ) & (
        df["tourney_date"].to_numpy() == elo_hist["date"].to_numpy()
    ) & (
        df["surface"].astype(str).to_numpy() == elo_hist["surface"].astype(str).to_numpy()
    ) & (
        df["winner_name"].astype(str).to_numpy() == elo_hist["winner"].astype(str).to_numpy()
    ) & (
        df["loser_name"].astype(str).to_numpy() == elo_hist["loser"].astype(str).to_numpy()
    )
    if not bool(np.all(aligned)):
        first_bad = int(np.flatnonzero(~aligned)[0])
        raise ValueError(f"Histórico ELO desalineado en match_row_id={first_bad}")

    elo_cols = [
        "elo_w_before", "elo_l_before",
        "elo_w_surface_before", "elo_l_surface_before",
    ]
    if "elo_w_blended_before" in elo_hist.columns:
        elo_cols += ["elo_w_blended_before", "elo_l_blended_before"]
    for col in elo_cols:
        df[col] = elo_hist[col].to_numpy()

    miss_g = float(df["elo_w_before"].isna().mean())
    miss_s = float(df["elo_w_surface_before"].isna().mean())
    print(f"   Missing global pre-match: {miss_g:.2%}")
    print(f"   Missing surface pre-match: {miss_s:.2%}")

    df["elo_w_before"] = df["elo_w_before"].fillna(INIT_ELO)
    df["elo_l_before"] = df["elo_l_before"].fillna(INIT_ELO)
    df["elo_w_surface_before"] = df["elo_w_surface_before"].fillna(INIT_ELO)
    df["elo_l_surface_before"] = df["elo_l_surface_before"].fillna(INIT_ELO)

    df["elo_diff_global"] = df["elo_w_before"] - df["elo_l_before"]
    df["elo_diff_surface"] = df["elo_w_surface_before"] - df["elo_l_surface_before"]

    # La mezcla 50/50 regulariza el Elo de superficies con pocas observaciones.
    if "elo_w_blended_before" in df.columns:
        df["elo_w_blended_before"] = df["elo_w_blended_before"].fillna(
            0.5 * df["elo_w_before"] + 0.5 * df["elo_w_surface_before"]
        )
        df["elo_l_blended_before"] = df["elo_l_blended_before"].fillna(
            0.5 * df["elo_l_before"] + 0.5 * df["elo_l_surface_before"]
        )
    else:
        df["elo_w_blended_before"] = 0.5 * df["elo_w_before"] + 0.5 * df["elo_w_surface_before"]
        df["elo_l_blended_before"] = 0.5 * df["elo_l_before"] + 0.5 * df["elo_l_surface_before"]
    df["elo_diff_blended"] = df["elo_w_blended_before"] - df["elo_l_blended_before"]
    ELO_SCALE = 400.0
    df["elo_p_blended"] = 1.0 / (1.0 + 10.0 ** (-df["elo_diff_blended"] / ELO_SCALE))
    print("   Blended ELO: elo_diff_blended, elo_p_blended")

    print("[5/6] Calculando last5 + h2h + h2h_surface + rest_days + recency + serve_stats (orden temporal)")
    df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    df = df.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    df = compute_last5(df)
    df = compute_h2h(df)
    df = compute_h2h_surface(df)
    df = compute_rest_days(df)
    df = compute_recent_form(df)
    df = compute_serve_stats(df)

    if "winner_age" in df.columns and "loser_age" in df.columns:
        df["age_diff"] = df["winner_age"] - df["loser_age"]
    else:
        df["age_diff"] = 0.0

    df["target"] = 1

    print("[6/6] Guardando features_full.parquet")
    df.to_parquet(out_path, index=False)
    print(f"OK: guardado {out_path} | filas={len(df):,} | cols={len(df.columns)}")


if __name__ == "__main__":
    main()
