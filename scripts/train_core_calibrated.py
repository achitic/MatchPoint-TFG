import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score, brier_score_loss
from sklearn.frozen import FrozenEstimator

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
FEATURES_PATH = PROC_DIR / "features_full.parquet"

MODEL_PATH_CANONICAL = MODEL_DIR / "model_calibrated_logreg.pkl"
MODEL_PATH_LEGACY = MODEL_DIR / "match_predictor_core_calibrated.pkl"
SCHEMA_PATH_CANONICAL = MODEL_DIR / "feature_schema_calibrated_logreg.json"
SCHEMA_PATH_LEGACY = MODEL_DIR / "feature_schema_core_calibrated.json"

ELO_SCALE_TRAIN = 400.0

CORE_FEATURES_ELOP = [
    "elo_p_global", "elo_p_surface", "elo_p_blended",
    "w_last5_ratio", "l_last5_ratio",
    "h2h_total", "h2h_ratio",
    "h2h_surface_total", "h2h_surface_ratio",
    "w_rest_days", "l_rest_days",
    "w_recent_form", "l_recent_form",
    "w_serve_pct", "l_serve_pct",
    "w_bp_save_pct", "l_bp_save_pct",
    "w_dominance", "l_dominance",
    "serve_pct_diff", "bp_save_pct_diff", "dominance_diff",
    "age_diff",
]


def calculate_elo_prob(diff_series):
    """P = 1 / (1 + 10^(-diff/scale)), donde diff = elo_winner - elo_loser."""
    s = pd.Series(diff_series).fillna(0).astype(float)
    s = np.clip(s, -2000, 2000)
    return 1.0 / (1.0 + (10.0 ** (-s / ELO_SCALE_TRAIN)))


def augment_original_plus_inverted(df):
    """
    Duplica el dataset invirtiendo jugadores para tener clases 0 y 1.

    Reglas:
    - swap w_* <-> l_*
    - invertir diffs (elo_diff_*, age_diff)
    - recalcular elo_p_* desde diffs invertidos
    - invertir h2h_ratio para vista opuesta (neutro 0.5 si total=0)
    """
    d = df.copy()
    inv = d.copy()

    if "target" in d.columns:
        d = d.drop(columns=["target"])
    if "target" in inv.columns:
        inv = inv.drop(columns=["target"])

    # La vista invertida intercambia jugador A/B y conserva el mismo partido.
    w_cols = [c for c in inv.columns if c.startswith("w_")]
    for wc in w_cols:
        lc = "l_" + wc[len("w_"):]
        if lc in inv.columns:
            tmp = inv[wc].copy()
            inv[wc] = inv[lc]
            inv[lc] = tmp

    for col in [
        "elo_diff_global", "elo_diff_surface", "elo_diff_blended",
        "serve_pct_diff", "bp_save_pct_diff", "dominance_diff",
        "age_diff",
    ]:
        if col in inv.columns:
            inv[col] = -inv[col]

    # Las probabilidades se recalculan; no basta con invertir el target.
    if "elo_diff_global" in inv.columns:
        inv["elo_p_global"] = calculate_elo_prob(inv["elo_diff_global"])
    if "elo_diff_surface" in inv.columns:
        inv["elo_p_surface"] = calculate_elo_prob(inv["elo_diff_surface"])
    if "elo_diff_blended" in inv.columns:
        inv["elo_p_blended"] = calculate_elo_prob(inv["elo_diff_blended"])

    # Sin historial, el H2H de ambas vistas permanece neutro.
    if "h2h_ratio" in inv.columns and "h2h_total" in inv.columns:
        has_h2h = inv["h2h_total"] > 0
        inv.loc[has_h2h, "h2h_ratio"] = 1.0 - inv.loc[has_h2h, "h2h_ratio"]
        inv.loc[~has_h2h, "h2h_ratio"] = 0.5

    if "h2h_wins" in inv.columns and "h2h_total" in inv.columns:
        inv["h2h_wins"] = inv["h2h_total"] - inv["h2h_wins"]
    if "h2h_surface_wins" in inv.columns and "h2h_surface_total" in inv.columns:
        inv["h2h_surface_wins"] = inv["h2h_surface_total"] - inv["h2h_surface_wins"]
        if "h2h_surface_ratio" in inv.columns:
            inv["h2h_surface_ratio"] = (inv["h2h_surface_wins"] + 1.0) / (inv["h2h_surface_total"] + 2.0)
    elif "h2h_surface_ratio" in inv.columns and "h2h_surface_total" in inv.columns:
        has_h2h_surface = inv["h2h_surface_total"] > 0
        inv.loc[has_h2h_surface, "h2h_surface_ratio"] = 1.0 - inv.loc[has_h2h_surface, "h2h_surface_ratio"]
        inv.loc[~has_h2h_surface, "h2h_surface_ratio"] = 0.5

    d["target"] = 1
    inv["target"] = 0

    return pd.concat([d, inv], ignore_index=True)


def temporal_sort(df):
    """Ordena por fecha para mantener orden temporal."""
    df = df.copy()
    df["tourney_date"] = pd.to_datetime(df["tourney_date"])
    return df.sort_values("tourney_date").reset_index(drop=True)


def temporal_split(df):
    """Partición temporal común: train <=2021, val 2022-2023, test 2024."""
    d = temporal_sort(df)
    dates = pd.to_datetime(d["tourney_date"])
    train = d.loc[dates <= "2021-12-31"].copy()
    val = d.loc[(dates >= "2022-01-01") & (dates <= "2023-12-31")].copy()
    test = d.loc[(dates >= "2024-01-01") & (dates <= "2024-12-31")].copy()
    if train.empty or val.empty or test.empty:
        raise ValueError("La partición temporal 2006-2021/2022-2023/2024 está incompleta")
    return train, val, test


