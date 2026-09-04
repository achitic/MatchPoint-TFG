// frontend/src/api/client.ts
const API_BASE: string = (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000';

export interface PredictRequest {
    player_a: string;
    player_b: string;
    surface: string;
    as_of: string | null;
    model: string;
    debug: boolean;
}

export interface FeatureDiff {
    feature: string;
    a: number;
    b: number;
    diff: number;
}

export interface DebugInfo {
    features_a: Record<string, number>;
    features_b: Record<string, number>;
    top_diffs: FeatureDiff[];
}

export interface ExplainContributor {
    feature: string;
    value: number;
    coef: number;
    contribution: number;
    favors: 'A' | 'B';
}

export interface ExplainInfo {
    method: string;
    top_contributors: ExplainContributor[];
}

export interface PredictResponse {
    player_a: string;
    player_b: string;
    surface: string;
    model: string;
    as_of_used: string;
    p_a: number;
    p_b: number;
    warnings: string[];
    debug: DebugInfo | null;
    explain: ExplainInfo | null;
}

export interface PlayersResponse {
    players: string[];
    count: number;
}

// ============== MODEL CATALOG ==============

export interface ModelInfo {
    id: string;
    label_es: string;
    description_es: string;
}

export interface ModelsResponse {
    models: ModelInfo[];
}

// Default models fallback (in case API fails)
export const DEFAULT_MODELS: ModelInfo[] = [
    { id: 'calibrated_logreg', label_es: 'Modelo probabilístico calibrado · Recomendado', description_es: 'Regresión logística con calibración isotónica para probabilidades fiables.' },
    { id: 'surface_logreg', label_es: 'Modelo especializado por superficie', description_es: 'Combina ELO global, específico por superficie y blended.' },
    { id: 'baseline_logreg', label_es: 'Modelo base ELO', description_es: 'Referencia interpretable basada únicamente en el ELO global.' },
    { id: 'stacking_ensemble', label_es: 'Ensemble avanzado', description_es: 'Combina varios algoritmos predictivos; ofrece menor interpretabilidad.' },
];

// ============== SIMULATION TYPES ==============

export interface SimulateRequest {
    player_a: string;
    player_b: string;
    surface: string;
    as_of: string | null;
    model: string;
    best_of: 3 | 5;
    seed: number | null;
    first_server: 'A' | 'B' | 'random';
    timeline_mode: 'none' | 'games' | 'points';
    engine_mode?: 'proxy_v0' | 'bayes_live_v1';
    debug?: boolean;
    p_a_override?: number | null;
}

export interface SimulationParams {
    proxy_method: string;
    surface_base: number;
    delta_max: number;
    strength_a: number;
    p_point_on_serve_a: number;
    p_point_on_serve_b: number;
}

export interface SimulateResult {
    winner: 'A' | 'B';
    sets: string[];
    sets_a: number;
    sets_b: number;
}

export interface SimulationPointEvent {
    point: number;
    winner: 'A' | 'B' | string;
    score: string;
    server?: 'A' | 'B';
    pressure?: number;
    fatigue_factor?: number;
    p_server_eff?: number;
    p_live_a?: number;
    p_live_ci_low?: number;
    p_live_ci_high?: number;
    p_server_bayes_before?: number;
    p_server_bayes_after?: number;
    p_server_bayes_delta?: number;
    trace_factors?: string[];
}

export interface GameEvent {
    game: number;
    type: 'game' | 'tiebreak';
    server: 'A' | 'B';
    winner: 'A' | 'B';
    score: string;
    p_live_a?: number;
    p_live_ci_low?: number;
    p_live_ci_high?: number;
    fatigue_factor?: number;
    points?: SimulationPointEvent[] | null;
}

export interface SetEvent {
    set: number;
    score: string;
    winner: 'A' | 'B';
    tiebreak: boolean;
    games: GameEvent[] | null;
}

export interface SimulateResponse {
    player_a: string;
    player_b: string;
    surface: string;
    model: string;
    as_of_used: string;
    p_a: number;
    p_b: number;
    seed_used: number;
    warnings: string[];
    params: SimulationParams;
    result: SimulateResult;
    timeline: SetEvent[] | null;
    debug: unknown | null;
}

// ============== TOURNAMENT TYPES ==============

export interface TournamentInfo {
    id: string;
    name: string;
    surface: string;
    date: string;
    level: string;
    year: number;
}

export interface TournamentsResponse {
    tournaments: TournamentInfo[];
    count: number;
}

export interface TournamentRequest {
    tournament_id: string | null;
    players: string[];
    size: 8 | 16;
    surface: string;
    as_of: string | null;
    model: string;
    best_of: 3 | 5;
    seed: number | null;
    timeline_mode: 'none' | 'games';
    seeding: 'elo' | 'random';
}

export interface TournamentMatchParams {
    p_point_on_serve_a: number;
    p_point_on_serve_b: number;
}

export interface TournamentMatchResult {
    winner: 'A' | 'B';
    winner_name: string;
    sets: string[];
    sets_a: number;
    sets_b: number;
}

export interface TournamentMatch {
    player_a: string;
    player_b: string;
    p_a: number;
    p_b: number;
    params: TournamentMatchParams;
    result: TournamentMatchResult;
    timeline?: SetEvent[] | null;
}

export interface TournamentRound {
    round: number;
    name: string;
    matches: TournamentMatch[];
}

export interface TournamentMeta {
    id: string | null;
    name: string;
    surface: string;
    date: string;
    level: string;
    year: number | null;
}

export interface PlayerStanding {
    wins: number;
    losses: number;
}

export interface TournamentResponse {
    tournament: TournamentMeta;
    surface: string;
    model: string;
    as_of_used: string;
    seed_used: number;
    seeding: string;
    size: number;
    best_of: number;
    warnings: string[];
    bracket_order: string[];
    rounds: TournamentRound[];
    champion: string;
    standings: Record<string, PlayerStanding>;
}

// ============== API FUNCTIONS ==============

export async function fetchPlayers(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/players`);
    if (!response.ok) {
        throw new Error('Error al cargar jugadores');
    }
    const data: PlayersResponse = await response.json();
    return data.players;
}

export async function fetchModels(): Promise<ModelInfo[]> {
    try {
        const response = await fetch(`${API_BASE}/models`);
        if (!response.ok) {
            console.warn('Error al cargar modelos, usando fallback');
            return DEFAULT_MODELS;
        }
        const data: ModelsResponse = await response.json();
        return data.models;
    } catch (error) {
        console.warn('Error al cargar modelos, usando fallback:', error);
        return DEFAULT_MODELS;
    }
}

export async function fetchSurfaces(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/surfaces`);
    if (!response.ok) {
        throw new Error('Error al cargar superficies');
    }
    const data = await response.json();
    return data.surfaces;
}

