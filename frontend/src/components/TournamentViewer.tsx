// frontend/src/components/TournamentViewer.tsx
import { useEffect, useState } from 'react';
import { AlertTriangle, BarChart3, Download, GitBranch, List, RefreshCw, Trophy } from 'lucide-react';
import {
    simulateTournamentMonteCarlo,
    type TournamentMonteCarloResponse,
    type TournamentRequest,
    type TournamentResponse,
    type TournamentRound,
    type TournamentMatch,
} from '../api/client';
import { TournamentBracket } from './TournamentBracket';
import { useToast } from './toastContext';

interface TournamentViewerProps {
    result: TournamentResponse;
    baseRequest?: TournamentRequest | null;
    onRerunSameSeed?: () => void;
}

type ViewMode = 'bracket' | 'list';

export function TournamentViewer({ result, baseRequest, onRerunSameSeed }: TournamentViewerProps) {
    const toast = useToast();
    const [viewMode, setViewMode] = useState<ViewMode>('bracket');
    const [mcResult, setMcResult] = useState<TournamentMonteCarloResponse | null>(null);
    const [mcLoading, setMcLoading] = useState(false);
    const [nSimulations, setNSimulations] = useState(200);

    useEffect(() => {
        const mediaQuery = window.matchMedia('(max-width: 640px)');
        const syncMobileView = () => {
            if (mediaQuery.matches) {
                setViewMode('list');
            }
        };

        syncMobileView();
        mediaQuery.addEventListener('change', syncMobileView);
        return () => mediaQuery.removeEventListener('change', syncMobileView);
    }, []);

    const handleExportJSON = () => {
        const data = {
            torneo: result.tournament.name,
            superficie: result.surface,
            modelo: result.model,
            semilla: result.seed_used,
            campeón: result.champion,
            rondas: result.rounds.map(r => ({
                nombre: r.name,
                partidos: r.matches.map(m => ({
                    playerA: m.player_a,
                    playerB: m.player_b,
                    pA: m.p_a,
                    pB: m.p_b,
                    ganador: m.result.winner_name,
                    resultado: m.result.sets.join(' '),
                })),
            })),
            clasificacion: result.standings,
        };
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `torneo_${result.tournament.name.replace(/\s/g, '_')}_semilla${result.seed_used}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Torneo exportado como JSON');
    };

    const handleMonteCarlo = async () => {
        if (!baseRequest) {
            toast.error('No hay datos base para repetir el torneo');
            return;
        }

        setMcLoading(true);
        try {
            const resultMc = await simulateTournamentMonteCarlo(baseRequest, nSimulations);
            setMcResult(resultMc);
            toast.success(`Monte Carlo completado: ${resultMc.n_simulations} simulaciones`);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Error al calcular Monte Carlo');
        } finally {
            setMcLoading(false);
        }
    };

    return (
        <div className="tournament-viewer">
            {/* Header */}
            <div className="tournament-header">
                <h2 className="section-heading"><Trophy size={22} aria-hidden="true" /> {result.tournament.name}</h2>
                <div className="tournament-meta">
                    <span className="meta-item">
                        <strong>Superficie:</strong> {result.surface}
                    </span>
                    <span className="meta-item">
                        <strong>Modelo:</strong> {result.model}
                    </span>
                    <span className="meta-item">
                        <strong>Fecha datos:</strong> {result.as_of_used}
                    </span>
                    <span className="meta-item">
                        <strong>Semilla:</strong> {result.seed_used}
                    </span>
                    <span className="meta-item">
                        <strong>Orden:</strong> {result.seeding === 'elo' ? 'Por ELO' : 'Aleatorio'}
                    </span>
                </div>
            </div>

            {/* Champion Banner */}
            <div className="champion-banner">
                <div className="champion-icon" aria-hidden="true"><Trophy size={26} /></div>
                <div className="champion-info">
                    <span className="champion-label">Campeón</span>
                    <span className="champion-name">{result.champion}</span>
                </div>
            </div>

            <div className="monte-carlo-panel">
                <div className="monte-carlo-header">
                    <div>
                        <span className="monte-carlo-kicker">Análisis estocástico</span>
                        <h3>Championship Odds</h3>
                    </div>
                    <div className="monte-carlo-controls">
                        <label>
                            Simulaciones
                            <select
                                value={nSimulations}
                                onChange={(event) => setNSimulations(Number(event.target.value))}
                                disabled={mcLoading}
                            >
                                <option value={100}>100</option>
                                <option value={200}>200</option>
                                <option value={500}>500</option>
                            </select>
                        </label>
                        <button
                            className="monte-carlo-btn"
                            onClick={handleMonteCarlo}
                            disabled={mcLoading || !baseRequest}
                        >
                            {mcLoading ? 'Calculando...' : 'Calcular probabilidades'}
                        </button>
                    </div>
                </div>

                {mcResult && (
                    <div className="monte-carlo-results">
                        <div className="monte-carlo-summary">
                            <span>{mcResult.n_simulations} simulaciones</span>
                            <span>Seed inicial: {mcResult.seed_start}</span>
                            <span>{mcResult.seeding === 'elo' ? 'Orden ELO' : 'Orden aleatorio'}</span>
                        </div>

                        {mcResult.warnings.length > 0 && (
                            <div className="monte-carlo-warnings">
                                {mcResult.warnings.slice(0, 3).map((warning) => (
                                    <span key={warning}>{warning}</span>
                                ))}
                            </div>
                        )}

                        <div className="monte-carlo-table-wrap">
                            <table className="monte-carlo-table">
                                <thead>
                                    <tr>
                                        <th>Jugador</th>
                                        <th>Campeón</th>
                                        <th>Final</th>
                                        <th>Semis</th>
                                        <th>Wins</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {mcResult.odds.map((odd) => (
                                        <tr key={odd.player} className={odd.player === result.champion ? 'current-champion-row' : ''}>
                                            <td>{odd.player}</td>
                                            <td>
                                                <div className="mc-odds-cell">
                                                    <span>{odd.win_pct.toFixed(1)}%</span>
                                                    <div className="mc-odds-bar">
                                                        <div style={{ width: `${odd.win_pct}%` }} />
                                                    </div>
                                                </div>
                                            </td>
                                            <td>{odd.final_pct.toFixed(1)}%</td>
                                            <td>{odd.semifinal_pct.toFixed(1)}%</td>
                                            <td>{odd.wins}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>

            {/* Warnings */}
            {result.warnings.length > 0 && (
                <div className="tournament-warnings">
                    <h4 className="section-heading"><AlertTriangle size={17} aria-hidden="true" /> Avisos</h4>
                    <ul>
                        {result.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* View mode toggle */}
            <div className="tournament-view-toggle">
                <button
                    className={`view-toggle-btn ${viewMode === 'bracket' ? 'active' : ''}`}
                    onClick={() => setViewMode('bracket')}
                    aria-pressed={viewMode === 'bracket'}
                >
                    <GitBranch size={16} aria-hidden="true" /> Cuadro
                </button>
                <button
                    className={`view-toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
                    onClick={() => setViewMode('list')}
                    aria-pressed={viewMode === 'list'}
                >
                    <List size={16} aria-hidden="true" /> Lista
                </button>
            </div>

            {/* Visual Bracket */}
            {viewMode === 'bracket' && (
                <div className="tournament-bracket-section">
                    <TournamentBracket result={result} />
                </div>
            )}

            {/* List view — original round cards */}
            {viewMode === 'list' && (
                <div className="tournament-rounds">
                    <h3 className="section-heading"><List size={18} aria-hidden="true" /> Cuadro del torneo</h3>
                    {result.rounds.map((round) => (
                        <RoundCard key={round.round} round={round} />
                    ))}
                </div>
            )}

            {/* Standings */}
            <div className="tournament-standings">
                <h3 className="section-heading"><BarChart3 size={18} aria-hidden="true" /> Clasificación</h3>
                <table className="standings-table">
                    <thead>
                        <tr>
                            <th>Jugador</th>
                            <th>Victorias</th>
                            <th>Derrotas</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Object.entries(result.standings)
                            .sort((a, b) => b[1].wins - a[1].wins)
                            .map(([player, stats]) => (
                                <tr key={player} className={player === result.champion ? 'champion-row' : ''}>
                                    <td>{player === result.champion ? <Trophy className="inline-champion-icon" size={14} aria-hidden="true" /> : null}{player}</td>
                                    <td className="wins-cell">{stats.wins}</td>
                                    <td className="losses-cell">{stats.losses}</td>
                                </tr>
                            ))}
                    </tbody>
                </table>
            </div>

            {/* Re-run and Export Buttons */}
            <div className="tournament-action-row">
                <button type="button" className="export-btn" onClick={handleExportJSON} title="Exportar torneo como JSON">
                    <Download size={16} aria-hidden="true" /> Exportar JSON
                </button>
                {onRerunSameSeed && (
                    <button
                        className="rerun-seed-btn"
                        onClick={onRerunSameSeed}
                        title="Repetir simulación con la misma semilla para verificar reproducibilidad"
                        type="button"
                    >
                        <RefreshCw size={16} aria-hidden="true" /> Repetir con la misma semilla
                    </button>
                )}
            </div>
        </div>
    );
}

// Round Card Component
function RoundCard({ round }: { round: TournamentRound }) {
    return (
        <div className="round-card">
            <h4 className="round-title">{round.name}</h4>
            <div className="round-matches">
                {round.matches.map((match, idx) => (
                    <MatchCard key={idx} match={match} />
                ))}
            </div>
        </div>
    );
}

// Match Card Component
function MatchCard({ match }: { match: TournamentMatch }) {
    const isPlayerAWinner = match.result.winner === 'A';
    const scoreStr = match.result.sets.join(' ');

    return (
        <div className="match-card">
            <div className={`match-player ${isPlayerAWinner ? 'winner' : ''}`}>
                <span className="player-name">{match.player_a}</span>
                <span className="player-prob">{(match.p_a * 100).toFixed(0)}%</span>
            </div>
            <div className="match-score">{scoreStr}</div>
            <div className={`match-player ${!isPlayerAWinner ? 'winner' : ''}`}>
                <span className="player-name">{match.player_b}</span>
                <span className="player-prob">{(match.p_b * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}
