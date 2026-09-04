# matchpoint/sim_engine.py
"""
Tennis match simulation engine.

Pure functions for simulating tennis matches point-by-point.
All randomness is controlled via an RNG object for reproducibility.

Timeline modes:
- "none": Only final score
- "games": Events per game
- "points": Events per point (verbose)
"""
from __future__ import annotations

import random
from typing import Literal, Optional, Union


# Tennis point names
POINT_NAMES = {0: "0", 1: "15", 2: "30", 3: "40"}
# Small pressure-based adjustment applied in clutch moments.
CLUTCH_MAX_SHIFT = 0.03
# Smooth serve-point penalty applied as the match gets longer.
FATIGUE_MAX_PENALTY = 0.025
FATIGUE_FULL_EFFECT_GAMES = 36


def simulate_point(p_server: float, rng: random.Random) -> bool:
    """
    Simulate a single point.
    
    Args:
        p_server: Probability that server wins the point
        rng: Random number generator for reproducibility
        
    Returns:
        True if server wins the point, False if returner wins
    """
    return rng.random() < p_server


def _apply_clutch_adjustment(p_server: float, pressure: float) -> float:
    """
    Apply a small deterministic clutch shift to point probability.

    The shift is intentionally mild and bounded:
    - Stronger server (p_server > 0.5) gets a slight boost under pressure.
    - Weaker server (p_server < 0.5) gets a slight penalty under pressure.
    """
    if pressure <= 0.0:
        return p_server
    # How far from coin-flip this server already is.
    edge = min(1.0, abs(p_server - 0.5) / 0.25)
    direction = 1.0 if p_server >= 0.5 else -1.0
    shift = CLUTCH_MAX_SHIFT * min(1.0, pressure) * edge
    return max(0.02, min(0.98, p_server + direction * shift))


def _match_fatigue_factor(completed_games: int) -> float:
    """Return match fatigue factor [0, 1] from completed games."""
    if completed_games <= 0:
        return 0.0
    return min(1.0, completed_games / FATIGUE_FULL_EFFECT_GAMES)


def _apply_fatigue_adjustment(p_server: float, fatigue_factor: float) -> float:
    """Apply a mild deterministic fatigue penalty to serve point probability."""
    if fatigue_factor <= 0.0:
        return p_server
    penalty = FATIGUE_MAX_PENALTY * min(1.0, fatigue_factor)
    return max(0.02, min(0.98, p_server - penalty))


def _game_pressure_factor(server_pts: int, returner_pts: int) -> float:
    """Return pressure level [0, 1] for the next point in a regular game."""
    # Deuce/advantage points are the highest-pressure moments.
    if server_pts >= 3 and returner_pts >= 3:
        return 1.0

    # Break points before deuce (0-40, 15-40, 30-40).
    if returner_pts == 3 and server_pts <= 2:
        return 0.5 + 0.15 * server_pts

    # Game points before deuce (40-0, 40-15, 40-30).
    if server_pts == 3 and returner_pts <= 2:
        return 0.35 + 0.10 * returner_pts

    return 0.0


def _tiebreak_pressure_factor(pts_a: int, pts_b: int) -> float:
    """Return pressure level [0, 1] for the next point in a tiebreak."""
    hi = max(pts_a, pts_b)
    diff = abs(pts_a - pts_b)

    # Set-point situations (one player can close the tiebreak on next point).
    if hi >= 6 and diff == 1:
        return 1.0

    # Late tiebreak, both close.
    if hi >= 5 and diff <= 1:
        return 0.7

    # Mid/late tiebreak with narrow gap.
    if hi >= 4 and diff <= 1:
        return 0.45

    return 0.0


def simulate_game(
    p_server: float,
    rng: random.Random,
    track_points: bool = False,
    fatigue_factor: float = 0.0,
) -> tuple[bool, Optional[list[dict]]]:
    """
    Simulate a single game with deuce/advantage rules.
    
    Args:
        p_server: Probability server wins each point
        rng: Random number generator
        track_points: Whether to track individual point results
        
    Returns:
        (server_won, points_log)
        - server_won: True if server won the game
        - points_log: List of point events if track_points=True, else None
    """
    server_pts = 0
    returner_pts = 0
    points_log = [] if track_points else None
    point_num = 0
    
    while True:
        point_num += 1
        pressure = _game_pressure_factor(server_pts, returner_pts)
        p_server_fatigued = _apply_fatigue_adjustment(p_server, fatigue_factor)
        p_server_eff = _apply_clutch_adjustment(p_server_fatigued, pressure)
        server_wins = simulate_point(p_server_eff, rng)
        
        if server_wins:
            server_pts += 1
        else:
            returner_pts += 1
        
        # Track point
        if track_points:
            points_log.append({
                "point": point_num,
                "winner": "server" if server_wins else "returner",
                "score": _game_score_str(server_pts, returner_pts),
                "pressure": round(pressure, 3),
                "fatigue_factor": round(fatigue_factor, 3),
                "p_server_eff": round(p_server_eff, 4),
            })
        
        # Check for game winner
        if server_pts >= 4 and server_pts - returner_pts >= 2:
            return (True, points_log)
        if returner_pts >= 4 and returner_pts - server_pts >= 2:
            return (False, points_log)


