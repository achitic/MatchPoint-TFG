# backend/schemas.py
"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Any
from matchpoint.model_registry import DEFAULT_MODEL_ID, normalize_model_id


class PredictRequest(BaseModel):
    player_a: str = Field(..., min_length=1, description="Player A name")
    player_b: str = Field(..., min_length=1, description="Player B name")
    surface: str = Field(..., description="Surface: Hard, Clay, or Grass")
    as_of: Optional[str] = Field(None, description="Date in YYYY-MM-DD format, or null for latest")
    model: str = Field(DEFAULT_MODEL_ID, description="Model variant to use")
    debug: bool = Field(False, description="Include debug features in response")

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str) -> str:
        v = v.strip().title()
        if v not in {"Hard", "Clay", "Grass"}:
            raise ValueError("Surface must be Hard, Clay, or Grass")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return normalize_model_id(v, scope="predict")


class FeatureDiff(BaseModel):
    feature: str
    a: float
    b: float
    diff: float


class ExplainContributor(BaseModel):
    """Single feature contribution to prediction."""
    feature: str
    value: float
    coef: float
    contribution: float
    favors: Literal["A", "B"]


class ExplainInfo(BaseModel):
    """Explainability info for the selected model/method."""
    method: str = "logreg_coeffs"
    top_contributors: list[ExplainContributor]


class DebugInfo(BaseModel):
    features_a: dict[str, float]
    features_b: dict[str, float]
    top_diffs: list[FeatureDiff]


class PredictResponse(BaseModel):
    player_a: str
    player_b: str
    surface: str
    model: str
    as_of_used: str
    p_a: float
    p_b: float
    warnings: list[str] = Field(default_factory=list)
    debug: Optional[DebugInfo] = None
    explain: Optional[ExplainInfo] = None


class HealthResponse(BaseModel):
    status: str = "ok"


class PlayersResponse(BaseModel):
    players: list[str]
    count: int


# ============== SIMULATION SCHEMAS ==============

class SimulateRequest(BaseModel):
    """Request schema for match simulation."""
    player_a: str = Field(..., min_length=1, description="Player A name")
    player_b: str = Field(..., min_length=1, description="Player B name")
    surface: str = Field(..., description="Surface: Hard, Clay, or Grass")
    as_of: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    model: str = Field(DEFAULT_MODEL_ID, description="Model for match probability")
    best_of: int = Field(3, description="Best of 3 or 5 sets")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    first_server: Literal["A", "B", "random"] = Field("random", description="Who serves first")
    timeline_mode: Literal["none", "games", "points"] = Field("games", description="Timeline detail level")
    engine_mode: Literal["proxy_v0", "bayes_live_v1"] = Field(
        "proxy_v0",
        description="Simulation engine: legacy proxy or bayesian live updates",
    )
    debug: bool = Field(False, description="Include debug info")
    p_a_override: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Override ML model win probability for player A (Coach Mode). "
            "Values in [0, 1] are accepted; the simulation service applies its "
            "operational safety bounds."
        ),
    )

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str) -> str:
        v = v.strip().title()
        if v not in {"Hard", "Clay", "Grass"}:
            raise ValueError("Surface must be Hard, Clay, or Grass")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return normalize_model_id(v, scope="simulate")

    @field_validator("best_of")
    @classmethod
    def validate_best_of(cls, v: int) -> int:
        if v not in {3, 5}:
            raise ValueError("best_of must be 3 or 5")
        return v


class SimulationParams(BaseModel):
    """Parameters used for point probability proxy."""
    proxy_method: str
    surface_base: Optional[float] = None
    delta_max: Optional[float] = None
    strength_a: Optional[float] = None
    p_point_on_serve_a: Optional[float] = None
    p_point_on_serve_b: Optional[float] = None
    prior_strength: Optional[float] = None
    p_live_a: Optional[float] = None
    p_live_ci_low: Optional[float] = None
    p_live_ci_high: Optional[float] = None
    uncertainty: Optional[float] = None
    n_observations: Optional[int] = None


class SimulateResult(BaseModel):
    """Match result from simulation."""
    winner: Literal["A", "B"]
    sets: list[str]
    sets_a: int
    sets_b: int


class SimulateResponse(BaseModel):
    """Response schema for match simulation."""
    player_a: str
    player_b: str
    surface: str
    model: str
    as_of_used: str
    p_a: float
    p_b: float
    seed_used: int
    warnings: list[str] = Field(default_factory=list)
    params: SimulationParams
    result: SimulateResult
    timeline: Optional[list[Any]] = None
    debug: Optional[dict] = None


# ============== IN-PLAY SCHEMAS ==============