export async function predict(request: PredictRequest): Promise<PredictResponse> {
    const response = await fetch(`${API_BASE}/predict`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Error en la predicción');
    }

    return response.json();
}

export async function healthCheck(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE}/health`);
        return response.ok;
    } catch {
        return false;
    }
}

export async function simulateMatch(request: SimulateRequest): Promise<SimulateResponse> {
    const response = await fetch(`${API_BASE}/simulate_match`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        let errorMessage = 'Error en la simulación';
        try {
            const error = await response.json();
            errorMessage = error.detail || errorMessage;
        } catch {
            errorMessage = `Error en la simulación: ${response.statusText}`;
        }
        throw new Error(errorMessage);
    }

    return response.json();
}

// ============== TOURNAMENT API FUNCTIONS ==============

export interface TournamentsParams {
    year?: number;
    surface?: string;
    level?: string;
    limit?: number;
}

export async function fetchTournaments(params: TournamentsParams = {}): Promise<TournamentInfo[]> {
    const searchParams = new URLSearchParams();
    if (params.year) searchParams.set('year', params.year.toString());
    if (params.surface) searchParams.set('surface', params.surface);
    if (params.level) searchParams.set('level', params.level);
    if (params.limit) searchParams.set('limit', params.limit.toString());

    const url = `${API_BASE}/tournaments${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error('Error al cargar torneos');
    }

    const data: TournamentsResponse = await response.json();
    return data.tournaments;
}

