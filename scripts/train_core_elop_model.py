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
MODEL_PATH_CANONICAL = MODEL_DIR / "model_surface_logreg.pkl"
MODEL_PATH_LEGACY = MODEL_DIR / "match_predictor_core_elop.pkl"
SCHEMA_PATH_CANONICAL = MODEL_DIR / "feature_schema_surface_logreg.json"
SCHEMA_PATH_LEGACY = MODEL_DIR / "feature_schema_core_elop.json"

ELO_SCALE = 400.0

CORE_ELOP_FEATURES = ["elo_p_global", "elo_p_surface", "elo_p_blended"]


def elo_expected_from_diff(diff: pd.Series, scale: float = ELO_SCALE) -> pd.Series:
    x = diff.clip(-2000, 2000).astype(float)
    return 1.0 / (1.0 + np.power(10.0, (-x / scale)))


def temporal_sort(df: pd.DataFrame) -> pd.DataFrame:
    if "tourney_date" in df.columns:
        d = df.copy()
        d["tourney_date"] = pd.to_datetime(d["tourney_date"])
        return d.sort_values("tourney_date").reset_index(drop=True)
    return df.reset_index(drop=True)


def augment_original_plus_inverted(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    inv = d.copy()

    # swap w_* y l_*
    w_cols = [c for c in inv.columns if c.startswith("w_")]
    for wc in w_cols:
        lc = "l_" + wc[len("w_"):]
        if lc in inv.columns:
            tmp = inv[wc].copy()
            inv[wc] = inv[lc]
            inv[lc] = tmp

    # invertir diffs
    for col in [
        "elo_diff_global", "elo_diff_surface", "elo_diff_blended",
        "serve_pct_diff", "bp_save_pct_diff", "dominance_diff",
        "age_diff",
    ]:
        if col in inv.columns:
            inv[col] = -inv[col]

    # h2h invertido + ratio neutro
    if "h2h_total" in inv.columns and "h2h_wins" in inv.columns:
        inv["h2h_wins"] = inv["h2h_total"] - inv["h2h_wins"]
    if "h2h_total" in inv.columns and "h2h_ratio" in inv.columns and "h2h_wins" in inv.columns:
        t = inv["h2h_total"].replace(0, np.nan)
        inv["h2h_ratio"] = (inv["h2h_wins"] / t).fillna(0.5)

    if "h2h_surface_total" in inv.columns and "h2h_surface_wins" in inv.columns:
        inv["h2h_surface_wins"] = inv["h2h_surface_total"] - inv["h2h_surface_wins"]
    if "h2h_surface_total" in inv.columns and "h2h_surface_ratio" in inv.columns and "h2h_surface_wins" in inv.columns:
        inv["h2h_surface_ratio"] = ((inv["h2h_surface_wins"] + 1.0) / (inv["h2h_surface_total"] + 2.0)).fillna(0.5)

    d["target"] = 1
    inv["target"] = 0
    return pd.concat([d, inv], ignore_index=True)


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


def build_dataset(df: pd.DataFrame):
    need = ["elo_diff_global", "elo_diff_surface", "elo_diff_blended", "target"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")

    X = df.copy()

    X["elo_p_global"] = elo_expected_from_diff(X["elo_diff_global"])
    X["elo_p_surface"] = elo_expected_from_diff(X["elo_diff_surface"])
    X["elo_p_blended"] = elo_expected_from_diff(X["elo_diff_blended"])

    X = X[CORE_ELOP_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0)
    y = df["target"].astype(int).values
    return X, y


def main():
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"No existe: {FEATURES_PATH}")

    df = pd.read_parquet(FEATURES_PATH)

    df_full = augment_original_plus_inverted(df)

    train_df, val_df, test_df = temporal_split(df_full)

    X_train, y_train = build_dataset(train_df)
    X_val, y_val = build_dataset(val_df)
    X_test, y_test = build_dataset(test_df)

    uniq = set(y_train.tolist())
    if len(uniq) < 2:
        raise ValueError(f"Train sigue teniendo 1 sola clase: {uniq}. Revisa augment/split.")

    clf = LogisticRegression(max_iter=2000, solver="lbfgs", C=0.05)
    clf.fit(X_train, y_train)

    p_val = clf.predict_proba(X_val)[:, 1]
    p_test = clf.predict_proba(X_test)[:, 1]

    print("== CORE_ELOP MODEL METRICS ==")
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
        "feature_names": CORE_ELOP_FEATURES,
        "fillna_value": 0,
        "source": "ELO global, superficie y blended + augmentación simétrica por partido",
        "n_features": len(CORE_ELOP_FEATURES),
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
