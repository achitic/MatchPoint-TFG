"""
FastAPI application for MatchPoint predictions.
"""
import logging
import uuid
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.schemas import (
    PredictRequest,
    PredictResponse,
    HealthResponse,
    PlayersResponse,
    DebugInfo,
    FeatureDiff,
    ExplainInfo,
    ExplainContributor,
    SimulateRequest,
    SimulateResponse,
    SimulationParams,
    SimulateResult,
    InPlayInitRequest,
    InPlayUpdateRequest,
    InPlayStateResponse,
    InPlayDeleteResponse,
    ModelInfo,
    ModelsResponse,
    TournamentInfo,
    TournamentsResponse,
    TournamentRequest,
    TournamentResponse,
    TournamentMeta,
    TournamentRound,
    TournamentMatch,
    TournamentMatchParams,
    TournamentMatchResult,
    PlayerStanding,
    TournamentMonteCarloRequest,
    TournamentMonteCarloResponse,
    ScoutingReportResponse,
    TacticalInsight,
    ScoutingCompareStats,
    PlayerProfileResponse,
    PlayerHistoryResponse,
    PlayerServeStatsResponse,
)
from backend.services.predict_service import get_service
from backend.services.simulate_service import get_simulate_service
from backend.services.tournament_service import get_tournament_service, get_models_catalog
from backend.services.player_service import get_player_service
from backend.settings import AVAILABLE_SURFACES, CORS_ORIGINS

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


