# backend/services/predict_service.py
"""
Service layer wrapping MatchPredictor for API use.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Add repo root to path for matchpoint imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from matchpoint import MatchPredictor
from matchpoint.feature_builder import build_match_features
from matchpoint.model_registry import (
    DEFAULT_MODEL_ID,
    get_explainable_model_ids,
    normalize_model_id,
    uses_dual_pass,
)
from backend.settings import MATCHES_CLEAN_PATH, PROCESSED_DIR
from backend.services.inference_utils import predict_pair_probabilities

# Models that support coefficient-based explanations
LOGREG_MODELS = set(get_explainable_model_ids(include_aliases=False))


class PredictService:
    """Service for making match predictions."""

    def __init__(self):
        self._players_cache: Optional[list[str]] = None
        self._max_date_cache: Optional[pd.Timestamp] = None
        self._min_date_cache: Optional[pd.Timestamp] = None
        self._predictors: dict[str, MatchPredictor] = {}

    def get_players(self) -> list[str]:
        """Get sorted list of unique player names."""
        if self._players_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            winners = set(df["winner_name"].dropna().unique())
            losers = set(df["loser_name"].dropna().unique())
            self._players_cache = sorted(winners | losers)
        return self._players_cache

    def _load_date_bounds(self):
        """Load min and max dates from dataset."""
        if self._max_date_cache is None or self._min_date_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH)
            df["tourney_date"] = pd.to_datetime(df["tourney_date"])
            self._max_date_cache = df["tourney_date"].max()
            self._min_date_cache = df["tourney_date"].min()

    def get_max_date(self) -> pd.Timestamp:
        """Get the maximum date in the dataset."""
        self._load_date_bounds()
        return self._max_date_cache

    def get_min_date(self) -> pd.Timestamp:
        """Get the minimum date in the dataset."""
        self._load_date_bounds()
        return self._min_date_cache

    def _get_predictor(self, model: str) -> MatchPredictor:
        """Get or create predictor for the given model variant."""
        if model not in self._predictors:
            self._predictors[model] = MatchPredictor.load(
                base_dir=REPO_ROOT,
                variant=model
            )
        return self._predictors[model]

    def _build_explain(
        self,
        predictor: MatchPredictor,
        X_a: pd.DataFrame,
        X_b: pd.DataFrame,
        feature_names: list[str],
        model_name: str,
        warnings: list[str],
    ) -> Optional[dict]:
        """
        Build explanation:
        - LogisticRegression coefficients for explainable models.
        - Model-agnostic swap perturbation for non-linear models (e.g. stacking).
        Returns None if model doesn't support it or on error.
        """
        if model_name not in LOGREG_MODELS:
            return self._build_explain_swap_perturbation(
                predictor=predictor,
                X_a=X_a,
                X_b=X_b,
                feature_names=feature_names,
                model_name=model_name,
                warnings=warnings,
            )

        try:
            clf = predictor.model
            
            # Handle CalibratedClassifierCV wrapper (core_calibrated)
            if hasattr(clf, 'calibrated_classifiers_'):
                base = clf.calibrated_classifiers_[0].estimator
                if hasattr(base, "estimator"):
                    # sklearn >=1.7 may wrap prefit estimators as FrozenEstimator
                    base = base.estimator
                if hasattr(base, 'coef_'):
                    coefs = base.coef_.flatten()
                else:
                    warnings.append("Explain unavailable: calibrated model has no coef_")
                    return None
            elif hasattr(clf, 'coef_'):
                coefs = clf.coef_.flatten()
            else:
                warnings.append("Explain unavailable: model has no coef_ attribute")
                return None

            if len(coefs) != len(feature_names):
                warnings.append(f"Explain unavailable: coef length {len(coefs)} != features {len(feature_names)}")
                return None

            x_values = X_a[feature_names].iloc[0].values
            contributions = []
            
            for i, feat in enumerate(feature_names):
                val = float(x_values[i])
                coef = float(coefs[i])
                contrib = val * coef
                
                contributions.append({
                    "feature": feat,
                    "value": round(val, 4),
                    "coef": round(coef, 4),
                    "contribution": round(contrib, 4),
                    "favors": "A" if contrib > 0 else "B",
                })

            # Sort by absolute contribution, top 8
            top = sorted(contributions, key=lambda x: abs(x["contribution"]), reverse=True)[:8]

            return {
                "method": "logreg_coeffs",
                "top_contributors": top,
            }

        except Exception as e:
            warnings.append(f"Explain unavailable: {str(e)}")
            return None

    def _predict_pair_from_feature_rows(
        self,
        predictor: MatchPredictor,
        model_name: str,
        X_a: pd.DataFrame,
        X_b: pd.DataFrame,
    ) -> float:
        """
        Predict P(A) from pre-built feature rows.
        For dual-pass models normalize A/B raw probabilities.
        """
        p_a_raw = float(predictor.model.predict_proba(X_a)[0][1])
        if not uses_dual_pass(model_name):
            return p_a_raw

        p_b_raw = float(predictor.model.predict_proba(X_b)[0][1])
        denom = p_a_raw + p_b_raw
        if denom <= 0:
            return 0.5
        return p_a_raw / denom

    def _build_explain_swap_perturbation(
        self,
        predictor: MatchPredictor,
        X_a: pd.DataFrame,
        X_b: pd.DataFrame,
        feature_names: list[str],
        model_name: str,
        warnings: list[str],
    ) -> Optional[dict]:
        """
        Model-agnostic explanation:
        For each feature, swap A's value with B's value and measure delta on P(A).
        """
        try:
            base_p_a = self._predict_pair_from_feature_rows(
                predictor=predictor,
                model_name=model_name,
                X_a=X_a,
                X_b=X_b,
            )

            row_a = X_a[feature_names].iloc[0]
            row_b = X_b[feature_names].iloc[0]
            contributions = []

            for feat in feature_names:
                X_mut = X_a.copy()
                X_mut.at[X_mut.index[0], feat] = row_b[feat]
                p_mut = self._predict_pair_from_feature_rows(
                    predictor=predictor,
                    model_name=model_name,
                    X_a=X_mut,
                    X_b=X_b,
                )
                delta = float(base_p_a - p_mut)
                contributions.append(
                    {
                        "feature": feat,
                        "value": round(float(row_a[feat]), 4),
                        "coef": round(delta, 4),
                        "contribution": round(delta, 4),
                        "favors": "A" if delta > 0 else "B",
                    }
                )

            top = sorted(contributions, key=lambda x: abs(x["contribution"]), reverse=True)[:8]
            return {
                "method": "swap_perturbation",
                "top_contributors": top,
            }
        except Exception as e:
            warnings.append(f"Explain unavailable: {str(e)}")
            return None

    def _detect_fallback_warnings(
        self,
        features: dict[str, float],
        warnings: list[str],
    ):
        """Add warnings for detected fallback/default values."""
        # Check for h2h neutral (no history)
        if features.get("h2h_total", -1) == 0:
            warnings.append("H2H: No head-to-head history, using neutral ratio (0.5)")

        # Check for zero ELO (player not found in history)
        elo_g = features.get("elo_p_global", -1)
        elo_s = features.get("elo_p_surface", -1)
        if elo_g == 0.5 and elo_s == 0.5:
            warnings.append("ELO: Both players have equal ELO (may indicate missing data)")

        # Check for zero rest days (first match or missing data)
        if features.get("w_rest_days", -1) == 0 and features.get("l_rest_days", -1) == 0:
            warnings.append("Rest days: Both players show 0 rest days (may be first recorded match)")

    def predict(
        self,
        player_a: str,
        player_b: str,
        surface: str,
        model: str = DEFAULT_MODEL_ID,
        as_of: Optional[str] = None,
        debug: bool = False,
    ) -> dict:
        """
        Make a prediction and return structured result.
        
        Returns dict with:
            - player_a, player_b, surface, model
            - as_of_used: actual date used
            - p_a, p_b: probabilities
            - warnings: list of warning messages
            - debug: optional debug info with features
            - explain: optional explanation (logreg coefficients)
        """
        warnings = []
        canonical_model = normalize_model_id(model, scope="predict")
        max_date = self.get_max_date()
        min_date = self.get_min_date()

        if player_a.strip().lower() == player_b.strip().lower():
            raise ValueError("player_a and player_b must be different")

        # Handle as_of date with clamping
        if as_of is None:
            as_of_used = max_date.strftime("%Y-%m-%d")
        else:
            try:
                as_of_dt = pd.Timestamp(as_of)
                if as_of_dt > max_date:
                    warnings.append(
                        f"as_of clamped to dataset max_date: {max_date.strftime('%Y-%m-%d')}"
                    )
                    as_of_used = max_date.strftime("%Y-%m-%d")
                elif as_of_dt < min_date:
                    warnings.append(
                        f"as_of clamped to dataset min_date: {min_date.strftime('%Y-%m-%d')}"
                    )
                    as_of_used = min_date.strftime("%Y-%m-%d")
                else:
                    as_of_used = as_of
            except Exception:
                warnings.append(f"Invalid date format '{as_of}'. Using max date.")
                as_of_used = max_date.strftime("%Y-%m-%d")

        predictor = self._get_predictor(canonical_model)
        
        try:
            p_a, p_b = predict_pair_probabilities(
                predictor=predictor,
                model_id=canonical_model,
                player_a=player_a,
                player_b=player_b,
                surface=surface,
                as_of=as_of_used,
            )
        except ValueError as e:
            raise ValueError(str(e))

        result = {
            "player_a": player_a,
            "player_b": player_b,
            "surface": surface,
            "model": canonical_model,
            "as_of_used": as_of_used,
            "p_a": round(p_a, 4),
            "p_b": round(p_b, 4),
            "warnings": warnings,
            "debug": None,
            "explain": None,
        }

        # Add debug info and explain if requested
        if debug:
            try:
                feature_names = predictor.feature_names
                
                X_a = build_match_features(
                    player_a=player_a,
                    player_b=player_b,
                    surface=surface,
                    as_of=as_of_used,
                    feature_schema=feature_names,
                    proc_dir=PROCESSED_DIR,
                )
                X_b = build_match_features(
                    player_a=player_b,
                    player_b=player_a,
                    surface=surface,
                    as_of=as_of_used,
                    feature_schema=feature_names,
                    proc_dir=PROCESSED_DIR,
                )

                features_a = {k: round(float(v), 4) for k, v in X_a.iloc[0].items()}
                features_b = {k: round(float(v), 4) for k, v in X_b.iloc[0].items()}

                # Detect fallback values and add warnings
                self._detect_fallback_warnings(features_a, warnings)

                # Calculate top diffs
                diffs = []
                for feat in feature_names:
                    a_val = features_a.get(feat, 0)
                    b_val = features_b.get(feat, 0)
                    diff = abs(a_val - b_val)
                    diffs.append({
                        "feature": feat,
                        "a": a_val,
                        "b": b_val,
                        "diff": round(diff, 4),
                    })
                
                top_diffs = sorted(diffs, key=lambda x: x["diff"], reverse=True)[:10]

                result["debug"] = {
                    "features_a": features_a,
                    "features_b": features_b,
                    "top_diffs": top_diffs,
                }

                result["explain"] = self._build_explain(
                    predictor, X_a, X_b, feature_names, canonical_model, warnings
                )

            except Exception as e:
                warnings.append(f"Debug info unavailable: {str(e)}")

        return result


# Singleton instance
_service: Optional[PredictService] = None


def get_service() -> PredictService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = PredictService()
    return _service
