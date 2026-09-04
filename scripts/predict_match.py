from __future__ import annotations

from pathlib import Path
import argparse
import sys
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from matchpoint import MatchPredictor
from matchpoint.feature_builder import build_match_features
from matchpoint.model_registry import (
    DEFAULT_MODEL_ID,
    get_available_model_ids,
    normalize_model_id,
    uses_dual_pass,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player_a", required=True, help="Nombre jugador A")
    ap.add_argument("--player_b", required=True, help="Nombre jugador B")
    ap.add_argument("--surface", required=True, choices=["Hard", "Clay", "Grass"])
    ap.add_argument("--as_of", default=None, help="YYYY-MM-DD (opcional). Si no, última fecha del dataset.")
    ap.add_argument(
        "--model",
        default=DEFAULT_MODEL_ID,
        choices=get_available_model_ids(scope="predict", include_aliases=True),
        help="Modelo a usar",
    )
    ap.add_argument("--debug", action="store_true", help="Imprime features y diagnóstico")
    args = ap.parse_args()

    canonical_model = normalize_model_id(args.model, scope="predict")
    predictor = MatchPredictor.load(base_dir=BASE_DIR, variant=canonical_model)

    # --- PROBA ---
    # Para modelos core (LR) NO hacemos doble pase + normalización.
    if not uses_dual_pass(canonical_model):
        pA_raw = float(predictor.predict_proba(args.player_a, args.player_b, args.surface, as_of=args.as_of))
        pA = pA_raw
        pB = 1.0 - pA_raw
        pB_raw = pB  # solo para mostrar algo coherente en el print
    else:
        # stacking (u otros futuros): puedes mantener la simetría por doble pase
        pA_raw = float(predictor.predict_proba(args.player_a, args.player_b, args.surface, as_of=args.as_of))
        pB_raw = float(predictor.predict_proba(args.player_b, args.player_a, args.surface, as_of=args.as_of))
        s = pA_raw + pB_raw
        if s > 0:
            pA = pA_raw / s
            pB = pB_raw / s
        else:
            pA, pB = 0.5, 0.5

    print(f"A: {args.player_a}")
    print(f"B: {args.player_b}")
    print(f"Surface: {args.surface}")
    if args.as_of:
        print(f"As-of: {args.as_of}")
    print(f"Model: {canonical_model} (input={args.model})")
    print("")
    print(f"P(A gana) = {pA:.4f}   (raw={pA_raw:.4f})")
    print(f"P(B gana) = {pB:.4f}   (raw={pB_raw:.4f})")

    if not args.debug:
        return

    # --- DEBUG: features ---
    feats = predictor.feature_names

    X_ab = build_match_features(
        player_a=args.player_a,
        player_b=args.player_b,
        surface=args.surface,
        as_of=args.as_of,
        feature_schema=feats,
        proc_dir=predictor.proc_dir,
    )
    X_ba = build_match_features(
        player_a=args.player_b,
        player_b=args.player_a,
        surface=args.surface,
        as_of=args.as_of,
        feature_schema=feats,
        proc_dir=predictor.proc_dir,
    )

    X_ab = X_ab[feats]
    X_ba = X_ba[feats]

    print("\n== DEBUG: FEATURES (A as winner-side) ==")
    print(X_ab.T.to_string(header=False))

    print("\n== DEBUG: FEATURES (B as winner-side) ==")
    print(X_ba.T.to_string(header=False))

    comp = pd.DataFrame({"AB": X_ab.iloc[0], "BA": X_ba.iloc[0]})
    comp["abs_diff"] = (comp["AB"] - comp["BA"]).abs()
    comp_sorted = comp.sort_values("abs_diff", ascending=False)

    print("\n== DEBUG: TOP 15 features que más cambian al intercambiar A/B ==")
    print(comp_sorted.head(15).to_string())


if __name__ == "__main__":
    main()

