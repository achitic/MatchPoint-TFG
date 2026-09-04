from pathlib import Path
import json
import pandas as pd

from train_model import STACKING_FEATURES

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"

FEATURES_PATH = PROC_DIR / "features_full.parquet"
OUT_SCHEMA_CANONICAL = MODEL_DIR / "feature_schema_stacking_ensemble.json"
OUT_SCHEMA_LEGACY = MODEL_DIR / "feature_schema.json"

def main():
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"No existe: {FEATURES_PATH}")

    df = pd.read_parquet(FEATURES_PATH)

    missing = [f for f in STACKING_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Faltan features esperadas para schema stacking: {missing}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_names": STACKING_FEATURES,
        "fillna_value": 0,
        "source": "STACKING_FEATURES v2 (sin columnas de identidad/contexto)",
        "n_features": len(STACKING_FEATURES),
    }

    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
    OUT_SCHEMA_CANONICAL.write_text(payload_text, encoding="utf-8")
    OUT_SCHEMA_LEGACY.write_text(payload_text, encoding="utf-8")
    print(f"OK: guardado {OUT_SCHEMA_CANONICAL} con {len(STACKING_FEATURES)} features")
    print(f"OK: guardado {OUT_SCHEMA_LEGACY} con {len(STACKING_FEATURES)} features (compat)")


if __name__ == "__main__":
    main()