export async function simulateTournament(request: TournamentRequest): Promise<TournamentResponse> {
    const response = await fetch(`${API_BASE}/tournament/simulate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        let errorMessage = 'Error en la simulación del torneo';
        try {
            const error = await response.json();
            errorMessage = error.detail || errorMessage;
        } catch {
            errorMessage = `Error en la simulación del torneo: ${response.statusText}`;
        }
        throw new Error(errorMessage);
    }

    return response.json();
}
// ============== H2H TYPES ==============

export interface H2HMatch {
    date: string;
    tournament: string;
    surface: string;
    winner: string;
    score: string;
}

export interface H2HSurfaceStats {
    wins_a: number;
    wins_b: number;
    total: number;
}

export interface H2HStats {
    total: number;
    wins_a: number;
    wins_b: number;
    by_surface: Record<string, H2HSurfaceStats>;
}

export interface H2HResponse {
    player_a: string;
    player_b: string;
    stats: H2HStats;
    matches: H2HMatch[];
}

// ============== H2H API ==============

export async function fetchH2H(playerA: string, playerB: string, limit = 20): Promise<H2HResponse> {
    const params = new URLSearchParams({
        player_a: playerA,
        player_b: playerB,
        limit: String(limit),
    });
    const response = await fetch(`${API_BASE}/h2h?${params.toString()}`);
    if (!response.ok) {
        let detail = 'Error al cargar historial H2H';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}


// ============== SCOUTING / RIVAL ANALYSIS TYPES ==============

export type InsightType = 'strength' | 'weakness' | 'neutral';
export type InsightCategory = 'serve' | 'return' | 'mental' | 'surface' | 'consistency';
export type InsightSeverity = 'high' | 'medium' | 'low';

export interface TacticalInsight {
    type: InsightType;
    category: InsightCategory;
    title: string;
    description: string;
    metric_value: number | null;
    metric_label: string | null;
    severity: InsightSeverity;
}

export interface ScoutingCompareStats {
    player: string;
    surface: string;
    first_serve_pct: number | null;
    ace_rate: number | null;
    double_fault_rate: number | null;
    bp_saved_pct: number | null;
    return_points_won_pct: number | null;
    matches_counted: number;
    elo_global: number | null;
    elo_surface: number | null;
    win_rate: number | null;
    win_rate_surface: number | null;
}

export interface ScoutingReportResponse {
    player_a: string;
    player_b: string;
    surface: string;
    stats_a: ScoutingCompareStats;
    stats_b: ScoutingCompareStats;
    rival_weaknesses: TacticalInsight[];
    rival_strengths: TacticalInsight[];
    recommendations: TacticalInsight[];
    overall_advantage: 'A' | 'B' | 'even';
    advantage_summary: string;
}

// ============== SCOUTING API ==============

export async function fetchScoutingReport(
    playerA: string,
    playerB: string,
    surface: string,
): Promise<ScoutingReportResponse> {
    const params = new URLSearchParams({
        player_a: playerA,
        player_b: playerB,
        surface,
    });
    const response = await fetch(`${API_BASE}/scouting?${params.toString()}`);
    if (!response.ok) {
        let detail = 'Error al generar informe de scouting';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

// ============== IN-PLAY / LIVE TRACKER TYPES ==============

export interface InPlayInitRequest {
    player_a: string;
    player_b: string;
    surface: string;
    as_of: string | null;
    model: string;
    best_of: 3 | 5;
    first_server: 'A' | 'B' | 'random';
}

export interface InPlayUpdateRequest {
    match_id: string;
    server: 'A' | 'B';
    game_winner: 'A' | 'B';
    server_points_won: number;
    server_points_lost: number;
    is_tiebreak?: boolean;
}

export interface InPlayGameEvent {
    server: 'A' | 'B';
    game_winner: 'A' | 'B';
    server_points_won: number;
    server_points_lost: number;
    is_tiebreak: boolean;
    sets_a: number;
    sets_b: number;
    games_a: number;
    games_b: number;
    p_live_a: number;
    p_live_ci_low: number;
    p_live_ci_high: number;
}

export interface InPlayStateResponse {
    match_id: string;
    player_a: string;
    player_b: string;
    surface: string;
    model: string;
    as_of_used: string;
    best_of: number;
    current_server: 'A' | 'B';
    sets_a: number;
    sets_b: number;
    games_a: number;
    games_b: number;
    status: 'in_progress' | 'finished';
    winner: 'A' | 'B' | null;
    p_prior_a: number;
    p_prior_b: number;
    p_live_a: number;
    p_live_ci_low: number;
    p_live_ci_high: number;
    uncertainty: number;
    n_observations: number;
    warnings: string[];
    events: InPlayGameEvent[];
}

export interface InPlayDeleteResponse {
    match_id: string;
    deleted: boolean;
}

// ============== IN-PLAY API ==============

export async function inplayInit(request: InPlayInitRequest): Promise<InPlayStateResponse> {
    const response = await fetch(`${API_BASE}/inplay/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    if (!response.ok) {
        let detail = 'Error al iniciar tracker en vivo';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

export async function inplayUpdate(request: InPlayUpdateRequest): Promise<InPlayStateResponse> {
    const response = await fetch(`${API_BASE}/inplay/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    if (!response.ok) {
        let detail = 'Error al registrar juego en vivo';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

export async function getInplayState(matchId: string): Promise<InPlayStateResponse> {
    const response = await fetch(`${API_BASE}/inplay/state/${encodeURIComponent(matchId)}`);
    if (!response.ok) {
        let detail = 'Error al cargar estado del tracker en vivo';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

export async function deleteInplayState(matchId: string): Promise<InPlayDeleteResponse> {
    const response = await fetch(`${API_BASE}/inplay/${encodeURIComponent(matchId)}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        let detail = 'Error al eliminar la sesión del tracker en vivo';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

// ============== MONTE CARLO TOURNAMENT TYPES ==============

export interface TournamentMonteCarloOdd {
    player: string;
    wins: number;
    win_pct: number;
    final_pct: number;
    semifinal_pct: number;
    round_reached_counts: Record<string, number>;
    round_appearance_counts: Record<string, number>;
}

export interface TournamentMonteCarloResponse {
    n_simulations: number;
    seed_start: number;
    tournament: TournamentMeta;
    surface: string;
    model: string;
    as_of_used: string;
    seeding: string;
    size: number;
    best_of: number;
    odds: TournamentMonteCarloOdd[];
    warnings: string[];
}

export async function simulateTournamentMonteCarlo(
    baseRequest: TournamentRequest,
    nSimulations: number
): Promise<TournamentMonteCarloResponse> {
    const payload = {
        ...baseRequest,
        n_simulations: nSimulations
    };
    const response = await fetch(`${API_BASE}/tournament/simulate_mc`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        let errorMessage = 'Error en la simulación Monte Carlo';
        try {
            const error = await response.json();
            errorMessage = error.detail || errorMessage;
        } catch {
            errorMessage = `Error en la simulación Monte Carlo: ${response.statusText}`;
        }
        throw new Error(errorMessage);
    }

    return response.json();
}

// ============== PLAYER PROFILE TYPES ==============

export interface RecordWinsLosses {
    wins: number;
    losses: number;
}

export interface CurrentStreak {
    type: 'W' | 'L';
    count: number;
}

export interface PlayerProfileResponse {
    name: string;
    age: number | null;
    nationality: string | null;
    elo_global: number | null;
    elo_by_surface: Record<string, number | null>;
    record: RecordWinsLosses;
    record_by_surface: Record<string, RecordWinsLosses>;
    current_streak: CurrentStreak;
    last_match_date: string | null;
}

export interface PlayerHistoryMatch {
    date: string;
    tournament: string;
    surface: string;
    opponent: string;
    result: 'W' | 'L';
    score: string;
}

export interface PlayerEloPoint {
    date: string;
    elo_global: number | null;
    elo_surface: number | null;
    surface: string;
}

export interface PlayerHistoryResponse {
    player: string;
    matches: PlayerHistoryMatch[];
    elo_evolution: PlayerEloPoint[];
}

export interface PlayerServeStatsResponse {
    player: string;
    surface: string;
    first_serve_pct: number | null;
    ace_rate: number | null;
    double_fault_rate: number | null;
    bp_saved_pct: number | null;
    return_points_won_pct: number | null;
    matches_counted: number;
}

// ============== PLAYER PROFILE API ==============

export async function fetchPlayerProfile(name: string): Promise<PlayerProfileResponse> {
    const response = await fetch(`${API_BASE}/player/${encodeURIComponent(name)}/profile`);
    if (!response.ok) {
        let detail = 'Error al cargar perfil de jugador';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

export async function fetchPlayerHistory(name: string, limit = 20): Promise<PlayerHistoryResponse> {
    const response = await fetch(`${API_BASE}/player/${encodeURIComponent(name)}/history?limit=${limit}`);
    if (!response.ok) {
        let detail = 'Error al cargar historial del jugador';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}

export async function fetchPlayerServeStats(name: string, surface?: string): Promise<PlayerServeStatsResponse> {
    const url = surface
        ? `${API_BASE}/player/${encodeURIComponent(name)}/serve_stats?surface=${encodeURIComponent(surface)}`
        : `${API_BASE}/player/${encodeURIComponent(name)}/serve_stats`;
    const response = await fetch(url);
    if (!response.ok) {
        let detail = 'Error al cargar estadísticas de saque del jugador';
        try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
    }
    return response.json();
}
