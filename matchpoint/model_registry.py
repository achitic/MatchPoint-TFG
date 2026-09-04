from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    canonical_id: str
    legacy_ids: tuple[str, ...]
    label_es: str
    description_es: str
    model_filenames: tuple[str, ...]
    schema_filenames: tuple[str, ...]
    supports_explain: bool
    use_dual_pass: bool


MODEL_SPECS: dict[str, ModelSpec] = {
    "calibrated_logreg": ModelSpec(
        canonical_id="calibrated_logreg",
        legacy_ids=("core_calibrated",),
        label_es="Modelo probabilístico calibrado · Recomendado",
        description_es="Regresión logística con calibración isotónica para probabilidades fiables.",
        model_filenames=("model_calibrated_logreg.pkl", "match_predictor_core_calibrated.pkl"),
        schema_filenames=("feature_schema_calibrated_logreg.json", "feature_schema_core_calibrated.json"),
        supports_explain=True,
        use_dual_pass=False,
    ),
    "surface_logreg": ModelSpec(
        canonical_id="surface_logreg",
        legacy_ids=("core_elop",),
        label_es="Modelo especializado por superficie",
        description_es="Combina ELO global, específico por superficie y blended.",
        model_filenames=("model_surface_logreg.pkl", "match_predictor_core_elop.pkl"),
        schema_filenames=("feature_schema_surface_logreg.json", "feature_schema_core_elop.json"),
        supports_explain=True,
        use_dual_pass=False,
    ),
    "baseline_logreg": ModelSpec(
        canonical_id="baseline_logreg",
        legacy_ids=("core",),
        label_es="Modelo base ELO",
        description_es="Referencia interpretable basada únicamente en el ELO global.",
        model_filenames=("model_baseline_logreg.pkl", "match_predictor_core.pkl"),
        schema_filenames=("feature_schema_baseline_logreg.json", "feature_schema_core.json"),
        supports_explain=True,
        use_dual_pass=False,
    ),
    "stacking_ensemble": ModelSpec(
        canonical_id="stacking_ensemble",
        legacy_ids=("stacking",),
        label_es="Ensemble avanzado",
        description_es="Combina varios algoritmos predictivos; ofrece menor interpretabilidad.",
        model_filenames=("model_stacking_ensemble.pkl", "match_predictor_stacking.pkl"),
        schema_filenames=("feature_schema_stacking_ensemble.json", "feature_schema.json"),
        supports_explain=False,
        use_dual_pass=True,
    ),
}

DEFAULT_MODEL_ID = "calibrated_logreg"

_SCOPE_TO_MODELS: dict[str, tuple[str, ...]] = {
    "predict": tuple(MODEL_SPECS.keys()),
    "simulate": tuple(MODEL_SPECS.keys()),
    "tournament": tuple(MODEL_SPECS.keys()),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical_id, spec in MODEL_SPECS.items():
    _ALIAS_TO_CANONICAL[canonical_id] = canonical_id
    for legacy_id in spec.legacy_ids:
        _ALIAS_TO_CANONICAL[legacy_id] = canonical_id


def _scope_ids(scope: str) -> tuple[str, ...]:
    if scope not in _SCOPE_TO_MODELS:
        valid = ", ".join(sorted(_SCOPE_TO_MODELS))
        raise ValueError(f"Unknown model scope '{scope}'. Valid scopes: {valid}")
    return _SCOPE_TO_MODELS[scope]


def normalize_model_id(model_id: str, scope: str = "predict") -> str:
    raw = (model_id or "").strip().lower()
    if not raw:
        raise ValueError("Model id cannot be empty")

    canonical_id = _ALIAS_TO_CANONICAL.get(raw)
    if canonical_id is None:
        valid = ", ".join(get_available_model_ids(scope=scope, include_aliases=True))
        raise ValueError(f"Model must be one of: {valid}")

    if canonical_id not in _scope_ids(scope):
        valid = ", ".join(get_available_model_ids(scope=scope, include_aliases=True))
        raise ValueError(f"Model '{model_id}' is not available for scope '{scope}'. Valid: {valid}")

    return canonical_id


def get_model_spec(model_id: str, scope: str = "predict") -> ModelSpec:
    canonical_id = normalize_model_id(model_id, scope=scope)
    return MODEL_SPECS[canonical_id]


def get_available_model_ids(scope: str = "predict", include_aliases: bool = False) -> list[str]:
    canonical_ids = list(_scope_ids(scope))
    if not include_aliases:
        return canonical_ids

    all_ids = set(canonical_ids)
    for canonical_id in canonical_ids:
        all_ids.update(MODEL_SPECS[canonical_id].legacy_ids)
    return sorted(all_ids)


def get_explainable_model_ids(include_aliases: bool = False) -> list[str]:
    canonical_ids = [m.canonical_id for m in MODEL_SPECS.values() if m.supports_explain]
    if not include_aliases:
        return canonical_ids

    all_ids = set(canonical_ids)
    for canonical_id in canonical_ids:
        all_ids.update(MODEL_SPECS[canonical_id].legacy_ids)
    return sorted(all_ids)


def get_models_catalog(scope: str = "predict") -> list[dict]:
    catalog: list[dict] = []
    for canonical_id in get_available_model_ids(scope=scope, include_aliases=False):
        spec = MODEL_SPECS[canonical_id]
        catalog.append(
            {
                "id": spec.canonical_id,
                "label_es": spec.label_es,
                "description_es": spec.description_es,
            }
        )
    return catalog


def uses_dual_pass(model_id: str) -> bool:
    return get_model_spec(model_id).use_dual_pass


def resolve_artifact_paths(base_dir: Path, model_id: str) -> tuple[Path, Path]:
    spec = get_model_spec(model_id)

    models_dir = base_dir / "models"
    model_candidates = [models_dir / name for name in spec.model_filenames]
    schema_candidates = [models_dir / name for name in spec.schema_filenames]

    model_path = next((path for path in model_candidates if path.exists()), model_candidates[0])
    schema_path = next((path for path in schema_candidates if path.exists()), schema_candidates[0])
    return model_path, schema_path
