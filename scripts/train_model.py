# scripts/train_model.py
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBClassifier
import lightgbm as lgb
from catboost import CatBoostClassifier


BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)


# Features that are stable and can be reconstructed at inference time.
# We intentionally exclude identity/context leakage columns (e.g. winner_id).
STACKING_FEATURES = [
    "winner_age",
    "loser_age",
    "winner_rank",
    "winner_rank_points",
    "loser_rank",
    "loser_rank_points",
    "elo_w_before",
    "elo_l_before",
    "elo_w_surface_before",
    "elo_l_surface_before",
    "elo_diff_global",
    "elo_diff_surface",
    "elo_w_blended_before",
    "elo_l_blended_before",
    "elo_diff_blended",
    "w_last5_wins",
    "l_last5_wins",
    "w_last5_ratio",
    "l_last5_ratio",
    "h2h_total",
    "h2h_wins",
    "h2h_ratio",
    "w_rest_days",
    "l_rest_days",
    "w_serve_pct",
    "l_serve_pct",
    "w_bp_save_pct",
    "l_bp_save_pct",
    "w_dominance",
    "l_dominance",
    "serve_pct_diff",
    "bp_save_pct_diff",
    "dominance_diff",
    "age_diff",
]


def load_data() -> pd.DataFrame:
    path = PROC_DIR / "features_full.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}")
    df = pd.read_parquet(path)

    if not np.issubdtype(df["tourney_date"].dtype, np.datetime64):
        df["tourney_date"] = pd.to_datetime(df["tourney_date"])

    df = df.sort_values("tourney_date").reset_index(drop=True)
    return df


