from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"

FEATURES_PATH = PROC_DIR / "features_full.parquet"
MODEL_PATH_CANONICAL = MODEL_DIR / "model_baseline_logreg.pkl"
MODEL_PATH_LEGACY = MODEL_DIR / "match_predictor_core.pkl"
SCHEMA_PATH_CANONICAL = MODEL_DIR / "feature_schema_baseline_logreg.json"
SCHEMA_PATH_LEGACY = MODEL_DIR / "feature_schema_core.json"


CORE_FEATURES = ["elo_p_global"]
ELO_SCALE = 400.0


def temporal_sort(df: pd.DataFrame) -> pd.DataFrame:
    if "tourney_date" in df.columns:
        d = df.copy()
        d["tourney_date"] = pd.to_datetime(d["tourney_date"])
        return d.sort_values("tourney_date").reset_index(drop=True)
    return df.reset_index(drop=True)


def augment_original_plus_inverted(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte un dataset con target=1 (winner-side gana) en uno balanceado:
    - original: A=winner, B=loser, target=1
    - invertido: swap winner/loser, invierte diffs, target=0
    """
    d = df.copy()

    inv = d.copy()

    # swap winner_* y loser_* si existen (por seguridad, aunque CORE no las use)
    winner_cols = [c for c in inv.columns if c.startswith("winner_")]
    loser_cols = [c for c in inv.columns if c.startswith("loser_")]
    for wc in winner_cols:
        lc = "loser_" + wc[len("winner_"):]
        if lc in inv.columns:
            tmp = inv[wc].copy()
            inv[wc] = inv[lc]
            inv[lc] = tmp

    # swap w_* y l_* (forma/descanso)
    w_cols = [c for c in inv.columns if c.startswith("w_")]
    for wc in w_cols:
        lc = "l_" + wc[len("w_"):]
        if lc in inv.columns:
            tmp = inv[wc].copy()
            inv[wc] = inv[lc]
            inv[lc] = tmp

    # invertir diffs que estén presentes
    for col in [
        "elo_diff_global", "elo_diff_surface",
        "serve_pct_diff", "bp_save_pct_diff", "dominance_diff",
        "age_diff",
    ]:
        if col in inv.columns:
            inv[col] = -inv[col]

    # h2h_wins desde el punto de vista del winner-side
    # si en original h2h_total = t, h2h_wins = wins_del_winner
    # en invertido, wins_del_nuevo_winner = t - wins_original
    if "h2h_total" in inv.columns and "h2h_wins" in inv.columns:
        inv["h2h_wins"] = inv["h2h_total"] - inv["h2h_wins"]

    # h2h_ratio coherente
    if "h2h_total" in inv.columns and "h2h_ratio" in inv.columns and "h2h_wins" in inv.columns:
        t = inv["h2h_total"].replace(0, np.nan)
        inv["h2h_ratio"] = (inv["h2h_wins"] / t).fillna(0.0)

    # target invertido
    if "target" in inv.columns:
        inv["target"] = 0
    else:
        inv["target"] = 0

    # original target = 1 (asegurar)
    d["target"] = 1

    full = pd.concat([d, inv], ignore_index=True)
    return full


def temporal_split(df: pd.DataFrame):
    """Partición temporal común: train <=2021, val 2022-2023, test 2024."""
    d = temporal_sort(df)
    dates = pd.to_datetime(d["tourney_date"])
    train = d.loc[dates <= "2021-12-31"].copy()
    val = d.loc[(dates >= "2022-01-01") & (dates <= "2023-12-31")].copy()
    test = d.loc[(dates >= "2024-01-01") & (dates <= "2024-12-31")].copy()
    if train.empty or val.empty or test.empty:
        raise ValueError("La partición temporal 2006-2021/2022-2023/2024 está incompleta")
    return train, val, test


def build_core_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    missing = [c for c in ["elo_diff_global", "target"] if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")

    diff = pd.to_numeric(df["elo_diff_global"], errors="coerce").fillna(0.0).clip(-2000, 2000)
    X = pd.DataFrame(
        {"elo_p_global": 1.0 / (1.0 + np.power(10.0, -diff / ELO_SCALE))},
        index=df.index,
    )
    y = df["target"].astype(int).values
    return X, y


def main():
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"No existe: {FEATURES_PATH}")

    df = pd.read_parquet(FEATURES_PATH)

    # Aumentar para tener 0/1
    df_full = augment_original_plus_inverted(df)

    # Split temporal
    train_df, val_df, test_df = temporal_split(df_full)

    X_train, y_train = build_core_dataset(train_df)
    X_val, y_val = build_core_dataset(val_df)
    X_test, y_test = build_core_dataset(test_df)

    uniq = set(y_train.tolist())
    if len(uniq) < 2:
        raise ValueError(f"Train sigue teniendo 1 sola clase: {uniq}. Revisa augment/split.")

    clf = LogisticRegression(max_iter=2000, solver="lbfgs")
    clf.fit(X_train, y_train)

    p_val = clf.predict_proba(X_val)[:, 1]
    p_test = clf.predict_proba(X_test)[:, 1]

    print("== CORE MODEL METRICS ==")
    val_loss = log_loss(y_val, p_val)
    val_auc = roc_auc_score(y_val, p_val)
    val_brier = brier_score_loss(y_val, p_val)
    test_loss = log_loss(y_test, p_test)
    test_auc = roc_auc_score(y_test, p_test)
    test_brier = brier_score_loss(y_test, p_test)
    test_accuracy = accuracy_score(y_test, p_test >= 0.5)
    print(f"Val   LogLoss: {val_loss:.5f} | AUC: {val_auc:.5f} | Brier: {val_brier:.5f}")
    print(f"Test  LogLoss: {test_loss:.5f} | AUC: {test_auc:.5f} | Brier: {test_brier:.5f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODEL_PATH_CANONICAL)
    joblib.dump(clf, MODEL_PATH_LEGACY)

    schema = {
        "feature_names": CORE_FEATURES,
        "fillna_value": 0,
        "source": "Baseline ELO global + augmentación simétrica por partido",
        "n_features": len(CORE_FEATURES),
        "elo_scale": ELO_SCALE,
        "temporal_protocol": "train<=2021; validation=2022-2023; test=2024",
        "metrics_test": {
            "accuracy": float(test_accuracy),
            "log_loss": float(test_loss),
            "auc": float(test_auc),
            "brier": float(test_brier),
        },
    }
    schema_payload = json.dumps(schema, ensure_ascii=False, indent=2)
    SCHEMA_PATH_CANONICAL.write_text(schema_payload, encoding="utf-8")
    SCHEMA_PATH_LEGACY.write_text(schema_payload, encoding="utf-8")

    print(f"\nOK: modelo canónico guardado en {MODEL_PATH_CANONICAL}")
    print(f"OK: modelo legacy guardado en {MODEL_PATH_LEGACY}")
    print(f"OK: schema canónico guardado en {SCHEMA_PATH_CANONICAL}")
    print(f"OK: schema legacy guardado en {SCHEMA_PATH_LEGACY}")


if __name__ == "__main__":
    main()