def _game_score_str(server_pts: int, returner_pts: int) -> str:
    """Convert point counts to tennis score string."""
    if server_pts < 4 and returner_pts < 4:
        return f"{POINT_NAMES[server_pts]}-{POINT_NAMES[returner_pts]}"
    elif server_pts == returner_pts:
        return "Deuce"
    elif server_pts > returner_pts:
        return "Adv-Server"
    else:
        return "Adv-Returner"


def simulate_tiebreak(
    p_serve_a: float,
    p_serve_b: float,
    rng: random.Random,
    first_server: Literal["A", "B"] = "A",
    track_points: bool = False,
    fatigue_factor: float = 0.0,
) -> tuple[Literal["A", "B"], Optional[list[dict]]]:
    """
    Simulate a tiebreak.
    
    Tiebreak serving pattern:
    - First server serves 1 point
    - Then alternating 2 points each
    - Win by 2, first to 7
    
    Args:
        p_serve_a: Probability A wins point when A serves
        p_serve_b: Probability B wins point when B serves
        rng: Random number generator
        first_server: Who serves first
        track_points: Whether to track points
        
    Returns:
        (winner, points_log)
    """
    pts_a = 0
    pts_b = 0
    points_log = [] if track_points else None
    point_num = 0
    server = first_server
    
    # Serving pattern: 1, then 2-2-2...
    points_this_server = 0
    first_serve_done = False
    
    while True:
        point_num += 1
        p_server_base = p_serve_a if server == "A" else p_serve_b
        pressure = _tiebreak_pressure_factor(pts_a, pts_b)
        p_server_fatigued = _apply_fatigue_adjustment(p_server_base, fatigue_factor)
        p_server_eff = _apply_clutch_adjustment(p_server_fatigued, pressure)
        server_wins = simulate_point(p_server_eff, rng)
        
        if server_wins:
            if server == "A":
                pts_a += 1
            else:
                pts_b += 1
        else:
            if server == "A":
                pts_b += 1
            else:
                pts_a += 1
        
        if track_points:
            points_log.append({
                "point": point_num,
                "server": server,
                "winner": "A" if (server_wins and server == "A") or (not server_wins and server == "B") else "B",
                "score": f"{pts_a}-{pts_b}",
                "pressure": round(pressure, 3),
                "fatigue_factor": round(fatigue_factor, 3),
                "p_server_eff": round(p_server_eff, 4),
            })
        
        # Check for tiebreak winner (first to 7, win by 2)
        if pts_a >= 7 and pts_a - pts_b >= 2:
            return ("A", points_log)
        if pts_b >= 7 and pts_b - pts_a >= 2:
            return ("B", points_log)
        
        # Update server
        points_this_server += 1
        if not first_serve_done:
            if points_this_server == 1:
                first_serve_done = True
                points_this_server = 0
                server = "B" if server == "A" else "A"
        else:
            if points_this_server == 2:
                points_this_server = 0
                server = "B" if server == "A" else "A"