class InPlayInitRequest(BaseModel):
    """Request schema to initialize a live in-play match state."""
    player_a: str = Field(..., min_length=1, description="Player A name")
    player_b: str = Field(..., min_length=1, description="Player B name")
    surface: str = Field(..., description="Surface: Hard, Clay, or Grass")
    as_of: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    model: str = Field(DEFAULT_MODEL_ID, description="Model for match prior probability")
    best_of: int = Field(3, description="Best of 3 or 5 sets")
    first_server: Literal["A", "B", "random"] = Field("random", description="Who serves first")

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str) -> str:
        v = v.strip().title()
        if v not in {"Hard", "Clay", "Grass"}:
            raise ValueError("Surface must be Hard, Clay, or Grass")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return normalize_model_id(v, scope="simulate")

    @field_validator("best_of")
    @classmethod
    def validate_best_of(cls, v: int) -> int:
        if v not in {3, 5}:
            raise ValueError("best_of must be 3 or 5")
        return v


class InPlayUpdateRequest(BaseModel):
    """Request schema to update an in-play state by one completed game event."""
    match_id: str = Field(..., min_length=1)
    server: Literal["A", "B"] = Field(..., description="Server for the completed game")
    game_winner: Literal["A", "B"] = Field(..., description="Game winner")
    server_points_won: int = Field(0, ge=0, description="Points won by server in this game")
    server_points_lost: int = Field(0, ge=0, description="Points lost by server in this game")
    is_tiebreak: Optional[bool] = Field(
        None,
        description="Optional client assertion; the server derives tie-break state from the score",
    )


# ============== TOURNAMENT SCHEMAS ==============

class ModelInfo(BaseModel):
    """Model catalog entry with Spanish labels."""
    id: str
    label_es: str
    description_es: str


class ModelsResponse(BaseModel):
    """Response for GET /models."""
    models: list[ModelInfo]


class TournamentInfo(BaseModel):
    """Tournament info from catalog."""
    id: str
    name: str
    surface: str
    date: str
    level: str
    year: int


class TournamentsResponse(BaseModel):
    """Response for GET /tournaments."""
    tournaments: list[TournamentInfo]
    count: int


class TournamentRequest(BaseModel):
    """Request for tournament simulation."""
    tournament_id: Optional[str] = Field(None, description="Real tournament ID from catalog, or null for custom")
    players: list[str] = Field(..., min_length=8, max_length=16, description="List of player names")
    size: int = Field(..., description="Tournament size: 8 or 16")
    surface: str = Field(..., description="Surface: Hard, Clay, or Grass")
    as_of: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    model: str = Field(DEFAULT_MODEL_ID, description="Model for match predictions")
    best_of: int = Field(3, description="Best of 3 or 5 sets per match")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    timeline_mode: Literal["none", "games"] = Field("none", description="Timeline detail level (points not supported for tournaments)")
    seeding: Literal["elo", "random"] = Field("random", description="Seeding method")

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v not in {8, 16}:
            raise ValueError("size must be 8 or 16")
        return v

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str) -> str:
        v = v.strip().title()
        if v not in {"Hard", "Clay", "Grass"}:
            raise ValueError("Surface must be Hard, Clay, or Grass")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return normalize_model_id(v, scope="tournament")

    @field_validator("best_of")
    @classmethod
    def validate_best_of(cls, v: int) -> int:
        if v not in {3, 5}:
            raise ValueError("best_of must be 3 or 5")
        return v


class TournamentMatchParams(BaseModel):
    """Point probability params for tournament match."""
    p_point_on_serve_a: float
    p_point_on_serve_b: float


class TournamentMatchResult(BaseModel):
    """Result of a single tournament match."""
    winner: Literal["A", "B"]
    winner_name: str
    sets: list[str]
    sets_a: int
    sets_b: int


class TournamentMatch(BaseModel):
    """A match within a tournament round."""
    player_a: str
    player_b: str
    p_a: float
    p_b: float
    params: TournamentMatchParams
    result: TournamentMatchResult
    timeline: Optional[list[Any]] = None


class TournamentRound(BaseModel):
    """A round in the tournament."""
    round: int
    name: str
    matches: list[TournamentMatch]


class TournamentMeta(BaseModel):
    """Tournament metadata (real or custom)."""
    id: Optional[str]
    name: str
    surface: str
    date: str
    level: str
    year: Optional[int]


class PlayerStanding(BaseModel):
    """Player stats in tournament."""
    wins: int
    losses: int


class TournamentResponse(BaseModel):
    """Response for POST /tournament/simulate."""
    tournament: TournamentMeta
    surface: str
    model: str
    as_of_used: str
    seed_used: int
    seeding: str
    size: int
    best_of: int
    warnings: list[str] = Field(default_factory=list)
    bracket_order: list[str]
    rounds: list[TournamentRound]
    champion: str
    standings: dict[str, PlayerStanding]


# ============== IN-PLAY / LIVE TRACKER SCHEMAS ==============

