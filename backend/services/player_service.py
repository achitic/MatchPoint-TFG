"""
Player profile and history service.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pandas as pd

from backend.settings import MATCHES_CLEAN_PATH, PROCESSED_DIR


SURFACES = ("Hard", "Clay", "Grass")


def _clean_optional_str(value: object) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_optional_float(value: object) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _safe_sum(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0.0).sum())


def _safe_ratio(num: float, den: float) -> Optional[float]:
    if den <= 0:
        return None
    return round(num / den, 4)


class PlayerService:
    """Read-only player analytics built from processed match and ELO data."""

    def __init__(self):
        self._matches_cache: Optional[pd.DataFrame] = None
        self._elo_latest_cache: Optional[pd.DataFrame] = None
        self._elo_history_cache: Optional[pd.DataFrame] = None
        self._players_cache: Optional[list[str]] = None

    def _load_matches(self) -> pd.DataFrame:
        if self._matches_cache is None:
            df = pd.read_parquet(MATCHES_CLEAN_PATH).copy()
            df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
            if "surface" in df.columns:
                df["surface"] = df["surface"].astype(str).str.title()
            self._matches_cache = df
        return self._matches_cache

    def _load_elo_latest(self) -> pd.DataFrame:
        if self._elo_latest_cache is None:
            path = PROCESSED_DIR / "elo_latest.csv"
            self._elo_latest_cache = pd.read_csv(path) if path.exists() else pd.DataFrame()
        return self._elo_latest_cache

    def _load_elo_history(self) -> pd.DataFrame:
        if self._elo_history_cache is None:
            path = PROCESSED_DIR / "elo_history.csv"
            if path.exists():
                df = pd.read_csv(path)
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                if "surface" in df.columns:
                    df["surface"] = df["surface"].astype(str).str.title()
                self._elo_history_cache = df
            else:
                self._elo_history_cache = pd.DataFrame()
        return self._elo_history_cache

    def get_players(self) -> list[str]:
        if self._players_cache is None:
            df = self._load_matches()
            winners = set(df["winner_name"].dropna().astype(str).unique())
            losers = set(df["loser_name"].dropna().astype(str).unique())
            self._players_cache = sorted(winners | losers)
        return self._players_cache

    def resolve_player(self, name: str) -> str:
        needle = name.strip()
        if not needle:
            raise ValueError("Player name is required")

        players = self.get_players()
        by_lower = {p.lower(): p for p in players}
        resolved = by_lower.get(needle.lower())
        if resolved:
            return resolved
        raise ValueError(f"Player '{name}' not found")

    def search_players(self, query: str, limit: int = 10) -> list[str]:
        q = query.strip().lower()
        if not q:
            return []
        players = self.get_players()
        starts = [p for p in players if p.lower().startswith(q)]
        contains = [p for p in players if q in p.lower() and p not in starts]
        return (starts + contains)[:limit]

    def _player_matches(self, player: str) -> pd.DataFrame:
        df = self._load_matches()
        mask = (df["winner_name"] == player) | (df["loser_name"] == player)
        return df[mask].copy().sort_values("tourney_date", ascending=False)

    def get_profile(self, name: str) -> dict:
        player = self.resolve_player(name)
        matches = self._player_matches(player)
        if matches.empty:
            raise ValueError(f"Player '{name}' has no matches")

        latest = matches.iloc[0]
        is_latest_winner = latest["winner_name"] == player
        age_col = "winner_age" if is_latest_winner else "loser_age"
        ioc_col = "winner_ioc" if is_latest_winner else "loser_ioc"

        wins = int((matches["winner_name"] == player).sum())
        losses = int((matches["loser_name"] == player).sum())

        record_by_surface = {}
        for surface in SURFACES:
            surf_df = matches[matches["surface"] == surface]
            record_by_surface[surface] = {
                "wins": int((surf_df["winner_name"] == player).sum()),
                "losses": int((surf_df["loser_name"] == player).sum()),
            }

        streak_type = "W" if latest["winner_name"] == player else "L"
        streak_count = 0
        for _, row in matches.iterrows():
            result = "W" if row["winner_name"] == player else "L"
            if result != streak_type:
                break
            streak_count += 1

        elo_latest = self._load_elo_latest()
        elo_row = pd.DataFrame()
        if not elo_latest.empty and "player" in elo_latest.columns:
            elo_row = elo_latest[elo_latest["player"] == player]

        elo_by_surface = {}
        for surface in SURFACES:
            col = f"elo_{surface}"
            elo_by_surface[surface] = (
                _clean_optional_float(elo_row.iloc[0].get(col)) if not elo_row.empty and col in elo_row.columns else None
            )

        elo_global = None
        if not elo_row.empty:
            elo_global = _clean_optional_float(elo_row.iloc[0].get("elo_global"))

        last_date = latest["tourney_date"]
        return {
            "name": player,
            "age": _clean_optional_float(latest.get(age_col)),
            "nationality": _clean_optional_str(latest.get(ioc_col)),
            "elo_global": elo_global,
            "elo_by_surface": elo_by_surface,
            "record": {"wins": wins, "losses": losses},
            "record_by_surface": record_by_surface,
            "current_streak": {"type": streak_type, "count": streak_count},
            "last_match_date": last_date.strftime("%Y-%m-%d") if pd.notna(last_date) else None,
        }

    def get_history(self, name: str, limit: int = 20) -> dict:
        player = self.resolve_player(name)
        matches_df = self._player_matches(player).head(limit)
        match_rows = []
        for _, row in matches_df.iterrows():
            won = row["winner_name"] == player
            opponent = row["loser_name"] if won else row["winner_name"]
            date_value = row["tourney_date"]
            match_rows.append({
                "date": date_value.strftime("%Y-%m-%d") if pd.notna(date_value) else "",
                "tournament": _clean_optional_str(row.get("tourney_name")) or "",
                "surface": _clean_optional_str(row.get("surface")) or "",
                "opponent": str(opponent),
                "result": "W" if won else "L",
                "score": _clean_optional_str(row.get("score")) or "",
            })

        elo_df = self._load_elo_history()
        elo_points = []
        if not elo_df.empty:
            mask = (elo_df["winner"] == player) | (elo_df["loser"] == player)
            player_elo = elo_df[mask].sort_values("date").tail(160)
            for _, row in player_elo.iterrows():
                won = row["winner"] == player
                date_value = row["date"]
                elo_points.append({
                    "date": date_value.strftime("%Y-%m-%d") if pd.notna(date_value) else "",
                    "elo_global": _clean_optional_float(row.get("elo_w_after" if won else "elo_l_after")),
                    "elo_surface": _clean_optional_float(row.get("elo_w_surface_after" if won else "elo_l_surface_after")),
                    "surface": _clean_optional_str(row.get("surface")) or "",
                })

        return {"player": player, "matches": match_rows, "elo_evolution": elo_points}

    def get_serve_stats(self, name: str, surface: Optional[str] = None) -> dict:
        player = self.resolve_player(name)
        matches = self._player_matches(player)
        if surface:
            surface_norm = surface.strip().title()
            if surface_norm not in SURFACES:
                raise ValueError("Surface must be Hard, Clay, or Grass")
            matches = matches[matches["surface"] == surface_norm]
        else:
            surface_norm = "all"

        winner_rows = matches[matches["winner_name"] == player]
        loser_rows = matches[matches["loser_name"] == player]

        svpt = _safe_sum(winner_rows, "w_svpt") + _safe_sum(loser_rows, "l_svpt")
        first_in = _safe_sum(winner_rows, "w_1stIn") + _safe_sum(loser_rows, "l_1stIn")
        aces = _safe_sum(winner_rows, "w_ace") + _safe_sum(loser_rows, "l_ace")
        dfs = _safe_sum(winner_rows, "w_df") + _safe_sum(loser_rows, "l_df")
        bp_saved = _safe_sum(winner_rows, "w_bpSaved") + _safe_sum(loser_rows, "l_bpSaved")
        bp_faced = _safe_sum(winner_rows, "w_bpFaced") + _safe_sum(loser_rows, "l_bpFaced")

        opp_svpt = _safe_sum(winner_rows, "l_svpt") + _safe_sum(loser_rows, "w_svpt")
        opp_first_won = _safe_sum(winner_rows, "l_1stWon") + _safe_sum(loser_rows, "w_1stWon")
        opp_second_won = _safe_sum(winner_rows, "l_2ndWon") + _safe_sum(loser_rows, "w_2ndWon")
        return_points_won = max(opp_svpt - opp_first_won - opp_second_won, 0.0)

        return {
            "player": player,
            "surface": surface_norm,
            "first_serve_pct": _safe_ratio(first_in, svpt),
            "ace_rate": _safe_ratio(aces, svpt),
            "double_fault_rate": _safe_ratio(dfs, svpt),
            "bp_saved_pct": _safe_ratio(bp_saved, bp_faced),
            "return_points_won_pct": _safe_ratio(return_points_won, opp_svpt),
            "matches_counted": int(len(matches)),
        }

    def generate_scouting_report(
        self,
        name_a: str,
        name_b: str,
        surface: str,
    ) -> dict:
        """
        Generate a tactical scouting report comparing player_a vs player_b on a surface.

        Returns a structured dict with:
          - Stats for both players (overall and surface-specific)
          - Rival weaknesses / strengths (about player_b)
          - Strategic recommendations for player_a
          - An overall advantage verdict
        """
        surface_norm = surface.strip().title()
        if surface_norm not in SURFACES:
            raise ValueError(f"Surface must be Hard, Clay, or Grass (got '{surface}')")

        player_a = self.resolve_player(name_a)
        player_b = self.resolve_player(name_b)

        # ── Gather base data ──────────────────────────────────────────
        def _build_compare_stats(name: str) -> dict:
            serve = self.get_serve_stats(name, surface=surface_norm)
            profile = self.get_profile(name)

            # Win rate overall
            rec = profile["record"]
            total = rec["wins"] + rec["losses"]
            win_rate = round(rec["wins"] / total, 4) if total > 0 else None

            # Win rate on surface
            rec_surf = profile["record_by_surface"].get(surface_norm, {"wins": 0, "losses": 0})
            total_surf = rec_surf["wins"] + rec_surf["losses"]
            win_rate_surf = round(rec_surf["wins"] / total_surf, 4) if total_surf > 0 else None

            # ELO surface
            elo_surf = profile["elo_by_surface"].get(surface_norm)

            return {
                "player": name,
                "surface": surface_norm,
                "first_serve_pct": serve["first_serve_pct"],
                "ace_rate": serve["ace_rate"],
                "double_fault_rate": serve["double_fault_rate"],
                "bp_saved_pct": serve["bp_saved_pct"],
                "return_points_won_pct": serve["return_points_won_pct"],
                "matches_counted": serve["matches_counted"],
                "elo_global": profile["elo_global"],
                "elo_surface": elo_surf,
                "win_rate": win_rate,
                "win_rate_surface": win_rate_surf,
            }

        stats_a = _build_compare_stats(player_a)
        stats_b = _build_compare_stats(player_b)

        # ── Insight-generation rules ──────────────────────────────────
        rival_weaknesses: list[dict] = []
        rival_strengths: list[dict] = []
        recommendations: list[dict] = []

        def _v(d: dict, key: str) -> Optional[float]:
            return d.get(key)

        # ── 1. Double fault rate (serve weakness) ──
        df_b = _v(stats_b, "double_fault_rate")
        if df_b is not None:
            if df_b >= 0.06:
                rival_weaknesses.append({
                    "type": "weakness", "category": "serve", "severity": "high",
                    "title": "Alto porcentaje de dobles faltas",
                    "description": (
                        f"{player_b} comete dobles faltas en el {df_b*100:.1f}% de sus puntos de servicio. "
                        "Aplica presión al segundo saque restando con agresividad. "
                        "Muévete hacia dentro de la pista para restar más cerca de la red."
                    ),
                    "metric_value": round(df_b * 100, 1),
                    "metric_label": "% Dobles Faltas",
                })
                recommendations.append({
                    "type": "strength", "category": "return", "severity": "high",
                    "title": "Presionar el segundo saque del rival",
                    "description": (
                        "El rival falla frecuentemente el segundo servicio. Adopta una posición "
                        "de resto más agresiva (+1m dentro de la línea de fondo) para reducir el tiempo de reacción del rival "
                        "e inducir el error o forzar un saque corto y atacable."
                    ),
                    "metric_value": round(df_b * 100, 1),
                    "metric_label": "% DF rival",
                })
            elif df_b <= 0.04:
                rival_strengths.append({
                    "type": "strength", "category": "serve", "severity": "medium",
                    "title": "Servicio muy fiable (pocas dobles faltas)",
                    "description": (
                        f"{player_b} tiene un ratio de dobles faltas muy bajo ({df_b*100:.1f}%). "
                        "No construyas el game plan esperando errores del rival al servicio. "
                        "Prepárate para intercambios desde la segunda bola con paciencia."
                    ),
                    "metric_value": round(df_b * 100, 1),
                    "metric_label": "% Dobles Faltas",
                })

        # ── 2. First serve percentage (serve consistency) ──
        fs_b = _v(stats_b, "first_serve_pct")
        if fs_b is not None:
            if fs_b < 0.60:
                rival_weaknesses.append({
                    "type": "weakness", "category": "serve", "severity": "medium",
                    "title": "Baja efectividad del primer servicio",
                    "description": (
                        f"{player_b} entra con primer saque solo el {fs_b*100:.1f}% de las veces. "
                        "Aprovecha sus numerosos segundos saques — más lentos y con menos ángulo — "
                        "para construir el punto desde el ataque."
                    ),
                    "metric_value": round(fs_b * 100, 1),
                    "metric_label": "% 1er Servicio",
                })
            elif fs_b >= 0.70:
                rival_strengths.append({
                    "type": "strength", "category": "serve", "severity": "medium",
                    "title": "Gran regularidad en el primer servicio",
                    "description": (
                        f"{player_b} entra con el primer saque el {fs_b*100:.1f}% de las veces. "
                        "Es difícil plantarle cara con el resto. Prioriza la profundidad y la dirección "
                        "cruzada para neutralizar la velocidad, en lugar de buscar el winner desde el primer golpe."
                    ),
                    "metric_value": round(fs_b * 100, 1),
                    "metric_label": "% 1er Servicio",
                })

        # ── 3. Ace rate (serving power) ──
        ace_b = _v(stats_b, "ace_rate")
        if ace_b is not None:
            if ace_b >= 0.10:
                rival_strengths.append({
                    "type": "strength", "category": "serve", "severity": "high",
                    "title": "Sacador muy peligroso (muchos aces)",
                    "description": (
                        f"{player_b} hace ace en el {ace_b*100:.1f}% de sus puntos de servicio. "
                        "Estudia sus patrones de saque en el calentamiento. Generalmente el T en deuce y "
                        "el cuerpo en ventaja son sus zonas preferidas. Mantén buena posición de lectura "
                        "en lugar de anticiparte a uno de los lados."
                    ),
                    "metric_value": round(ace_b * 100, 1),
                    "metric_label": "% Aces",
                })
            elif ace_b <= 0.04:
                rival_weaknesses.append({
                    "type": "weakness", "category": "serve", "severity": "low",
                    "title": "Servicio sin mucho poder (pocos aces)",
                    "description": (
                        f"{player_b} hace ace en solo el {ace_b*100:.1f}% de sus puntos. "
                        "Su servicio no es una arma directa — puedes planificar un retorno activo "
                        "con confianza y construir el punto desde la primera bola."
                    ),
                    "metric_value": round(ace_b * 100, 1),
                    "metric_label": "% Aces",
                })

        # ── 4. Break point saved percentage (mental toughness) ──
        bp_b = _v(stats_b, "bp_saved_pct")
        if bp_b is not None:
            if bp_b < 0.58:
                rival_weaknesses.append({
                    "type": "weakness", "category": "mental", "severity": "high",
                    "title": "Vulnerable bajo presión de break point",
                    "description": (
                        f"{player_b} salva solo el {bp_b*100:.1f}% de los break points en su contra. "
                        "Construye puntos largos y agotadores para llevarlo a situaciones de presión. "
                        "En los puntos de break, juega con margen y profundidad — el rival tiende a 'apretarse'."
                    ),
                    "metric_value": round(bp_b * 100, 1),
                    "metric_label": "% BP Salvados",
                })
                recommendations.append({
                    "type": "strength", "category": "mental", "severity": "high",
                    "title": "Forzar situaciones de break point",
                    "description": (
                        "El rival falla bajo presión en los puntos de break. Asegúrate de llegar a break point "
                        "con buen margen de energía. Usa el punto de break para jugar conservador/profundo — "
                        "el error vendrá del rival."
                    ),
                    "metric_value": round(bp_b * 100, 1),
                    "metric_label": "% BP Salvados rival",
                })
            elif bp_b >= 0.70:
                rival_strengths.append({
                    "type": "strength", "category": "mental", "severity": "high",
                    "title": "Muy sólido en los break points",
                    "description": (
                        f"{player_b} salva el {bp_b*100:.1f}% de los break points. "
                        "Es muy difícil romper su saque desde puntos de presión directa. "
                        "En lugar de buscar el break con riesgo alto, construye ventaja acumulando "
                        "juegos de saque sólidos primero."
                    ),
                    "metric_value": round(bp_b * 100, 1),
                    "metric_label": "% BP Salvados",
                })

        # ── 5. Return points won (return game) ──
        rpw_b = _v(stats_b, "return_points_won_pct")
        if rpw_b is not None:
            if rpw_b >= 0.40:
                rival_strengths.append({
                    "type": "strength", "category": "return", "severity": "high",
                    "title": "Restador muy efectivo",
                    "description": (
                        f"{player_b} gana el {rpw_b*100:.1f}% de los puntos de resto. "
                        "Varía la velocidad y la dirección de tu servicio constantemente. "
                        "Un saque al cuerpo puede ser muy efectivo para interrumpir su ritmo de resto."
                    ),
                    "metric_value": round(rpw_b * 100, 1),
                    "metric_label": "% Puntos Resto Ganados",
                })
            elif rpw_b <= 0.35:
                rival_weaknesses.append({
                    "type": "weakness", "category": "return", "severity": "medium",
                    "title": "Débil en el juego de resto",
                    "description": (
                        f"{player_b} gana solo el {rpw_b*100:.1f}% de los puntos de resto. "
                        "Sirve con confianza y construye el punto desde la ventaja del saque. "
                        "Un primer saque potente hacia el T puede darte el punto directo o la iniciativa inmediata."
                    ),
                    "metric_value": round(rpw_b * 100, 1),
                    "metric_label": "% Puntos Resto Ganados",
                })

        # ── 6. Surface ELO adaptation ──
        elo_global_b = _v(stats_b, "elo_global")
        elo_surface_b = _v(stats_b, "elo_surface")
        if elo_global_b is not None and elo_surface_b is not None:
            diff = elo_global_b - elo_surface_b
            if diff >= 100:
                rival_weaknesses.append({
                    "type": "weakness", "category": "surface", "severity": "high",
                    "title": f"Poca adaptación a {surface_norm}",
                    "description": (
                        f"El ELO global de {player_b} es {elo_global_b:.0f} pero su ELO específico "
                        f"en {surface_norm} es {elo_surface_b:.0f} (diferencia de {diff:.0f} puntos). "
                        "Esta superficie no es su hábitat natural — puede cometer más errores no forzados "
                        "y tener menos confianza en sus golpes de fondo."
                    ),
                    "metric_value": round(diff, 0),
                    "metric_label": f"Diferencia ELO global vs {surface_norm}",
                })
            elif elo_surface_b is not None and elo_global_b is not None and (elo_surface_b - elo_global_b) >= 100:
                rival_strengths.append({
                    "type": "strength", "category": "surface", "severity": "high",
                    "title": f"Especialista en {surface_norm}",
                    "description": (
                        f"El ELO de {player_b} en {surface_norm} ({elo_surface_b:.0f}) supera en "
                        f"{elo_surface_b - elo_global_b:.0f} puntos a su ELO global ({elo_global_b:.0f}). "
                        "Es un rival particularmente peligroso en esta superficie — adapta tu juego "
                        "priorizando la consistencia sobre el riesgo."
                    ),
                    "metric_value": round(elo_surface_b - elo_global_b, 0),
                    "metric_label": f"Ventaja ELO en {surface_norm}",
                })

        # ── 7. Win rate on surface ──
        wr_surf_b = _v(stats_b, "win_rate_surface")
        if wr_surf_b is not None:
            if wr_surf_b < 0.50:
                rival_weaknesses.append({
                    "type": "weakness", "category": "consistency", "severity": "medium",
                    "title": f"Bajo porcentaje de victorias en {surface_norm}",
                    "description": (
                        f"{player_b} solo ha ganado el {wr_surf_b*100:.1f}% de sus partidos "
                        f"en {surface_norm}. Los números históricos están de tu lado — "
                        "juega con confianza y sin miedo."
                    ),
                    "metric_value": round(wr_surf_b * 100, 1),
                    "metric_label": f"% Victorias en {surface_norm}",
                })
            elif wr_surf_b >= 0.70:
                rival_strengths.append({
                    "type": "strength", "category": "consistency", "severity": "medium",
                    "title": f"Historial dominante en {surface_norm}",
                    "description": (
                        f"{player_b} gana el {wr_surf_b*100:.1f}% de sus partidos en {surface_norm}. "
                        "Su historial en esta superficie es muy sólido — necesitarás elevar tu nivel "
                        "para competirle de tú a tú."
                    ),
                    "metric_value": round(wr_surf_b * 100, 1),
                    "metric_label": f"% Victorias en {surface_norm}",
                })

        # ── Determine overall advantage ───────────────────────────────
        score_a = 0
        score_b = 0

        # ELO comparison
        elo_a = _v(stats_a, "elo_surface") or _v(stats_a, "elo_global") or 1500.0
        elo_b = _v(stats_b, "elo_surface") or _v(stats_b, "elo_global") or 1500.0
        if elo_a > elo_b + 50:
            score_a += 2
        elif elo_b > elo_a + 50:
            score_b += 2

        # Win rate comparison
        wr_a = _v(stats_a, "win_rate_surface") or _v(stats_a, "win_rate") or 0.5
        wr_b = _v(stats_b, "win_rate_surface") or _v(stats_b, "win_rate") or 0.5
        if wr_a > wr_b + 0.05:
            score_a += 1
        elif wr_b > wr_a + 0.05:
            score_b += 1

        # Number of weaknesses detected
        score_a += len(rival_weaknesses)
        score_b += len(rival_strengths)

        if score_a > score_b + 1:
            overall_advantage = "A"
            advantage_summary = (
                f"Los datos favorecen a {player_a} en {surface_norm}. "
                f"El análisis detecta {len(rival_weaknesses)} debilidad(es) explotable(s) en el juego de {player_b}."
            )
        elif score_b > score_a + 1:
            overall_advantage = "B"
            advantage_summary = (
                f"{player_b} parte como favorito en {surface_norm} según el análisis estadístico. "
                f"El partido requerirá un rendimiento táctico elevado de {player_a}."
            )
        else:
            overall_advantage = "even"
            advantage_summary = (
                f"Partido muy equilibrado en {surface_norm}. "
                "Los datos muestran fortalezas y debilidades compensadas para ambos jugadores. "
                "Los detalles tácticos y la gestión de la presión serán decisivos."
            )

        return {
            "player_a": player_a,
            "player_b": player_b,
            "surface": surface_norm,
            "stats_a": stats_a,
            "stats_b": stats_b,
            "rival_weaknesses": rival_weaknesses,
            "rival_strengths": rival_strengths,
            "recommendations": recommendations,
            "overall_advantage": overall_advantage,
            "advantage_summary": advantage_summary,
        }


@lru_cache(maxsize=1)
def get_player_service() -> PlayerService:
    return PlayerService()