def invert_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera la versión invertida del partido:
    A <-> B y target = 0.
    """
    df_inv = df.copy()

    def _swap_by_prefix(prefix_a: str, prefix_b: str):
        cols_a = [c for c in df.columns if c.startswith(prefix_a)]
        for col_a in cols_a:
            col_b = prefix_b + col_a[len(prefix_a):]
            if col_b in df.columns:
                tmp = df_inv[col_a].copy()
                df_inv[col_a] = df_inv[col_b]
                df_inv[col_b] = tmp

    # Swap all winner/loser, w/l and elo_w/elo_l prefixed columns.
    _swap_by_prefix("winner_", "loser_")
    _swap_by_prefix("w_", "l_")
    _swap_by_prefix("elo_w_", "elo_l_")

    # Invert directional diffs.
    if "elo_diff_global" in df.columns:
        df_inv["elo_diff_global"] = -df["elo_diff_global"]
    if "elo_diff_surface" in df.columns:
        df_inv["elo_diff_surface"] = -df["elo_diff_surface"]
    if "elo_diff_blended" in df.columns:
        df_inv["elo_diff_blended"] = -df["elo_diff_blended"]
    if "serve_pct_diff" in df.columns:
        df_inv["serve_pct_diff"] = -df["serve_pct_diff"]
    if "bp_save_pct_diff" in df.columns:
        df_inv["bp_save_pct_diff"] = -df["bp_save_pct_diff"]
    if "dominance_diff" in df.columns:
        df_inv["dominance_diff"] = -df["dominance_diff"]

    # edad (diferencia)
    if "age_diff" in df.columns:
        df_inv["age_diff"] = -df["age_diff"]

    # head-to-head
    if {"h2h_total", "h2h_wins"}.issubset(df.columns):
        df_inv["h2h_wins"] = df["h2h_total"] - df["h2h_wins"]
        h2h_total_safe = df["h2h_total"].replace(0, np.nan)
        df_inv["h2h_ratio"] = (df_inv["h2h_wins"] / h2h_total_safe).fillna(0.5)

    # etiqueta invertida
    df_inv["target"] = 0

    return df_inv


def build_full_dataset(df: pd.DataFrame):
    """
    Dataset original (target=1) + invertido (target=0),
    ordenado temporalmente y con pares (partido, vista).
    """
    df_pos = df.copy().reset_index(drop=True)
    df_pos["target"] = 1
    df_pos["pair_id"] = df_pos.index
    df_pos["view"] = 0  # A gana

    df_neg = invert_rows(df_pos.copy())
    df_neg["pair_id"] = df_pos["pair_id"]
    df_neg["view"] = 1  # B gana

    df_full = pd.concat([df_pos, df_neg], ignore_index=True)

    # orden temporal + emparejar vistas (1 y 0 del mismo partido)
    df_full = df_full.sort_values(
        ["tourney_date", "pair_id", "view"]
    ).reset_index(drop=True)

    missing = [f for f in STACKING_FEATURES if f not in df_full.columns]
    if missing:
        raise ValueError(f"Faltan features esperadas para stacking: {missing}")

    X = df_full[STACKING_FEATURES].fillna(0)
    y = df_full["target"]

    return df_full, X, y, STACKING_FEATURES


def temporal_split(df_full: pd.DataFrame, X: pd.DataFrame, y: pd.Series):
    """
    Splits temporales:
      - train:   <= 2021-12-31
      - val:     2022-01-01 – 2023-12-31
      - test:    >= 2024-01-01
    """
    dates = df_full["tourney_date"]

    train_end = pd.Timestamp("2021-12-31")
    val_start = pd.Timestamp("2022-01-01")
    val_end = pd.Timestamp("2023-12-31")
    test_start = pd.Timestamp("2024-01-01")

    train_mask = dates <= train_end
    val_mask = (dates >= val_start) & (dates <= val_end)
    test_mask = dates >= test_start

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


def evaluate_model(name, model, X_val, y_val):
    proba = model.predict_proba(X_val)[:, 1]
    acc = accuracy_score(y_val, proba > 0.5)
    ll = log_loss(y_val, proba, labels=[0, 1])
    auc = roc_auc_score(y_val, proba)
    brier = brier_score_loss(y_val, proba)
    print(f"\n{name}")
    print(f"  Accuracy: {acc:.4f}")
    print(f"  LogLoss:  {ll:.4f}")
    print(f"  AUC:      {auc:.4f}")
    print(f"  Brier:    {brier:.4f}")
    return {"accuracy": acc, "logloss": ll, "auc": auc, "brier": brier}


def train_baselines(X_train, y_train, X_val, y_val):
    results = {}

    # 1. Regresión logística
    logreg = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, random_state=42),
    )
    logreg.fit(X_train, y_train)
    results["logreg"] = {
        "model": logreg,
        **evaluate_model("LogisticRegression", logreg, X_val, y_val),
    }

    # 2. Random Forest
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)
    results["random_forest"] = {
        "model": rf,
        **evaluate_model("RandomForest", rf, X_val, y_val),
    }

    # 3. XGBoost
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        n_jobs=-1,
        random_state=42,
    )
    xgb.fit(X_train, y_train)
    results["xgboost"] = {
        "model": xgb,
        **evaluate_model("XGBoost", xgb, X_val, y_val),
    }

    # 4. LightGBM
    lgbm = lgb.LGBMClassifier(
        n_estimators=400,
        max_depth=-1,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42,
    )
    lgbm.fit(X_train, y_train)
    results["lightgbm"] = {
        "model": lgbm,
        **evaluate_model("LightGBM", lgbm, X_val, y_val),
    }

    # 5. CatBoost
    cat = CatBoostClassifier(
        depth=6,
        learning_rate=0.1,
        iterations=300,
        loss_function="Logloss",
        verbose=False,
        random_state=42,
    )
    cat.fit(X_train, y_train)
    results["catboost"] = {
        "model": cat,
        **evaluate_model("CatBoost", cat, X_val, y_val),
    }

    return results


def train_stacking(estimators, final_estimator, X_meta, y_meta, X_test, y_test):
    """Ajusta el meta-modelo en validación con bases prefiteadas solo en train."""
    stack = StackingClassifier(
        estimators=estimators,
        final_estimator=final_estimator,
        stack_method="predict_proba",
        cv="prefit",
        n_jobs=-1,
    )
    stack.fit(X_meta, y_meta)
    _ = evaluate_model("STACKING (test 2024)", stack, X_test, y_test)
    return stack


def main():
    print("Cargando datos...")
    df = load_data()

    print("Construyendo dataset completo (original + invertido)...")
    df_full, X_all, y_all, features = build_full_dataset(df)
    print(f"Número de filas tras augmentación: {len(df_full)}")
    print(f"Número de features numéricas: {len(features)}")

    (X_train, y_train), (X_val, y_val), (X_test, y_test) = temporal_split(df_full, X_all, y_all)
    print(f"Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")

    print("\nEntrenando modelos baseline...")
    results = train_baselines(X_train, y_train, X_val, y_val)

    sorted_models = sorted(results.items(), key=lambda kv: kv[1]["logloss"])
    top2 = sorted_models[:2]

    print("\nTop-2 modelos baseline por LogLoss:")
    for name, res in top2:
        print(f"- {name}: LogLoss={res['logloss']:.4f}, AUC={res['auc']:.4f}, Brier={res['brier']:.4f}")

    selected_models = {name: res["model"] for name, res in top2}

    print("\nEvaluación de candidatos seleccionados en test 2024:")
    for name, model in selected_models.items():
        print(f"\nModelo seleccionado: {name}")
        _ = evaluate_model(name + " (test)", model, X_test, y_test)

    estimators = [(name, model) for name, model in selected_models.items()]
    final_est = LogisticRegression(max_iter=2000, random_state=42)

    print("\nEntrenando meta-modelo en validación con bases prefiteadas en train...")
    stack_model = train_stacking(estimators, final_est, X_val, y_val, X_test, y_test)

    canonical_path = MODEL_DIR / "model_stacking_ensemble.pkl"
    legacy_path = MODEL_DIR / "match_predictor_stacking.pkl"
    joblib.dump(stack_model, canonical_path)
    joblib.dump(stack_model, legacy_path)
    print(f"\nModelo stacking canónico guardado en {canonical_path}")
    print(f"Modelo stacking legacy guardado en {legacy_path}")


if __name__ == "__main__":
    main()