def main():
    print("Entrenando calibrated_logreg con partición temporal")

    print("\n[1/6] Cargando features_full.parquet...")
    df = pd.read_parquet(FEATURES_PATH)
    print(f"   Cargado: {len(df):,} partidos")

    need = ["tourney_date", "elo_diff_global", "elo_diff_surface", "elo_diff_blended"] + [
        "w_last5_ratio", "l_last5_ratio",
        "h2h_total", "h2h_ratio", "w_rest_days", "l_rest_days",
        "h2h_surface_total", "h2h_surface_ratio",
        "w_recent_form", "l_recent_form",
        "w_serve_pct", "l_serve_pct",
        "w_bp_save_pct", "l_bp_save_pct",
        "w_dominance", "l_dominance",
        "serve_pct_diff", "bp_save_pct_diff", "dominance_diff",
        "age_diff",
    ]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en features_full.parquet: {missing}")

    print("\n[2/6] Calculando elo_p_* desde diffs (dataset original)...")
    df = df.copy()
    df["elo_p_global"] = calculate_elo_prob(df["elo_diff_global"])
    df["elo_p_surface"] = calculate_elo_prob(df["elo_diff_surface"])
    df["elo_p_blended"] = calculate_elo_prob(df["elo_diff_blended"])
    print(f"   elo_p_global: min={df['elo_p_global'].min():.3f}, max={df['elo_p_global'].max():.3f}")
    print(f"   elo_p_surface: min={df['elo_p_surface'].min():.3f}, max={df['elo_p_surface'].max():.3f}")

    print("\n[3/6] Augmentación (original + invertido)...")
    df_full = augment_original_plus_inverted(df)
    print(f"   Dataset aumentado: {len(df_full):,} filas")
    print(f"   Distribución target: {df_full['target'].value_counts().to_dict()}")

    print("\n[4/6] Split temporal (train<=2021, val=2022-2023, test=2024)...")
    train, val, test = temporal_split(df_full)
    print(f"   Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    X_train = train[CORE_FEATURES_ELOP].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train = train["target"].astype(int)

    X_val = val[CORE_FEATURES_ELOP].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_val = val["target"].astype(int)

    X_test = test[CORE_FEATURES_ELOP].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_test = test["target"].astype(int)

    print("\n[5/6] Entrenando base LR + calibración temporal...")
    base_clf = LogisticRegression(max_iter=2000, C=0.1, solver="lbfgs", random_state=42)

    print("   Ajuste base LR en train")
    base_clf.fit(X_train, y_train)

    print("   Calibración isotónica en validación")
    cal_clf = CalibratedClassifierCV(estimator=FrozenEstimator(base_clf), method="isotonic")
    cal_clf.fit(X_val, y_val)

    print("\n[6/6] Evaluación...")

    p_val = cal_clf.predict_proba(X_val)[:, 1]
    val_loss = log_loss(y_val, p_val)
    val_auc = roc_auc_score(y_val, p_val)
    val_brier = brier_score_loss(y_val, p_val)

    p_test = cal_clf.predict_proba(X_test)[:, 1]
    test_loss = log_loss(y_test, p_test)
    test_auc = roc_auc_score(y_test, p_test)
    test_brier = brier_score_loss(y_test, p_test)
    test_accuracy = accuracy_score(y_test, p_test >= 0.5)

    print(f"{'Dataset':<10} {'LogLoss':<10} {'AUC':<10} {'Brier':<10}")
    print(f"{'Val':<10} {val_loss:<10.5f} {val_auc:<10.5f} {val_brier:<10.5f}")
    print(f"{'Test':<10} {test_loss:<10.5f} {test_auc:<10.5f} {test_brier:<10.5f}")

    print("\nDistribución de probabilidades predichas (test):")
    percentiles = [0, 10, 25, 50, 75, 90, 100]
    perc_vals = np.percentile(p_test, percentiles)
    for p, v in zip(percentiles, perc_vals):
        print(f"   p{p:>3}: {v:.4f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(cal_clf, MODEL_PATH_CANONICAL)
    joblib.dump(cal_clf, MODEL_PATH_LEGACY)

    schema = {
        "feature_names": CORE_FEATURES_ELOP,
        "note": "CORE_CALIBRATED: LR + Isotonic calibrado temporalmente (fit base en train, calibración en val)",
        "elo_scale": ELO_SCALE_TRAIN,
        "calibration_method": "isotonic",
        "base_model": "LogisticRegression(C=0.1) with reduced collinearity feature set",
        "temporal_protocol": "train<=2021 -> calibrate=2022-2023 -> test=2024",
        "metrics_test": {
            "accuracy": float(test_accuracy),
            "log_loss": float(test_loss),
            "auc": float(test_auc),
            "brier": float(test_brier),
        },
    }
    schema_payload = json.dumps(schema, indent=2, ensure_ascii=False)
    SCHEMA_PATH_CANONICAL.write_text(schema_payload, encoding="utf-8")
    SCHEMA_PATH_LEGACY.write_text(schema_payload, encoding="utf-8")

    print(f"\nOK: modelo canónico guardado en: {MODEL_PATH_CANONICAL}")
    print(f"OK: modelo legacy guardado en: {MODEL_PATH_LEGACY}")
    print(f"OK: schema canónico guardado en: {SCHEMA_PATH_CANONICAL}")
    print(f"OK: schema legacy guardado en: {SCHEMA_PATH_LEGACY}")
    print("Entrenamiento completado")


if __name__ == "__main__":
    main()