def _internal_error(context: str, exc: Exception) -> HTTPException:
    error_id = uuid.uuid4().hex[:10]
    logger.exception("%s [error_id=%s]: %s", context, error_id, exc)
    return HTTPException(
        status_code=500,
        detail=f"Internal server error. Reference: {error_id}",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Precargando servicios de MatchPoint...")
    try:
        svc = get_service()
        players = svc.get_players()
        print(f"PredictService cargado: {len(players)} jugadores")
    except Exception as e:
        print(f"Aviso: PredictService no se pudo precargar: {e}")

    try:
        get_simulate_service()
        print("SimulateService cargado")
    except Exception as e:
        print(f"Aviso: SimulateService no se pudo precargar: {e}")

    try:
        get_tournament_service()
        print("TournamentService cargado")
    except Exception as e:
        print(f"Aviso: TournamentService no se pudo precargar: {e}")

    try:
        psvc = get_player_service()
        psvc._load_matches()
        print("PlayerService cargado")
    except Exception as e:
        print(f"Aviso: PlayerService no se pudo precargar: {e}")

    print("MatchPoint API lista.")
    yield


app = FastAPI(
    title="MatchPoint API",
    description="Tennis match prediction and tournament simulation API",
    version="1.3.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.get("/players", response_model=PlayersResponse)
def get_players():
    """Get list of available players."""
    try:
        service = get_service()
        players = service.get_players()
        return PlayersResponse(players=players, count=len(players))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading players: {str(e)}")


@app.get("/players/search")
def search_players(
    q: str = Query(..., min_length=1, description="Search query (name fragment)"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    """
    Fuzzy search players by name fragment (case-insensitive).
    Prefix matches are returned first, then substring matches.
    """
    try:
        service = get_player_service()
        results = service.search_players(query=q, limit=limit)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as e:
        logger.exception("Error in /players/search")
        raise HTTPException(status_code=500, detail=f"Player search error: {str(e)}")


@app.get("/models", response_model=ModelsResponse)
def get_models():
    """Get catalog of available models with Spanish labels."""
    catalog = get_models_catalog()
    return ModelsResponse(
        models=[ModelInfo(**m) for m in catalog]
    )


@app.get("/surfaces")
def get_surfaces():
    """Get list of available surfaces."""
    return {"surfaces": AVAILABLE_SURFACES}


@app.post("/predict", response_model=PredictResponse)
@limiter.limit("60/minute")
def predict(request: Request, body: PredictRequest):
    """Make a match prediction."""
    try:
        service = get_service()
        result = service.predict(
            player_a=body.player_a,
            player_b=body.player_b,
            surface=body.surface,
            model=body.model,
            as_of=body.as_of,
            debug=body.debug,
        )

        debug_info = None
        if result.get("debug"):
            d = result["debug"]
            debug_info = DebugInfo(
                features_a=d["features_a"],
                features_b=d["features_b"],
                top_diffs=[FeatureDiff(**diff) for diff in d["top_diffs"]],
            )

        explain_info = None
        if result.get("explain"):
            e = result["explain"]
            explain_info = ExplainInfo(
                method=e["method"],
                top_contributors=[ExplainContributor(**c) for c in e["top_contributors"]],
            )

        return PredictResponse(
            player_a=result["player_a"],
            player_b=result["player_b"],
            surface=result["surface"],
            model=result["model"],
            as_of_used=result["as_of_used"],
            p_a=result["p_a"],
            p_b=result["p_b"],
            warnings=result.get("warnings", []),
            debug=debug_info,
            explain=explain_info,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data file not found: {str(e)}")
    except Exception as e:
        logger.exception("Error in /predict")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.post("/simulate_match", response_model=SimulateResponse)
@limiter.limit("30/minute")
def simulate_match(request: Request, body: SimulateRequest):
    """
    Simulate a tennis match point-by-point.

    Uses the existing ML model to get match probability, then converts
    to point-level probabilities using a proxy method (v0: logit+tanh).

    Timeline modes:
    - "none": Only final score
    - "games": Events per game (default)
    - "points": Events per point (verbose)

    Use `seed` for reproducibility - same seed produces identical results.
    """
    try:
        service = get_simulate_service()
        result = service.simulate(
            player_a=body.player_a,
            player_b=body.player_b,
            surface=body.surface,
            model=body.model,
            as_of=body.as_of,
            best_of=body.best_of,
            seed=body.seed,
            first_server=body.first_server,
            timeline_mode=body.timeline_mode,
            engine_mode=body.engine_mode,
            p_a_override=body.p_a_override,
        )

        return SimulateResponse(
            player_a=result["player_a"],
            player_b=result["player_b"],
            surface=result["surface"],
            model=result["model"],
            as_of_used=result["as_of_used"],
            p_a=result["p_a"],
            p_b=result["p_b"],
            seed_used=result["seed_used"],
            warnings=result.get("warnings", []),
            params=SimulationParams(**result["params"]),
            result=SimulateResult(**result["result"]),
            timeline=result.get("timeline"),
            debug=None,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data file not found: {str(e)}")
    except Exception as e:
        logger.exception("Error in /simulate_match")
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


@app.post("/inplay/init", response_model=InPlayStateResponse)
@limiter.limit("10/minute")
def inplay_init(request: Request, body: InPlayInitRequest):
    """Initialize in-play bayesian state for a match."""
    try:
        service = get_simulate_service()
        state = service.init_inplay(
            player_a=body.player_a,
            player_b=body.player_b,
            surface=body.surface,
            model=body.model,
            as_of=body.as_of,
            best_of=body.best_of,
            first_server=body.first_server,
        )
        return InPlayStateResponse(**state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _internal_error("Error in /inplay/init", e)


@app.post("/inplay/update", response_model=InPlayStateResponse)
def inplay_update(request: InPlayUpdateRequest):
    """Update in-play bayesian state with one completed game event."""
    try:
        service = get_simulate_service()
        state = service.update_inplay(
            match_id=request.match_id,
            server=request.server,
            game_winner=request.game_winner,
            server_points_won=request.server_points_won,
            server_points_lost=request.server_points_lost,
            is_tiebreak=request.is_tiebreak,
        )
        return InPlayStateResponse(**state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _internal_error("Error in /inplay/update", e)


@app.get("/inplay/state/{match_id}", response_model=InPlayStateResponse)
def inplay_state(match_id: str):
    """Get current in-play bayesian state by match id."""
    try:
        service = get_simulate_service()
        state = service.get_inplay_state(match_id=match_id)
        return InPlayStateResponse(**state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _internal_error("Error in /inplay/state", e)


@app.delete("/inplay/{match_id}", response_model=InPlayDeleteResponse)
def inplay_delete(match_id: str):
    """Delete a live tracking session explicitly."""
    try:
        service = get_simulate_service()
        deleted = service.delete_inplay_state(match_id)
        return InPlayDeleteResponse(match_id=match_id, deleted=deleted)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise _internal_error("Error in DELETE /inplay", e)


# ============== TOURNAMENT ENDPOINTS ==============

@app.get("/tournaments", response_model=TournamentsResponse)
def get_tournaments(
    year: Optional[int] = Query(None, description="Filter by year"),
    surface: Optional[str] = Query(None, description="Filter by surface"),
    level: Optional[str] = Query(None, description="Filter by level (G, M, A, etc.)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
):
    """
    Get catalog of real tournaments from historical data.
    
    Filters:
    - year: 2020, 2021, 2022, ...
    - surface: Hard, Clay, Grass
    - level: G=Grand Slam, M=Masters, A=ATP, F=Finals, etc.
    """
    try:
        service = get_tournament_service()
        tournaments = service.get_tournaments(
            year=year,
            surface=surface,
            level=level,
            limit=limit,
        )
        return TournamentsResponse(
            tournaments=[TournamentInfo(**t) for t in tournaments],
            count=len(tournaments),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading tournaments: {str(e)}")


@app.post("/tournament/simulate", response_model=TournamentResponse)
@limiter.limit("20/minute")
def simulate_tournament(request: Request, body: TournamentRequest):
    """
    Simulate a single-elimination tournament.

    - size: 8 or 16 players
    - seeding: 'elo' (by ELO rating) or 'random'
    - timeline_mode: 'none' (faster) or 'games' (detailed)
    - seed: for reproducibility

    If tournament_id is provided, uses real tournament metadata from catalog.
    """
    try:
        service = get_tournament_service()
        result = service.simulate_tournament(
            players=body.players,
            size=body.size,
            surface=body.surface,
            model=body.model,
            as_of=body.as_of,
            best_of=body.best_of,
            seed=body.seed,
            timeline_mode=body.timeline_mode,
            seeding=body.seeding,
            tournament_id=body.tournament_id,
        )

        # Convert standings dict
        standings_converted = {
            p: PlayerStanding(**s) for p, s in result["standings"].items()
        }

        # Convert rounds
        rounds_converted = []
        for r in result["rounds"]:
            matches_converted = []
            for m in r["matches"]:
                matches_converted.append(TournamentMatch(
                    player_a=m["player_a"],
                    player_b=m["player_b"],
                    p_a=m["p_a"],
                    p_b=m["p_b"],
                    params=TournamentMatchParams(**m["params"]),
                    result=TournamentMatchResult(**m["result"]),
                    timeline=m.get("timeline"),
                ))
            rounds_converted.append(TournamentRound(
                round=r["round"],
                name=r["name"],
                matches=matches_converted,
            ))

        return TournamentResponse(
            tournament=TournamentMeta(**result["tournament"]),
            surface=result["surface"],
            model=result["model"],
            as_of_used=result["as_of_used"],
            seed_used=result["seed_used"],
            seeding=result["seeding"],
            size=result["size"],
            best_of=result["best_of"],
            warnings=result["warnings"],
            bracket_order=result["bracket_order"],
            rounds=rounds_converted,
            champion=result["champion"],
            standings=standings_converted,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data file not found: {str(e)}")
    except Exception as e:
        logger.exception("Error in /tournament/simulate")
        raise HTTPException(status_code=500, detail=f"Tournament simulation error: {str(e)}")

@app.post("/tournament/simulate_mc", response_model=TournamentMonteCarloResponse)
@limiter.limit("10/minute")
def simulate_tournament_monte_carlo(request: Request, body: TournamentMonteCarloRequest):
    """
    Run repeated Monte Carlo simulations for a tournament and aggregate championship odds.
    """
    try:
        service = get_tournament_service()
        result = service.simulate_monte_carlo(
            players=body.players,
            size=body.size,
            surface=body.surface,
            model=body.model,
            as_of=body.as_of,
            best_of=body.best_of,
            seed=body.seed,
            seeding=body.seeding,
            tournament_id=body.tournament_id,
            n_simulations=body.n_simulations,
        )
        return TournamentMonteCarloResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data file not found: {str(e)}")
    except Exception as e:
        logger.exception("Error in /tournament/simulate_mc")
        raise HTTPException(status_code=500, detail=f"Monte Carlo simulation error: {str(e)}")


@app.get("/h2h")
def head_to_head(
    player_a: str = Query(..., description="First player name"),
    player_b: str = Query(..., description="Second player name"),
    limit: int = Query(20, ge=1, le=100, description="Max matches to return"),
):
    """
    Get historical head-to-head record between two players.

    Returns:
    - stats: total matches, wins per player, breakdown by surface
    - matches: list of recent encounters (date, tournament, surface, winner, score)
    """
    try:
        import pandas as pd

        # El H2H reutiliza el DataFrame cacheado para no releer el parquet.
        service = get_player_service()
        df = service._load_matches()

        # Filter matches involving both players (in either direction)
        mask = (
            ((df["winner_name"] == player_a) & (df["loser_name"] == player_b)) |
            ((df["winner_name"] == player_b) & (df["loser_name"] == player_a))
        )
        h2h_df = df[mask].copy()

        if h2h_df.empty:
            return {
                "player_a": player_a,
                "player_b": player_b,
                "stats": {"total": 0, "wins_a": 0, "wins_b": 0, "by_surface": {}},
                "matches": [],
            }

        h2h_df = h2h_df.sort_values("tourney_date", ascending=False)

        wins_a = int((h2h_df["winner_name"] == player_a).sum())
        wins_b = int((h2h_df["winner_name"] == player_b).sum())
        total = wins_a + wins_b

        by_surface: dict = {}
        for surf, grp in h2h_df.groupby("surface"):
            if pd.isna(surf):
                continue
            s_wins_a = int((grp["winner_name"] == player_a).sum())
            s_wins_b = int((grp["winner_name"] == player_b).sum())
            by_surface[str(surf)] = {
                "wins_a": s_wins_a,
                "wins_b": s_wins_b,
                "total": s_wins_a + s_wins_b,
            }

        recent = h2h_df.head(limit)
        matches = []
        for _, row in recent.iterrows():
            score = ""
            if "score" in row and pd.notna(row["score"]):
                score = str(row["score"])
            tourney_name = str(row.get("tourney_name", "")) if pd.notna(row.get("tourney_name", "")) else ""
            matches.append({
                "date": row["tourney_date"].strftime("%Y-%m-%d"),
                "tournament": tourney_name,
                "surface": str(row.get("surface", "")) if pd.notna(row.get("surface", "")) else "",
                "winner": str(row["winner_name"]),
                "score": score,
            })

        return {
            "player_a": player_a,
            "player_b": player_b,
            "stats": {
                "total": total,
                "wins_a": wins_a,
                "wins_b": wins_b,
                "by_surface": by_surface,
            },
            "matches": matches,
        }

    except Exception as e:
        logger.exception("Error in /h2h")
        raise HTTPException(status_code=500, detail=f"Error al cargar H2H: {str(e)}")


# ============== SCOUTING / RIVAL ANALYSIS ENDPOINT ==============

@app.get("/scouting", response_model=ScoutingReportResponse)
def scouting_report(
    player_a: str = Query(..., description="Your player (preparing the match)"),
    player_b: str = Query(..., description="The rival to scout"),
    surface: str = Query(..., description="Surface: Hard, Clay, or Grass"),
):
    """
    Generate a tactical scouting report for player_a against player_b on the given surface.

    Returns:
    - stats: serve/return/ELO statistics for both players on that surface
    - rival_weaknesses: detected weaknesses in player_b's game with tactical advice
    - rival_strengths: detected strengths in player_b's game to be aware of
    - recommendations: concrete strategic actions for player_a to exploit
    - overall_advantage: who the data favors (A / B / even)
    - advantage_summary: human-readable verdict
    """
    try:
        service = get_player_service()
        report = service.generate_scouting_report(
            name_a=player_a,
            name_b=player_b,
            surface=surface,
        )
        return ScoutingReportResponse(
            player_a=report["player_a"],
            player_b=report["player_b"],
            surface=report["surface"],
            stats_a=ScoutingCompareStats(**report["stats_a"]),
            stats_b=ScoutingCompareStats(**report["stats_b"]),
            rival_weaknesses=[TacticalInsight(**i) for i in report["rival_weaknesses"]],
            rival_strengths=[TacticalInsight(**i) for i in report["rival_strengths"]],
            recommendations=[TacticalInsight(**i) for i in report["recommendations"]],
            overall_advantage=report["overall_advantage"],
            advantage_summary=report["advantage_summary"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Data file not found: {str(e)}")
    except Exception as e:
        logger.exception("Error in /scouting")
        raise HTTPException(status_code=500, detail=f"Scouting report error: {str(e)}")


# ============== PLAYER PROFILE / HISTORY ENDPOINTS ==============

@app.get("/player/{name}/profile", response_model=PlayerProfileResponse)
def get_player_profile(name: str):
    """Get detailed profile for a player."""
    try:
        service = get_player_service()
        profile = service.get_profile(name)
        return PlayerProfileResponse(**profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in /player/profile")
        raise HTTPException(status_code=500, detail=f"Error loading player profile: {str(e)}")


@app.get("/player/{name}/history", response_model=PlayerHistoryResponse)
def get_player_history(name: str, limit: int = Query(20, ge=1, le=100)):
    """Get match history and ELO evolution points for a player."""
    try:
        service = get_player_service()
        history = service.get_history(name, limit=limit)
        return PlayerHistoryResponse(**history)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in /player/history")
        raise HTTPException(status_code=500, detail=f"Error loading player history: {str(e)}")


@app.get("/player/{name}/serve_stats", response_model=PlayerServeStatsResponse)
def get_player_serve_stats(name: str, surface: Optional[str] = Query(None)):
    """Get serve/return percentage statistics for a player."""
    try:
        service = get_player_service()
        stats = service.get_serve_stats(name, surface=surface)
        return PlayerServeStatsResponse(**stats)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error in /player/serve_stats")
        raise HTTPException(status_code=500, detail=f"Error loading player serve stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
