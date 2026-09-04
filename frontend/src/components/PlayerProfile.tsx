import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Activity, ArrowLeft, Calendar, Gauge, TrendingUp, Trophy } from 'lucide-react';
import { motion } from 'framer-motion';
import {
    fetchPlayerHistory,
    fetchPlayerProfile,
    fetchPlayerServeStats,
    type PlayerHistoryResponse,
    type PlayerProfileResponse,
    type PlayerServeStatsResponse,
} from '../api/client';

type SurfaceFilter = 'all' | 'Hard' | 'Clay' | 'Grass';

const surfaces: SurfaceFilter[] = ['all', 'Hard', 'Clay', 'Grass'];

function formatPct(value: number | null | undefined, decimals = 1) {
    if (value === null || value === undefined) return 'N/D';
    return `${(value * 100).toFixed(decimals)}%`;
}

function formatElo(value: number | null | undefined) {
    if (value === null || value === undefined) return 'N/D';
    return Math.round(value).toString();
}

function buildLinePath(points: Array<{ elo_global: number | null }>, width = 620, height = 180) {
    const values = points
        .map((point) => point.elo_global)
        .filter((value): value is number => value !== null && value !== undefined);

    if (values.length < 2) {
        return { path: '', min: 0, max: 0 };
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(max - min, 1);
    const validPoints = points.filter((point) => point.elo_global !== null && point.elo_global !== undefined);
    const step = width / Math.max(validPoints.length - 1, 1);
    const path = validPoints
        .map((point, index) => {
            const x = index * step;
            const y = height - (((point.elo_global as number) - min) / span) * height;
            return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(' ');

    return { path, min, max };
}

function StatTile({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof Trophy;
    label: string;
    value: string;
    detail?: string;
}) {
    return (
        <div className="profile-stat-tile">
            <Icon size={18} strokeWidth={2} />
            <span>{label}</span>
            <strong>{value}</strong>
            {detail && <small>{detail}</small>}
        </div>
    );
}

function SurfaceBar({ surface, wins, losses }: { surface: string; wins: number; losses: number }) {
    const total = wins + losses;
    const pct = total > 0 ? wins / total : 0;

    return (
        <div className="surface-winrate-row">
            <div className="surface-winrate-label">
                <span>{surface}</span>
                <strong>{total > 0 ? `${(pct * 100).toFixed(1)}%` : 'N/D'}</strong>
            </div>
            <div className="surface-winrate-track">
                <motion.div
                    className="surface-winrate-fill"
                    initial={{ width: 0 }}
                    animate={{ width: `${pct * 100}%` }}
                    transition={{ duration: 0.55, ease: 'easeOut' }}
                />
            </div>
            <small>{wins}V / {losses}D</small>
        </div>
    );
}

function EloChart({ history }: { history: PlayerHistoryResponse }) {
    const recent = history.elo_evolution.slice(-80);
    const { path, min, max } = buildLinePath(recent);

    if (!path) {
        return <div className="profile-empty-panel">Sin puntos ELO suficientes.</div>;
    }

    return (
        <div className="elo-chart-wrap">
            <svg viewBox="0 0 620 180" className="elo-chart" role="img" aria-label="Evolucion ELO global">
                <line x1="0" y1="180" x2="620" y2="180" />
                <line x1="0" y1="0" x2="620" y2="0" />
                <motion.path
                    d={path}
                    fill="none"
                    initial={{ pathLength: 0, opacity: 0.4 }}
                    animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: 0.75, ease: 'easeOut' }}
                />
            </svg>
            <div className="elo-chart-scale">
                <span>{Math.round(min)}</span>
                <span>{Math.round(max)}</span>
            </div>
        </div>
    );
}

function ServeMetric({ label, value }: { label: string; value: number | null }) {
    const pct = value ?? 0;
    return (
        <div className="serve-metric">
            <div>
                <span>{label}</span>
                <strong>{formatPct(value)}</strong>
            </div>
            <div className="serve-metric-track">
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct * 100}%` }}
                    transition={{ duration: 0.5, ease: 'easeOut' }}
                />
            </div>
        </div>
    );
}

export function PlayerProfile() {
    const { playerName } = useParams();
    const decodedName = useMemo(() => decodeURIComponent(playerName || ''), [playerName]);

    const [profile, setProfile] = useState<PlayerProfileResponse | null>(null);
    const [history, setHistory] = useState<PlayerHistoryResponse | null>(null);
    const [serveStats, setServeStats] = useState<PlayerServeStatsResponse | null>(null);
    const [surfaceFilter, setSurfaceFilter] = useState<SurfaceFilter>('all');
    const [loading, setLoading] = useState(true);
    const [serveLoading, setServeLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function loadProfile() {
            if (!decodedName) return;
            setLoading(true);
            setError(null);
            try {
                const [nextProfile, nextHistory] = await Promise.all([
                    fetchPlayerProfile(decodedName),
                    fetchPlayerHistory(decodedName, 20),
                ]);
                if (!cancelled) {
                    setProfile(nextProfile);
                    setHistory(nextHistory);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err instanceof Error ? err.message : 'Error al cargar el perfil');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        loadProfile();
        return () => { cancelled = true; };
    }, [decodedName]);

    useEffect(() => {
        let cancelled = false;
        async function loadServeStats() {
            if (!decodedName) return;
            setServeLoading(true);
            try {
                const nextStats = await fetchPlayerServeStats(
                    decodedName,
                    surfaceFilter === 'all' ? undefined : surfaceFilter,
                );
                if (!cancelled) setServeStats(nextStats);
            } catch {
                if (!cancelled) setServeStats(null);
            } finally {
                if (!cancelled) setServeLoading(false);
            }
        }
        loadServeStats();
        return () => { cancelled = true; };
    }, [decodedName, surfaceFilter]);

    if (loading) {
        return <div className="profile-loading">Cargando perfil...</div>;
    }

    if (error || !profile || !history) {
        return (
            <div className="profile-error">
                <Link to="/app/predict" className="profile-back-link">
                    <ArrowLeft size={16} /> Volver
                </Link>
                <h2>No se pudo cargar el jugador</h2>
                <p>{error || 'Perfil no disponible.'}</p>
            </div>
        );
    }

    const totalMatches = profile.record.wins + profile.record.losses;
    const winrate = totalMatches > 0 ? profile.record.wins / totalMatches : 0;

    return (
        <motion.div
            className="player-profile"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
        >
            <Link to="/app/predict" className="profile-back-link">
                <ArrowLeft size={16} /> Volver a prediccion
            </Link>

            <section className="profile-hero">
                <div>
                    <span className="profile-kicker">Perfil de jugador</span>
                    <h2>{profile.name}</h2>
                    <div className="profile-meta-line">
                        {profile.nationality && <span>{profile.nationality}</span>}
                        {profile.age !== null && <span>{profile.age.toFixed(1)} anos</span>}
                        {profile.last_match_date && <span>Ultimo partido: {profile.last_match_date}</span>}
                    </div>
                </div>
                <div className="profile-elo-badge">
                    <span>ELO global</span>
                    <strong>{formatElo(profile.elo_global)}</strong>
                </div>
            </section>

            <section className="profile-stat-grid">
                <StatTile icon={Trophy} label="Victorias" value={profile.record.wins.toString()} detail={`${profile.record.losses} derrotas`} />
                <StatTile icon={Gauge} label="Winrate" value={`${(winrate * 100).toFixed(1)}%`} detail={`${totalMatches} partidos`} />
                <StatTile icon={TrendingUp} label="Racha" value={`${profile.current_streak.type}${profile.current_streak.count}`} detail="resultado reciente" />
                <StatTile icon={Calendar} label="Partidos recientes" value={history.matches.length.toString()} detail="en historial" />
            </section>

            <section className="profile-grid">
                <div className="profile-panel profile-panel-wide">
                    <div className="profile-panel-heading">
                        <h3>Evolucion ELO</h3>
                        <span>{history.elo_evolution.length} puntos</span>
                    </div>
                    <EloChart history={history} />
                </div>

                <div className="profile-panel">
                    <div className="profile-panel-heading">
                        <h3>Winrate por superficie</h3>
                    </div>
                    <div className="surface-winrate-list">
                        {Object.entries(profile.record_by_surface).map(([surface, record]) => (
                            <SurfaceBar key={surface} surface={surface} wins={record.wins} losses={record.losses} />
                        ))}
                    </div>
                </div>

                <div className="profile-panel">
                    <div className="profile-panel-heading">
                        <h3>Servicio y resto</h3>
                        {serveLoading && <span>Actualizando...</span>}
                    </div>
                    <div className="surface-filter-row">
                        {surfaces.map((surface) => (
                            <button
                                key={surface}
                                type="button"
                                className={surfaceFilter === surface ? 'active' : ''}
                                onClick={() => setSurfaceFilter(surface)}
                                aria-pressed={surfaceFilter === surface}
                            >
                                {surface === 'all' ? 'Todas' : surface}
                            </button>
                        ))}
                    </div>
                    {serveStats ? (
                        <div className="serve-metric-list">
                            <ServeMetric label="Primer servicio" value={serveStats.first_serve_pct} />
                            <ServeMetric label="Ace rate" value={serveStats.ace_rate} />
                            <ServeMetric label="Break points salvados" value={serveStats.bp_saved_pct} />
                            <ServeMetric label="Puntos al resto ganados" value={serveStats.return_points_won_pct} />
                            <small>{serveStats.matches_counted} partidos computados</small>
                        </div>
                    ) : (
                        <div className="profile-empty-panel">Stats no disponibles.</div>
                    )}
                </div>

                <div className="profile-panel profile-panel-wide">
                    <div className="profile-panel-heading">
                        <h3>Ultimos partidos</h3>
                    </div>
                    <div className="profile-table-wrap">
                        <table className="profile-match-table">
                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Torneo</th>
                                    <th>Sup.</th>
                                    <th>Rival</th>
                                    <th>Res.</th>
                                    <th>Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {history.matches.map((match) => (
                                    <tr key={`${match.date}-${match.opponent}-${match.score}`}>
                                        <td>{match.date}</td>
                                        <td>{match.tournament || 'N/D'}</td>
                                        <td>{match.surface}</td>
                                        <td>
                                            <Link to={`/app/player/${encodeURIComponent(match.opponent)}`}>
                                                {match.opponent}
                                            </Link>
                                        </td>
                                        <td>
                                            <span className={match.result === 'W' ? 'result-win' : 'result-loss'}>
                                                {match.result}
                                            </span>
                                        </td>
                                        <td>{match.score || 'N/D'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div className="profile-panel elo-surface-panel">
                    <div className="profile-panel-heading">
                        <h3>ELO superficie</h3>
                        <Activity size={16} />
                    </div>
                    <div className="elo-surface-list">
                        {Object.entries(profile.elo_by_surface).map(([surface, elo]) => (
                            <div key={surface}>
                                <span>{surface}</span>
                                <strong>{formatElo(elo)}</strong>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </motion.div>
    );
}
