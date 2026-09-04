from __future__ import annotations

import pandas as pd

from matchpoint.model_registry import get_models_catalog
from scripts.train_core_calibrated import temporal_split as calibrated_split
from scripts.train_core_elop_model import temporal_split as surface_split
from scripts.train_core_model import temporal_split as baseline_split
from scripts.build_features import compute_last5
from scripts.train_model import build_full_dataset


def _sample_augmented_rows() -> pd.DataFrame:
    rows = []
    for date in ["2021-12-31", "2022-01-01", "2023-12-31", "2024-01-01"]:
        rows.extend(
            [
                {"tourney_date": date, "pair_id": date, "target": 1},
                {"tourney_date": date, "pair_id": date, "target": 0},
            ]
        )
    return pd.DataFrame(rows)


def test_all_core_models_share_strict_temporal_boundaries():
    for splitter in [baseline_split, surface_split, calibrated_split]:
        train, validation, test = splitter(_sample_augmented_rows())

        assert set(train["pair_id"]) == {"2021-12-31"}
        assert set(validation["pair_id"]) == {"2022-01-01", "2023-12-31"}
        assert set(test["pair_id"]) == {"2024-01-01"}
        assert train.groupby("pair_id")["target"].nunique().eq(2).all()
        assert validation.groupby("pair_id")["target"].nunique().eq(2).all()
        assert test.groupby("pair_id")["target"].nunique().eq(2).all()


def test_public_model_catalog_hides_legacy_aliases():
    catalog = get_models_catalog()
    labels = {item["id"]: item["label_es"] for item in catalog}

    assert labels["baseline_logreg"] == "Modelo base ELO"
    assert labels["surface_logreg"] == "Modelo especializado por superficie"
    assert labels["calibrated_logreg"].startswith("Modelo probabilístico calibrado")
    assert labels["stacking_ensemble"] == "Ensemble avanzado"
    assert all("legacy" not in item["description_es"].lower() for item in catalog)


def test_last5_excludes_current_match_result():
    matches = pd.DataFrame(
        [
            {"winner_name": "A", "loser_name": "B"},
            {"winner_name": "A", "loser_name": "C"},
        ]
    )

    result = compute_last5(matches)

    assert result.loc[0, "w_last5_wins"] == 0
    assert result.loc[0, "l_last5_wins"] == 0
    assert result.loc[1, "w_last5_wins"] == 1
    assert result.loc[1, "l_last5_wins"] == 0


def test_stacking_inversion_keeps_no_h2h_neutral():
    row = {
        "tourney_date": pd.Timestamp("2024-01-01"),
        "h2h_total": 0,
        "h2h_wins": 0,
        "h2h_ratio": 0.5,
    }
    # Complete the synthetic row with neutral values for the stacking contract.
    from scripts.train_model import STACKING_FEATURES

    row.update({feature: row.get(feature, 0.0) for feature in STACKING_FEATURES})
    full, _, _, _ = build_full_dataset(pd.DataFrame([row]))

    assert full["h2h_ratio"].tolist() == [0.5, 0.5]
