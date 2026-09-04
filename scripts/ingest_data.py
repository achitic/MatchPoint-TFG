import sys
from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

YEARS = range(2006, 2025)  # 2006–2024

COLS_KEEP = [
    "tourney_id", "tourney_name", "tourney_date", "tourney_level",
    "surface", "draw_size",
    "match_num", "best_of", "round",
    "winner_id", "winner_name", "winner_hand", "winner_ioc", "winner_age",
    "loser_id", "loser_name", "loser_hand", "loser_ioc", "loser_age",
    "score", "minutes",
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
    "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon",
    "l_SvGms", "l_bpSaved", "l_bpFaced",
    "winner_rank", "winner_rank_points",
    "loser_rank", "loser_rank_points",
]

SURFACE_MAP = {
    "Hard": "Hard",
    "Clay": "Clay",
    "Grass": "Grass",
    "Carpet": "Carpet",  # rara, puedes filtrar luego
    None: None,
    "": None,
}

def read_year(path: Path) -> pd.DataFrame:
    """Lee y normaliza un CSV anual de Sackmann."""
    df = pd.read_csv(path, low_memory=False)
    missing = [c for c in COLS_KEEP if c not in df.columns]
    for c in missing:
        df[c] = pd.NA
    df = df[COLS_KEEP].copy()

    df["surface"] = df["surface"].map(lambda x: SURFACE_MAP.get(x, x))

    df["tourney_date"] = pd.to_datetime(
        df["tourney_date"].astype(str), format="%Y%m%d", errors="coerce"
    )

    df = df.dropna(subset=["winner_name", "loser_name", "tourney_date"])
    df = df[df["best_of"].isin([3, 5])]

    return df


def main():
    frames = []
    missing_years = []

    for y in YEARS:
        main_path = RAW_DIR / f"atp_matches_{y}.csv"
        chall_path = RAW_DIR / f"atp_matches_qual_chall_{y}.csv"

        if main_path.exists():
            frames.append(read_year(main_path))
        else:
            missing_years.append(f"ATP {y}")

        if chall_path.exists():
            frames.append(read_year(chall_path))
        else:
            missing_years.append(f"CHALL {y}")

    if not frames:
        print("No se encontraron CSV en data/raw/.")
        sys.exit(1)

    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.sort_values(
        ["tourney_date", "tourney_name", "match_num"], kind="mergesort"
    ).reset_index(drop=True)

    df_all["year"] = df_all["tourney_date"].dt.year

    out_parquet = PROC_DIR / "matches.parquet"
    df_all.to_parquet(out_parquet, index=False)
    print(f"Guardado {out_parquet} con {len(df_all):,} filas")

    summary = (
        df_all.groupby(["year", "surface"], dropna=False)
        .size()
        .reset_index(name="n_matches")
        .sort_values(["year", "surface"])
    )
    out_summary = PROC_DIR / "matches_summary.csv"
    summary.to_csv(out_summary, index=False)
    print(f"Guardado resumen en {out_summary}")

    if missing_years:
        print(f"Aviso: faltan archivos de estos años: {missing_years}")


if __name__ == "__main__":
    main()
