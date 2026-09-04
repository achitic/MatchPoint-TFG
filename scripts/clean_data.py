from pathlib import Path
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

def main():
    parquet_path = PROC_DIR / "matches.parquet"
    df = pd.read_parquet(parquet_path)
    print(f"Dataset original: {len(df):,} filas, {len(df.columns)} columnas")

    df = df[df["surface"].isin(["Hard", "Clay", "Grass"])].copy()

    before = len(df)
    df = df.drop_duplicates()
    print(f"Duplicados eliminados: {before - len(df):,}")

    for col in ["winner_name", "loser_name"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.title()
        )

    valid_levels = ["G", "M", "A", "C", "D", "F"]
    before = len(df)
    df = df[df["tourney_level"].isin(valid_levels)]
    print(f"Filas descartadas por nivel: {before - len(df):,}")

    df = df.dropna(subset=["tourney_date", "winner_name", "loser_name"])
    df = df[df["best_of"].isin([3, 5])]
    df["year"] = df["tourney_date"].dt.year

    out_path = PROC_DIR / "matches_clean.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Dataset limpio: {out_path} ({len(df):,} filas)")

    preview_path = PROC_DIR / "matches_clean_preview.csv"
    df.head(200).to_csv(preview_path, index=False)
    print(f"Vista previa: {preview_path}")

    print("\nResumen por superficie:")
    print(df["surface"].value_counts())
    print("\nNiveles de torneo:")
    print(df["tourney_level"].value_counts())
    print(f"\nAños: {df['year'].min()} - {df['year'].max()}")

if __name__ == "__main__":
    main()
