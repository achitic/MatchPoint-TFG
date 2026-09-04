from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union
import json
import joblib

from .feature_builder import build_match_features
from .model_registry import DEFAULT_MODEL_ID, normalize_model_id, resolve_artifact_paths


@dataclass
class MatchPredictor:
    model: object
    feature_names: list[str]
    proc_dir: Path

    @staticmethod
    def load(
        base_dir: Union[str, Path, None] = None,
        variant: str = DEFAULT_MODEL_ID,
    ) -> "MatchPredictor":
        """
        Carga un modelo y su schema desde /models y fija proc_dir en /data/processed.

        base_dir:
          - None -> se usa la raíz del repo (MatchPoint/)
          - str/Path -> ruta explícita a la raíz del repo
        variant:
          - Nombres canónicos: baseline_logreg, surface_logreg,
            calibrated_logreg, stacking_ensemble
          - Alias legacy también soportados: core, core_elop,
            core_calibrated, stacking
        """
        if base_dir is None:
            base = Path(__file__).resolve().parents[1]
        else:
            base = Path(base_dir)

        canonical_variant = normalize_model_id(variant, scope="predict")
        model_path, schema_path = resolve_artifact_paths(base, canonical_variant)

        proc_dir = base / "data" / "processed"

        # Validaciones útiles
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modelo no encontrado: {model_path}\n"
                f"Base dir resuelta: {base}\n"
                f"Variante solicitada: {variant} (canónica: {canonical_variant})\n"
                f"Comprueba que existe /models y que el nombre del .pkl coincide."
            )
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema no encontrado: {schema_path}\n"
                f"Base dir resuelta: {base}\n"
                f"Variante solicitada: {variant} (canónica: {canonical_variant})\n"
                f"Comprueba que existe el JSON de schema para esta variante."
            )
        if not proc_dir.exists():
            raise FileNotFoundError(
                f"Directorio de datos procesados no encontrado: {proc_dir}\n"
                f"Base dir resuelta: {base}\n"
                f"Comprueba que has generado data/processed (features, elo_history, etc.)."
            )

        model = joblib.load(model_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        feature_names = schema["feature_names"]

        return MatchPredictor(model=model, feature_names=feature_names, proc_dir=proc_dir)

    def predict_proba(
        self,
        player_a: str,
        player_b: str,
        surface: str,
        as_of: str | None = None,
    ) -> float:
        X = build_match_features(
            player_a=player_a,
            player_b=player_b,
            surface=surface,
            as_of=as_of,
            feature_schema=self.feature_names,
            proc_dir=self.proc_dir,
        )
        return float(self.model.predict_proba(X)[0][1])