class InPlayGameEvent(BaseModel):
    server: Literal["A", "B"]
    game_winner: Literal["A", "B"]
    server_points_won: int
    server_points_lost: int
    is_tiebreak: bool
    sets_a: int
    sets_b: int
    games_a: int
    games_b: int
    p_live_a: float
    p_live_ci_low: float
    p_live_ci_high: float


class InPlayStateResponse(BaseModel):
    match_id: str
    player_a: str
    player_b: str
    surface: str
    model: str
    as_of_used: str
    best_of: int
    current_server: Literal["A", "B"]
    sets_a: int
    sets_b: int
    games_a: int
    games_b: int
    status: Literal["in_progress", "finished"]
    winner: Optional[Literal["A", "B"]] = None
    p_prior_a: float
    p_prior_b: float
    p_live_a: float
    p_live_ci_low: float
    p_live_ci_high: float
    uncertainty: float
    n_observations: int
    warnings: list[str] = Field(default_factory=list)
    events: list[InPlayGameEvent] = Field(default_factory=list)


class InPlayDeleteResponse(BaseModel):
    match_id: str
    deleted: bool


# ============== MONTE CARLO SCHEMAS ==============

class TournamentMonteCarloRequest(TournamentRequest):
    """Request for Monte Carlo tournament simulation."""
    n_simulations: int = Field(200, ge=1, le=1000, description="Number of simulations to run")


class TournamentMonteCarloOdd(BaseModel):
    """Aggregated odds for one player across Monte Carlo simulations."""
    player: str
    wins: int
    win_pct: float
    final_pct: float
    semifinal_pct: float
    round_reached_counts: dict[str, int]
    round_appearance_counts: dict[str, int]


class TournamentMonteCarloResponse(BaseModel):
    """Response for POST /tournament/monte_carlo."""
    n_simulations: int
    seed_start: int
    tournament: TournamentMeta
    surface: str
    model: str
    as_of_used: str
    seeding: str
    size: int
    best_of: int
    odds: list[TournamentMonteCarloOdd]
    warnings: list[str] = Field(default_factory=list)


# ============== SCOUTING / RIVAL ANALYSIS SCHEMAS ==============

class TacticalInsight(BaseModel):
    """A single tactical observation or recommendation."""
    type: Literal["strength", "weakness", "neutral"]
    category: Literal["serve", "return", "mental", "surface", "consistency"]
    title: str
    description: str
    metric_value: Optional[float] = None
    metric_label: Optional[str] = None
    severity: Literal["high", "medium", "low"] = "medium"


class ScoutingCompareStats(BaseModel):
    """Serve/return statistics for one player in the scouting context."""
    player: str
    surface: str
    first_serve_pct: Optional[float] = None
    ace_rate: Optional[float] = None
    double_fault_rate: Optional[float] = None
    bp_saved_pct: Optional[float] = None
    return_points_won_pct: Optional[float] = None
    matches_counted: int
    elo_global: Optional[float] = None
    elo_surface: Optional[float] = None
    win_rate: Optional[float] = None
    win_rate_surface: Optional[float] = None


class ScoutingReportResponse(BaseModel):
    """Full scouting report comparing two players on a given surface."""
    player_a: str
    player_b: str
    surface: str
    stats_a: ScoutingCompareStats
    stats_b: ScoutingCompareStats
    # Insights about player_b (the rival to scout)
    rival_weaknesses: list[TacticalInsight]
    rival_strengths: list[TacticalInsight]
    # Strategic recommendations for player_a
    recommendations: list[TacticalInsight]
    overall_advantage: Literal["A", "B", "even"]
    advantage_summary: str


# ============== PLAYER PROFILE / HISTORY SCHEMAS ==============

class PlayerHistoryMatch(BaseModel):
    date: str
    tournament: str
    surface: str
    opponent: str
    result: Literal["W", "L"]
    score: str


class PlayerEloPoint(BaseModel):
    date: str
    elo_global: Optional[float] = None
    elo_surface: Optional[float] = None
    surface: str


class PlayerHistoryResponse(BaseModel):
    player: str
    matches: list[PlayerHistoryMatch]
    elo_evolution: list[PlayerEloPoint]


class PlayerServeStatsResponse(BaseModel):
    player: str
    surface: str
    first_serve_pct: Optional[float] = None
    ace_rate: Optional[float] = None
    double_fault_rate: Optional[float] = None
    bp_saved_pct: Optional[float] = None
    return_points_won_pct: Optional[float] = None
    matches_counted: int


class RecordWinsLosses(BaseModel):
    wins: int
    losses: int


class CurrentStreak(BaseModel):
    type: Literal["W", "L"]
    count: int


class PlayerProfileResponse(BaseModel):
    name: str
    age: Optional[float] = None
    nationality: Optional[str] = None
    elo_global: Optional[float] = None
    elo_by_surface: dict[str, Optional[float]]
    record: RecordWinsLosses
    record_by_surface: dict[str, RecordWinsLosses]
    current_streak: CurrentStreak
    last_match_date: Optional[str] = None


