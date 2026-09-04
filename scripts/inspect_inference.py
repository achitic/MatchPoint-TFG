from pathlib import Path
import json
import pandas as pd
import numpy as np

from matchpoint.feature_builder import build_match_features
from matchpoint import MatchPredictor


BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"

FEATURES_PATH = PROC_DIR / "features_full.parquet"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"


def load_schema() -> list[str]:
    data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return data["feature_names"]


def main():
    player_a = "Carlos Alcaraz"
    player_b = "Jannik Sinner"
    surface = "Hard"
    as_of = None  # puedes poner "2024-09-01" si quieres

    feature_names = load_schema()

    # filas de inferencia
    X_ab = build_match_features(
        player_a=player_a, player_b=player_b, surface=surface, as_of=as_of,
        feature_schema=feature_names, proc_dir=PROC_DIR
    )
    X_ba = build_match_features(
        player_a=player_b, player_b=player_a, surface=surface, as_of=as_of,
        feature_schema=feature_names, proc_dir=PROC_DIR
    )

    # predicciones raw
    predictor = MatchPredictor.load(base_dir=BASE_DIR)
    pA_raw = predictor.model.predict_proba(X_ab)[0][1]
    pB_raw = predictor.model.predict_proba(X_ba)[0][1]

    print("== RAW PROBA ==")
    print(f"raw(A gana) A-as-winner_side: {pA_raw:.6f}")
    print(f"raw(B gana) B-as-winner_side: {pB_raw:.6f}")
    print("")

    # stats de entrenamiento para esas 32 features
    df_train = pd.read_parquet(FEATURES_PATH)
    # mismas columnas numéricas que usaste
    cols = [c for c in feature_names if c in df_train.columns]
    train = df_train[cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    stats = pd.DataFrame({
        "mean": train.mean(),
        "std": train.std(ddof=0).replace(0, 1),
        "p05": train.quantile(0.05),
        "p95": train.quantile(0.95),
    })

    # tabla comparativa AB vs BA
    comp = pd.DataFrame({
        "AB": X_ab.iloc[0][cols],
        "BA": X_ba.iloc[0][cols],
    })

    comp["abs_diff"] = (comp["AB"] - comp["BA"]).abs()
    comp["AB_outside_p05_p95"] = ~comp["AB"].between(stats["p05"], stats["p95"])
    comp["BA_outside_p05_p95"] = ~comp["BA"].between(stats["p05"], stats["p95"])

    # ordenar por diferencia
    comp_sorted = comp.sort_values("abs_diff", ascending=False)

    print("== TOP 15 features que más cambian al intercambiar A/B ==")
    print(comp_sorted.head(15).to_string())
    print("")

    # features fuera de rango vs train
    out_ab = comp_sorted[comp_sorted["AB_outside_p05_p95"]].head(15)
    out_ba = comp_sorted[comp_sorted["BA_outside_p05_p95"]].head(15)

    print("== TOP 15 AB fuera del rango [p05, p95] del train ==")
    print(out_ab.to_string())
    print("")
    print("== TOP 15 BA fuera del rango [p05, p95] del train ==")
    print(out_ba.to_string())
    print("")

    # por si quieres ver todo en csv
    out_path = BASE_DIR / "debug_inference_comparison.csv"
    comp_sorted.join(stats, how="left").to_csv(out_path, index=True)
    print(f"CSV guardado: {out_path}")


if __name__ == "__main__":
    main()