def simulate_set(
    p_serve_a: float,
    p_serve_b: float,
    rng: random.Random,
    first_server: Literal["A", "B"] = "A",
    track_games: bool = False,
    track_points: bool = False,
    completed_games_before_set: int = 0,
    enable_fatigue: bool = True,
) -> dict:
    """
    Simulate a set.
    
    Rules: Win with 6 games and 2+ lead, or tiebreak at 6-6.
    
    Args:
        p_serve_a: P(A wins point when A serves)
        p_serve_b: P(B wins point when B serves)
        rng: Random generator
        first_server: Who serves first in set
        track_games: Include game-level timeline
        track_points: Include point-level timeline
        
    Returns:
        {
            "games_a": int,
            "games_b": int,
            "winner": "A" | "B",
            "score": "6-4" | "7-6",
            "tiebreak": None | {"score": "7-5", "timeline": [...]} 
            "timeline": [...] if track_games
        }
    """
    games_a = 0
    games_b = 0
    server = first_server
    timeline = [] if track_games else None
    game_num = 0
    
    while True:
        game_num += 1
        
        # Check for tiebreak
        if games_a == 6 and games_b == 6:
            fatigue_factor = (
                _match_fatigue_factor(completed_games_before_set + games_a + games_b)
                if enable_fatigue else 0.0
            )
            tb_winner, tb_log = simulate_tiebreak(
                p_serve_a, p_serve_b, rng, 
                first_server=server, 
                track_points=track_points,
                fatigue_factor=fatigue_factor,
            )
            if tb_winner == "A":
                games_a += 1
            else:
                games_b += 1
            
            if track_games:
                timeline.append({
                    "game": game_num,
                    "type": "tiebreak",
                    "server": server,
                    "winner": tb_winner,
                    "score": f"{games_a}-{games_b}",
                    "points": tb_log,
                    "fatigue_factor": round(fatigue_factor, 3),
                })
            
            winner = "A" if games_a > games_b else "B"
            return {
                "games_a": games_a,
                "games_b": games_b,
                "winner": winner,
                "score": f"{games_a}-{games_b}",
                "tiebreak": True,
                "timeline": timeline,
            }
        
        # Regular game
        p_server = p_serve_a if server == "A" else p_serve_b
        fatigue_factor = (
            _match_fatigue_factor(completed_games_before_set + games_a + games_b)
            if enable_fatigue else 0.0
        )
        server_won, pts_log = simulate_game(
            p_server,
            rng,
            track_points=track_points,
            fatigue_factor=fatigue_factor,
        )
        
        if server == "A":
            if server_won:
                games_a += 1
            else:
                games_b += 1
        else:
            if server_won:
                games_b += 1
            else:
                games_a += 1
        
        game_winner = (server if server_won else ("B" if server == "A" else "A"))
        
        if track_games:
            timeline.append({
                "game": game_num,
                "type": "game",
                "server": server,
                "winner": game_winner,
                "score": f"{games_a}-{games_b}",
                "points": pts_log,
                "fatigue_factor": round(fatigue_factor, 3),
            })
        
        # Check for set winner
        if games_a >= 6 and games_a - games_b >= 2:
            return {
                "games_a": games_a,
                "games_b": games_b,
                "winner": "A",
                "score": f"{games_a}-{games_b}",
                "tiebreak": False,
                "timeline": timeline,
            }
        if games_b >= 6 and games_b - games_a >= 2:
            return {
                "games_a": games_a,
                "games_b": games_b,
                "winner": "B",
                "score": f"{games_a}-{games_b}",
                "tiebreak": False,
                "timeline": timeline,
            }
        
        # Switch server
        server = "B" if server == "A" else "A"


def simulate_match(
    p_serve_a: float,
    p_serve_b: float,
    rng: random.Random,
    best_of: int = 3,
    first_server: Union[Literal["A", "B", "random"], None] = "random",
    timeline_mode: Literal["none", "games", "points"] = "games",
    enable_fatigue: bool = True,
) -> dict:
    """
    Simulate a complete tennis match.
    
    Args:
        p_serve_a: P(A wins point when A serves)
        p_serve_b: P(B wins point when B serves)
        rng: Random generator (for reproducibility)
        best_of: 3 or 5 sets
        first_server: "A", "B", or "random"
        timeline_mode: "none", "games", or "points"
        
    Returns:
        {
            "winner": "A" | "B",
            "sets_a": int,
            "sets_b": int,
            "sets": ["6-4", "3-6", "7-5"],
            "timeline": [...] | None
        }
    """
    sets_to_win = (best_of + 1) // 2  # 2 for best_of=3, 3 for best_of=5
    sets_a = 0
    sets_b = 0
    sets_scores = []
    match_timeline = [] if timeline_mode != "none" else None
    
    # Determine first server
    if first_server == "random":
        current_server: Literal["A", "B"] = "A" if rng.random() < 0.5 else "B"
    else:
        current_server = first_server
    
    set_num = 0
    while sets_a < sets_to_win and sets_b < sets_to_win:
        set_num += 1
        
        track_games = timeline_mode in ("games", "points")
        track_points = timeline_mode == "points"
        
        set_result = simulate_set(
            p_serve_a, p_serve_b, rng,
            first_server=current_server,
            track_games=track_games,
            track_points=track_points,
            completed_games_before_set=sum(
                int(score.split("-")[0]) + int(score.split("-")[1])
                for score in sets_scores
            ),
            enable_fatigue=enable_fatigue,
        )
        
        sets_scores.append(set_result["score"])
        if set_result["winner"] == "A":
            sets_a += 1
        else:
            sets_b += 1
        
        if match_timeline is not None:
            match_timeline.append({
                "set": set_num,
                "score": set_result["score"],
                "winner": set_result["winner"],
                "tiebreak": set_result["tiebreak"],
                "games": set_result["timeline"],
            })
        
        # Next set: who served last in set now receives first
        # Simple rule: total games in set determines who serves next
        total_games = set_result["games_a"] + set_result["games_b"]
        if total_games % 2 == 1:
            current_server = "B" if current_server == "A" else "A"
    
    return {
        "winner": "A" if sets_a > sets_b else "B",
        "sets_a": sets_a,
        "sets_b": sets_b,
        "sets": sets_scores,
        "timeline": match_timeline,
    }
