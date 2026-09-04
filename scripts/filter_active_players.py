# scripts/filter_active_players.py
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"

# Parámetros del filtro
REFERENCE_DATE = datetime(2024, 12, 31)
YEARS_ACTIVE = 2  # considerar jugadores con partidos en los últimos 2 años

def main():
    hist_path = PROC_DIR / "elo_history.csv"
    latest_path = PROC_DIR / "elo_latest.csv"
    out_path = PROC_DIR / "elo_latest_active.csv"

    df_hist = pd.read_csv(hist_path, parse_dates=["date"])
    df_latest = pd.read_csv(latest_path)

    cutoff = REFERENCE_DATE - timedelta(days=365 * YEARS_ACTIVE)
    recent_matches = df_hist[df_hist["date"] >= cutoff]

    active_players = pd.unique(recent_matches[["winner", "loser"]].values.ravel("K"))
    df_active = df_latest[df_latest["player"].isin(active_players)]

    df_active.to_csv(out_path, index=False)
    print(f"Jugadores activos guardados en: {out_path}")
    print(f"Jugadores activos: {len(df_active)} de {len(df_latest)} totales")
    print("\nTop 10 jugadores activos por ELO global:")
    print(df_active.sort_values("elo_global", ascending=False).head(10))

if __name__ == "__main__":
    main()
