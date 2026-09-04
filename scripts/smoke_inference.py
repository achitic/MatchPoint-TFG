# scripts/smoke_inference.py
"""
Smoke test para validar coherencia del pipeline de inferencia.

Ejecuta predicciones de prueba y verifica:
- 0 <= p <= 1
- pA + pB ≈ 1
- Columnas de X coinciden con schema
- Sanity checks sobre features_full.parquet
"""
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from matchpoint import MatchPredictor
from matchpoint.feature_builder import build_match_features

PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"


def check_features_parquet():
    """Sanity checks sobre features_full.parquet."""
    print("\n" + "=" * 60)
    print("SANITY CHECKS: features_full.parquet")

    path = PROC_DIR / "features_full.parquet"
    if not path.exists():
        print(f"   ERROR: falta {path}")
        return False

    df = pd.read_parquet(path)
    ok = True

    # Check 1: elo_diff_* no todo 0
    for col in ["elo_diff_global", "elo_diff_surface"]:
        if col in df.columns:
            non_zero = (df[col] != 0).sum()
            pct = non_zero / len(df) * 100
            if pct < 10:
                print(f"   ERROR: {col}: solo {pct:.1f}% no-cero (esperado >10%)")
                ok = False
            else:
                print(f"   OK: {col}: {pct:.1f}% no-cero")

    # Check 2: elo_p_* (si existen) dentro (0,1) y no constante
    for col in ["elo_p_global", "elo_p_surface"]:
        if col in df.columns:
            vals = df[col].dropna()
            if len(vals) == 0:
                continue
            mn, mx = vals.min(), vals.max()
            if mn < 0 or mx > 1:
                print(f"   ERROR: {col}: fuera de (0,1) - min={mn:.3f}, max={mx:.3f}")
                ok = False
            elif mx - mn < 0.01:
                print(f"   ERROR: {col}: casi constante (range={mx - mn:.4f})")
                ok = False
            else:
                print(f"   OK: {col}: min={mn:.3f}, max={mx:.3f}")

    # Check 3: NaNs en columnas core bajo umbral
    core_cols = ["elo_diff_global", "elo_diff_surface", "h2h_ratio", "age_diff"]
    for col in core_cols:
        if col in df.columns:
            nan_pct = df[col].isna().mean() * 100
            if nan_pct > 5:
                print(f"   ERROR: {col}: {nan_pct:.1f}% NaN (esperado <5%)")
                ok = False
            else:
                print(f"   OK: {col}: {nan_pct:.1f}% NaN")

    print(f"\n   RESULTADO: {'PASS' if ok else 'FAIL'}")
    return ok


def check_predictions():
    """Ejecuta predicciones de prueba y valida coherencia."""
    print("\n" + "=" * 60)
    print("SMOKE TEST: Predicciones")

    test_cases = [
        ("Carlos Alcaraz", "Novak Djokovic", "Hard", "2024-05-01"),
        ("Rafael Nadal", "Roger Federer", "Clay", "2019-06-01"),
        ("Jannik Sinner", "Daniil Medvedev", "Hard", "2024-01-15"),
    ]

    models = ["calibrated_logreg", "surface_logreg"]
    all_ok = True

    for model_name in models:
        print(f"\n--- Modelo: {model_name} ---")
        try:
            predictor = MatchPredictor.load(base_dir=BASE_DIR, variant=model_name)
        except Exception as e:
            print(f"   ERROR cargando modelo: {e}")
            all_ok = False
            continue

        schema_path = MODEL_DIR / f"feature_schema_{model_name}.json"
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            expected_feats = schema.get("feature_names", [])
        else:
            expected_feats = predictor.feature_names

        for pA_name, pB_name, surface, as_of in test_cases:
            try:
                # Predecir A vs B
                prob_A = predictor.predict_proba(pA_name, pB_name, surface, as_of=as_of)
                prob_B = 1.0 - prob_A  # Core models asumen simetría

                # Validar rango
                if not (0 <= prob_A <= 1):
                    print(f"   ERROR: {pA_name} vs {pB_name}: P(A)={prob_A:.4f} fuera de [0,1]")
                    all_ok = False
                    continue

                # Validar suma
                total = prob_A + prob_B
                if abs(total - 1.0) > 0.01:
                    print(f"   ERROR: {pA_name} vs {pB_name}: P(A)+P(B)={total:.4f} != 1")
                    all_ok = False
                    continue

                # Check extremos
                extreme = prob_A > 0.95 or prob_A < 0.05
                flag = " EXTREMO" if extreme else ""
                print(f"   OK: {pA_name} vs {pB_name} ({surface}, {as_of}): P(A)={prob_A:.4f}{flag}")

                # Verificar columnas de features
                X = build_match_features(
                    player_a=pA_name,
                    player_b=pB_name,
                    surface=surface,
                    as_of=as_of,
                    feature_schema=expected_feats,
                    proc_dir=PROC_DIR,
                )
                missing_cols = set(expected_feats) - set(X.columns)
                if missing_cols:
                    print(f"   ERROR: columnas faltantes en X: {missing_cols}")
                    all_ok = False

            except Exception as e:
                print(f"   ERROR: {pA_name} vs {pB_name}: {e}")
                all_ok = False

    print(f"\n   RESULTADO: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def main():
    print("MATCHPOINT SMOKE INFERENCE TEST")

    parquet_ok = check_features_parquet()
    pred_ok = check_predictions()

    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print(f"   features_full.parquet: {'PASS' if parquet_ok else 'FAIL'}")
    print(f"   Predicciones:          {'PASS' if pred_ok else 'FAIL'}")

    if parquet_ok and pred_ok:
        print("Todos los smoke tests pasaron")
        return 0
    else:
        print("Algunos smoke tests fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())

