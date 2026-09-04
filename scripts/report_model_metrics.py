from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from train_core_calibrated import (
    augment_original_plus_inverted as augment_core,
    calculate_elo_prob,
    temporal_split as temporal_split_core,
)
from train_model import (
    build_full_dataset as build_stack_dataset,
    load_data as load_stack_data,
    temporal_split as temporal_split_stack,
)

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models"
DOCS_DIR = BASE_DIR / "docs"


def ece_score(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.digitize(y_prob, bins) - 1
    total = len(y_true)
    ece = 0.0
    for i in range(n_bins):
        mask = bin_ids == i
        if not np.any(mask):
            continue
        acc = float(np.mean(y_true[mask]))
        conf = float(np.mean(y_prob[mask]))
        ece += (np.sum(mask) / total) * abs(acc - conf)
    return float(ece)


def evaluate_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-15, 1.0 - 1e-15)
    y_true = np.asarray(y_true, dtype=int)
    return {
        "accuracy": float(accuracy_score(y_true, y_prob >= 0.5)),
        "logloss": float(log_loss(y_true, y_prob)),
        "auc": float(roc_auc_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "ece10": float(ece_score(y_true, y_prob, n_bins=10)),
    }


def load_schema_features(schema_path: Path) -> list[str]:
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    return list(data["feature_names"])


def build_segment_rows(
    model_id: str,
    protocol: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    ref_df: pd.DataFrame,
) -> list[dict]:
    rows: list[dict] = []
    candidates: list[tuple[str, np.ndarray]] = []

    if {"winner_rank", "loser_rank"}.issubset(ref_df.columns):
        top10 = (
            pd.to_numeric(ref_df["winner_rank"], errors="coerce").fillna(9999).to_numpy() <= 10
        ) & (
            pd.to_numeric(ref_df["loser_rank"], errors="coerce").fillna(9999).to_numpy() <= 10
        )
        candidates.append(("top10_vs_top10", top10))

    if "surface" in ref_df.columns:
        surfaces = ref_df["surface"].astype(str).str.title().to_numpy()
        for s in ["Hard", "Clay", "Grass"]:
            candidates.append((f"surface={s}", surfaces == s))

    if "tourney_level" in ref_df.columns:
        levels = ref_df["tourney_level"].astype(str).to_numpy()
        candidates.append(("circuit=ATP_main", np.isin(levels, ["A", "M", "G", "F"])))
        candidates.append(("circuit=Challenger", levels == "C"))

    for name, mask in candidates:
        n = int(np.sum(mask))
        if n < 50:
            continue
        y_seg = y_true[mask]
        p_seg = y_prob[mask]
        rows.append(
            {
                "model_id": model_id,
                "protocol": protocol,
                "segment": name,
                "n_test": n,
                **evaluate_metrics(y_seg, p_seg),
            }
        )
    return rows


def evaluate_core_model(model_id: str, model_path: Path, schema_path: Path, test_df: pd.DataFrame) -> dict:
    model = joblib.load(model_path)
    feats = load_schema_features(schema_path)
    X = test_df[feats].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = test_df["target"].astype(int).to_numpy()
    p = model.predict_proba(X)[:, 1]

    base = {
        "model_id": model_id,
        "protocol": "temporal: train<=2021, val=2022-2023, test=2024",
        "n_test": int(len(y)),
        **evaluate_metrics(y, p),
    }
    segments = build_segment_rows(model_id, base["protocol"], y, p, test_df)
    return {"base": base, "segments": segments}


def evaluate_stack_model() -> dict:
    model_path = MODEL_DIR / "model_stacking_ensemble.pkl"
    model = joblib.load(model_path)

    df = load_stack_data()
    df_full, X_all, y_all, _ = build_stack_dataset(df)
    (_, _), (_, _), (X_test, y_test) = temporal_split_stack(df_full, X_all, y_all)
    p = model.predict_proba(X_test)[:, 1]

    base = {
        "model_id": "stacking_ensemble",
        "protocol": "stack temporal by date (<=2021, 2022-2023, >=2024)",
        "n_test": int(len(y_test)),
        **evaluate_metrics(y_test.to_numpy(), p),
    }
    ref_df = df_full.loc[X_test.index].reset_index(drop=True)
    segments = build_segment_rows(base["model_id"], base["protocol"], y_test.to_numpy(), p, ref_df)
    return {"base": base, "segments": segments}


def build_report(rows: list[dict]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_rows = [r for r in rows if "segment" not in r]
    segment_rows = [r for r in rows if "segment" in r]

    lines = [
        "# Model Metrics Baseline",
        "",
        f"- Generated at: `{ts}`",
        "- Protocol: train through 2021, validation/calibration in 2022-2023 and final test in 2024.",
        "- The stacking base learners use train only; its prefitted meta-learner uses validation only.",
        "",
        "| Model | Protocol | N test | Accuracy | LogLoss | AUC | Brier | ECE@10 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in base_rows:
        lines.append(
            f"| `{r['model_id']}` | {r['protocol']} | {r['n_test']} | "
            f"{r['accuracy']:.6f} | {r['logloss']:.6f} | {r['auc']:.6f} | "
            f"{r['brier']:.6f} | {r['ece10']:.6f} |"
        )

    if segment_rows:
        lines.extend(
            [
                "",
                "## Segment Metrics",
                "",
                "| Model | Segment | N | Accuracy | LogLoss | AUC | Brier | ECE@10 |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for r in segment_rows:
            lines.append(
                f"| `{r['model_id']}` | {r['segment']} | {r['n_test']} | "
                f"{r['accuracy']:.6f} | {r['logloss']:.6f} | {r['auc']:.6f} | "
                f"{r['brier']:.6f} | {r['ece10']:.6f} |"
            )

    return "\n".join(lines) + "\n"


def main() -> None:
    features_path = PROC_DIR / "features_full.parquet"
    df = pd.read_parquet(features_path)
    df["elo_p_global"] = calculate_elo_prob(df["elo_diff_global"])
    df["elo_p_surface"] = calculate_elo_prob(df["elo_diff_surface"])
    df_core = augment_core(df)
    _, _, test_core = temporal_split_core(df_core)

    core_baseline = evaluate_core_model(
        "baseline_logreg",
        MODEL_DIR / "model_baseline_logreg.pkl",
        MODEL_DIR / "feature_schema_baseline_logreg.json",
        test_core,
    )
    core_surface = evaluate_core_model(
        "surface_logreg",
        MODEL_DIR / "model_surface_logreg.pkl",
        MODEL_DIR / "feature_schema_surface_logreg.json",
        test_core,
    )
    core_calibrated = evaluate_core_model(
        "calibrated_logreg",
        MODEL_DIR / "model_calibrated_logreg.pkl",
        MODEL_DIR / "feature_schema_calibrated_logreg.json",
        test_core,
    )
    stack_eval = evaluate_stack_model()

    rows = [
        core_baseline["base"],
        core_surface["base"],
        core_calibrated["base"],
        stack_eval["base"],
        *core_baseline["segments"],
        *core_surface["segments"],
        *core_calibrated["segments"],
        *stack_eval["segments"],
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / f"model-metrics-baseline-{datetime.now().strftime('%Y-%m-%d')}.md"
    out_path.write_text(build_report(rows), encoding="utf-8")
    print(f"OK: report saved to {out_path}")


if __name__ == "__main__":
    main()
