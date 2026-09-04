import { useState, useEffect, useRef } from 'react';
import { Play, Activity, Loader2, AlertTriangle, RefreshCw, Plus, Trophy, Undo2 } from 'lucide-react';
import type { InPlayStateResponse, InPlayGameEvent, InPlayInitRequest } from '../api/client';
import { deleteInplayState, fetchPlayers, inplayInit, inplayUpdate, getInplayState } from '../api/client';
import { formatTennisScore, isCompletedGame } from './tennisScore';
import type { PointWinner } from './tennisScore';

function LiveProbabilityChart({ events, playerA, playerB, width = 500, height = 180 }: {
    events: InPlayGameEvent[];
    playerA: string;
    playerB: string;
    width?: number;
    height?: number;
}) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const rootStyles = getComputedStyle(document.documentElement);
        const sansFont = rootStyles.getPropertyValue('--font-sans').trim() || 'system-ui, sans-serif';
        const monoFont = rootStyles.getPropertyValue('--font-mono').trim() || 'Consolas, monospace';

        const dpr = window.devicePixelRatio || 1;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.scale(dpr, dpr);

        ctx.clearRect(0, 0, width, height);

        const paddingLeft = 32;
        const paddingRight = 16;
        const paddingTop = 16;
        const paddingBottom = 20;

        const chartWidth = width - paddingLeft - paddingRight;
        const chartHeight = height - paddingTop - paddingBottom;

        const gridLines = [0, 0.25, 0.50, 0.75, 1];
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;

        gridLines.forEach(lvl => {
            const y = paddingTop + chartHeight * (1 - lvl);
            ctx.beginPath();
            ctx.moveTo(paddingLeft, y);
            ctx.lineTo(width - paddingRight, y);
            ctx.stroke();

            ctx.fillStyle = '#64748b'; // text-dim
            ctx.font = `9px ${sansFont}`;
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${Math.round(lvl * 100)}%`, paddingLeft - 6, y);
        });

        const centerLineY = paddingTop + chartHeight * 0.50;
        ctx.strokeStyle = 'rgba(34, 211, 238, 0.25)'; // cyan muted
        ctx.lineWidth = 1.25;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, centerLineY);
        ctx.lineTo(width - paddingRight, centerLineY);
        ctx.stroke();
        ctx.setLineDash([]); // Reset line dash

        ctx.fillStyle = 'rgba(34, 211, 238, 0.4)';
        ctx.font = `8px ${sansFont}`;
        ctx.textAlign = 'left';
        ctx.fillText(`Favorece a ${playerA.split(' ').pop()}`, paddingLeft + 6, paddingTop + 10);

        ctx.fillStyle = 'rgba(139, 92, 246, 0.4)';
        ctx.textAlign = 'left';
        ctx.fillText(`Favorece a ${playerB.split(' ').pop()}`, paddingLeft + 6, paddingTop + chartHeight - 4);

        if (events.length === 0) {
            ctx.fillStyle = '#64748b';
            ctx.font = `11px ${sansFont}`;
            ctx.textAlign = 'center';
            ctx.fillText('Registra juegos para observar el gráfico de momentum', paddingLeft + chartWidth / 2, paddingTop + chartHeight / 2);
            return;
        }

        const firstEvent = events[0];
        const points = [
            { x: paddingLeft, y: paddingTop + chartHeight * (1 - firstEvent.p_live_a) } // start value approximation
        ];

        const totalPoints = events.length;
        const stepX = totalPoints > 1 ? chartWidth / (totalPoints) : chartWidth;

        events.forEach((ev, idx) => {
            const x = paddingLeft + (idx + 1) * stepX;
            const y = paddingTop + chartHeight * (1 - ev.p_live_a);
            points.push({ x, y });

            ctx.fillStyle = '#64748b';
            ctx.font = `8px ${monoFont}`;
            ctx.textAlign = 'center';
            ctx.fillText(`J${idx+1}`, x, paddingTop + chartHeight + 12);
        });

        ctx.fillStyle = 'rgba(34, 211, 238, 0.05)';
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        events.forEach((ev, idx) => {
            const x = paddingLeft + (idx + 1) * stepX;
            const y = paddingTop + chartHeight * (1 - ev.p_live_ci_high);
            ctx.lineTo(x, y);
        });
        for (let idx = events.length - 1; idx >= 0; idx--) {
            const ev = events[idx];
            const x = paddingLeft + (idx + 1) * stepX;
            const y = paddingTop + chartHeight * (1 - ev.p_live_ci_low);
            ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = '#22d3ee'; // primary cyan
        ctx.lineWidth = 2.5;
        ctx.shadowBlur = 8;
        ctx.shadowColor = 'rgba(34, 211, 238, 0.5)';
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        points.slice(1).forEach(pt => ctx.lineTo(pt.x, pt.y));
        ctx.stroke();

        ctx.shadowBlur = 0; // Reset shadow

        points.forEach((pt, idx) => {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, idx === points.length - 1 ? 4.5 : 3, 0, 2 * Math.PI);
            ctx.fillStyle = idx === points.length - 1 ? '#22d3ee' : '#030712';
            ctx.fill();
            ctx.strokeStyle = '#22d3ee';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        });

    }, [events, playerA, playerB, width, height]);

    return (
        <div className="live-chart-canvas-wrap">
            <canvas
                ref={canvasRef}
                role="img"
                aria-label={`Evolución de la probabilidad en vivo de ${playerA} frente a ${playerB}`}
            />
        </div>
    );
}

function InPlaySetup({
    players,
    onSubmit,
    loading,
}: {
    players: string[];
    onSubmit: (request: InPlayInitRequest) => void;
    loading: boolean;
}) {
    const [playerA, setPlayerA] = useState('');
    const [playerB, setPlayerB] = useState('');
    const [surface, setSurface] = useState('Hard');
    const [bestOf, setBestOf] = useState<3 | 5>(3);
    const [firstServer, setFirstServer] = useState<'A' | 'B' | 'random'>('random');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (playerA && playerB && playerA !== playerB) {
            onSubmit({
                player_a: playerA,
                player_b: playerB,
                surface,
                as_of: null,
                model: 'calibrated_logreg',
                best_of: bestOf,
                first_server: firstServer,
            });
        }
    };

    const [queryA, setQueryA] = useState('');
    const [queryB, setQueryB] = useState('');
    const [openA, setOpenA] = useState(false);
    const [openB, setOpenB] = useState(false);
    const [activeA, setActiveA] = useState(-1);
    const [activeB, setActiveB] = useState(-1);

    const filteredA = players.filter(p => p.toLowerCase().includes(queryA.toLowerCase().trim())).slice(0, 6);
    const filteredB = players.filter(p => p !== playerA && p.toLowerCase().includes(queryB.toLowerCase().trim())).slice(0, 6);
    const showA = openA && queryA.length >= 2 && filteredA.length > 0;
    const showB = openB && queryB.length >= 2 && filteredB.length > 0;
    const selectA = (player: string) => { setPlayerA(player); setQueryA(player); setOpenA(false); setActiveA(-1); };
    const selectB = (player: string) => { setPlayerB(player); setQueryB(player); setOpenB(false); setActiveB(-1); };

    return (
        <form className="scouting-form" onSubmit={handleSubmit}>
            <div className="scouting-form-header">
                <Activity size={20} strokeWidth={2} style={{ color: '#22d3ee' }} />
                <h3>Iniciar Rastreador In-Play en Vivo</h3>
                <p>Configura las condiciones del partido para loguear los juegos y actualizar probabilidades Bayes en vivo.</p>
            </div>

            <div className="scouting-form-grid">
                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="live-player-a">Jugador A</label>
                    <div style={{ position: 'relative' }}>
                        <input
                            id="live-player-a"
                            name="player_a"
                            type="text"
                            className="coach-player-input"
                            value={queryA}
                            placeholder="Buscar jugador A..."
                            onChange={e => { setQueryA(e.target.value); setOpenA(true); setActiveA(-1); setPlayerA(''); }}
                            onFocus={() => setOpenA(true)}
                            onBlur={() => setTimeout(() => setOpenA(false), 150)}
                            onKeyDown={e => {
                                if (e.key === 'ArrowDown') { e.preventDefault(); setActiveA(i => Math.min(i + 1, filteredA.length - 1)); }
                                if (e.key === 'ArrowUp') { e.preventDefault(); setActiveA(i => Math.max(i - 1, 0)); }
                                if (e.key === 'Enter' && showA && filteredA[activeA]) { e.preventDefault(); selectA(filteredA[activeA]); }
                                if (e.key === 'Escape') setOpenA(false);
                            }}
                            role="combobox"
                            aria-autocomplete="list"
                            aria-expanded={showA}
                            aria-controls="live-player-a-options"
                            aria-activedescendant={showA && activeA >= 0 ? `live-player-a-option-${activeA}` : undefined}
                        />
                        {showA && (
                            <ul className="coach-player-dropdown" id="live-player-a-options" role="listbox">
                                {filteredA.map((p, index) => (
                                    <li
                                        key={p}
                                        id={`live-player-a-option-${index}`}
                                        className={index === activeA ? 'active' : ''}
                                        role="option"
                                        aria-selected={index === activeA}
                                        onMouseEnter={() => setActiveA(index)}
                                        onMouseDown={event => { event.preventDefault(); selectA(p); }}
                                    >{p}</li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>

                <div className="scouting-vs-divider">VS</div>

                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="live-player-b">Jugador B</label>
                    <div style={{ position: 'relative' }}>
                        <input
                            id="live-player-b"
                            name="player_b"
                            type="text"
                            className="coach-player-input"
                            value={queryB}
                            placeholder="Buscar jugador B..."
                            onChange={e => { setQueryB(e.target.value); setOpenB(true); setActiveB(-1); setPlayerB(''); }}
                            onFocus={() => setOpenB(true)}
                            onBlur={() => setTimeout(() => setOpenB(false), 150)}
                            onKeyDown={e => {
                                if (e.key === 'ArrowDown') { e.preventDefault(); setActiveB(i => Math.min(i + 1, filteredB.length - 1)); }
                                if (e.key === 'ArrowUp') { e.preventDefault(); setActiveB(i => Math.max(i - 1, 0)); }
                                if (e.key === 'Enter' && showB && filteredB[activeB]) { e.preventDefault(); selectB(filteredB[activeB]); }
                                if (e.key === 'Escape') setOpenB(false);
                            }}
                            role="combobox"
                            aria-autocomplete="list"
                            aria-expanded={showB}
                            aria-controls="live-player-b-options"
                            aria-activedescendant={showB && activeB >= 0 ? `live-player-b-option-${activeB}` : undefined}
                        />
                        {showB && (
                            <ul className="coach-player-dropdown" id="live-player-b-options" role="listbox">
                                {filteredB.map((p, index) => (
                                    <li
                                        key={p}
                                        id={`live-player-b-option-${index}`}
                                        className={index === activeB ? 'active' : ''}
                                        role="option"
                                        aria-selected={index === activeB}
                                        onMouseEnter={() => setActiveB(index)}
                                        onMouseDown={event => { event.preventDefault(); selectB(p); }}
                                    >{p}</li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            </div>

            <div className="live-config-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '0.5rem' }}>
                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="live-surface">Superficie</label>
                    <select id="live-surface" name="surface" className="coach-player-input" value={surface} onChange={e => setSurface(e.target.value)}>
                        <option value="Hard">Hard (Dura)</option>
                        <option value="Clay">Clay (Tierra)</option>
                        <option value="Grass">Grass (Hierba)</option>
                    </select>
                </div>

                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="live-best-of">Formato del partido</label>
                    <select id="live-best-of" name="best_of" className="coach-player-input" value={bestOf} onChange={e => setBestOf(parseInt(e.target.value) as 3 | 5)}>
                        <option value={3}>Al mejor de 3 sets</option>
                        <option value={5}>Al mejor de 5 sets</option>
                    </select>
                </div>

                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="live-first-server">Primer servidor</label>
                    <select id="live-first-server" name="first_server" className="coach-player-input" value={firstServer} onChange={e => setFirstServer(e.target.value as 'A' | 'B' | 'random')}>
                        <option value="random">Aleatorio (Sorteo)</option>
                        <option value="A">Jugador A</option>
                        <option value="B">Jugador B</option>
                    </select>
                </div>
            </div>

            <button
                type="submit"
                className="scouting-submit-btn"
                disabled={!playerA || !playerB || playerA === playerB || loading}
                id="live-init-submit-btn"
                style={{ marginTop: '0.5rem' }}
            >
                {loading ? (
                    <><Loader2 size={16} className="scouting-spin" /> Creando sesión...</>
                ) : (
                    <><Play size={16} /> Inicializar Tracker en Vivo</>
                )}
            </button>
        </form>
    );
}

export function LiveTracker() {
    const [players, setPlayers] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [state, setState] = useState<InPlayStateResponse | null>(null);

    const [serverPoints, setServerPoints] = useState(0);
    const [returnerPoints, setReturnerPoints] = useState(0);
    const [pointHistory, setPointHistory] = useState<PointWinner[]>([]);
    const [updating, setUpdating] = useState(false);

    const isTiebreak = state?.games_a === 6 && state?.games_b === 6;
    const pointScore = formatTennisScore(serverPoints, returnerPoints, Boolean(isTiebreak));

    useEffect(() => {
        setServerPoints(0);
        setReturnerPoints(0);
        setPointHistory([]);
    }, [isTiebreak, state?.match_id]);

    useEffect(() => {
        fetchPlayers().then(setPlayers).catch(() => {});

        const savedMatchId = localStorage.getItem('matchpoint_live_match_id');
        if (savedMatchId) {
            setLoading(true);
            getInplayState(savedMatchId)
                .then(setState)
                .catch(() => {
                    localStorage.removeItem('matchpoint_live_match_id');
                })
                .finally(() => setLoading(false));
        }
    }, []);

    const handleInit = async (req: InPlayInitRequest) => {
        setLoading(true);
        setError(null);
        try {
            const data = await inplayInit(req);
            setState(data);
            localStorage.setItem('matchpoint_live_match_id', data.match_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error al inicializar sesión');
        } finally {
            setLoading(false);
        }
    };

    const handleLogGame = async (winner: 'A' | 'B', completedServerPoints: number, completedReturnerPoints: number) => {
        if (!state) return;
        setUpdating(true);
        setError(null);
        try {
            const data = await inplayUpdate({
                match_id: state.match_id,
                server: state.current_server,
                game_winner: winner,
                server_points_won: completedServerPoints,
                server_points_lost: completedReturnerPoints,
                is_tiebreak: isTiebreak,
            });
            setState(data);
            setServerPoints(0);
            setReturnerPoints(0);
            setPointHistory([]);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error al registrar juego');
        } finally {
            setUpdating(false);
        }
    };

    const handlePoint = (pointWinner: PointWinner) => {
        if (!state || updating) return;
        const nextServerPoints = serverPoints + (pointWinner === 'server' ? 1 : 0);
        const nextReturnerPoints = returnerPoints + (pointWinner === 'returner' ? 1 : 0);
        setServerPoints(nextServerPoints);
        setReturnerPoints(nextReturnerPoints);
        setPointHistory(history => [...history, pointWinner]);

        if (isCompletedGame(nextServerPoints, nextReturnerPoints, Boolean(isTiebreak))) {
            const winnerIsServer = nextServerPoints > nextReturnerPoints;
            const gameWinner = winnerIsServer
                ? state.current_server
                : (state.current_server === 'A' ? 'B' : 'A');
            void handleLogGame(gameWinner, nextServerPoints, nextReturnerPoints);
        }
    };

    const undoLastPoint = () => {
        if (updating || pointHistory.length === 0) return;
        const lastPoint = pointHistory[pointHistory.length - 1];
        setPointHistory(history => history.slice(0, -1));
        if (lastPoint === 'server') setServerPoints(points => Math.max(0, points - 1));
        else setReturnerPoints(points => Math.max(0, points - 1));
    };

    const handleReset = async () => {
        if (window.confirm('¿Seguro que deseas reiniciar el rastreador? Se perderá el historial del partido actual.')) {
            const matchId = state?.match_id;
            localStorage.removeItem('matchpoint_live_match_id');
            setState(null);
            setError(null);
            if (matchId) {
                try {
                    await deleteInplayState(matchId);
                } catch (err) {
                    setError(err instanceof Error ? err.message : 'No se pudo eliminar la sesión remota');
                }
            }
        }
    };

    const isFinished = state?.status === 'finished';

    return (
        <div className="live-tracker-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {!state && (
                <InPlaySetup players={players} onSubmit={handleInit} loading={loading} />
            )}

            {error && (
                <div className="coach-error-banner" style={{ margin: 0 }}>
                    <AlertTriangle size={15} />
                    {error}
                </div>
            )}

            {state && (
                <div className="live-panel-grid" style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '1.5rem' }}>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

                        <div className="live-score-card">
                            <div className="live-score-header">
                                <span className="live-score-title">Marcador en Vivo</span>
                                <span className={`live-status-badge ${isFinished ? 'finished' : 'live'}`}>
                                    {isFinished ? 'Finalizado' : 'En Curso'}
                                </span>
                            </div>

                            <div className="live-score-grid">
                                <div className="live-grid-row header">
                                    <span className="col-p">Jugador</span>
                                    <span className="col-s">Sets</span>
                                    <span className="col-g">Juegos</span>
                                </div>

                                <div className={`live-grid-row ${isFinished && state.winner === 'A' ? 'winner' : ''}`}>
                                    <span className="col-p">
                                        {state.player_a} {state.current_server === 'A' && !isFinished && '🎾'}
                                    </span>
                                    <span className="col-s">{state.sets_a}</span>
                                    <span className="col-g">{state.games_a}</span>
                                </div>

                                <div className={`live-grid-row ${isFinished && state.winner === 'B' ? 'winner' : ''}`}>
                                    <span className="col-p">
                                        {state.player_b} {state.current_server === 'B' && !isFinished && '🎾'}
                                    </span>
                                    <span className="col-s">{state.sets_b}</span>
                                    <span className="col-g">{state.games_b}</span>
                                </div>
                            </div>
                        </div>

                        {!isFinished ? (
                            <div className="scouting-form">
                                <div className="live-score-header" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.5rem', marginBottom: '0.2rem' }}>
                                    <span className="live-score-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#22d3ee' }}>
                                        <Plus size={16} /> Registrar Siguiente Juego
                                    </span>
                                    <span className="live-server-hint" style={{ fontSize: '0.78rem', color: '#64748b' }}>
                                        Servidor actual: <strong>{state.current_server === 'A' ? state.player_a.split(' ').pop() : state.player_b.split(' ').pop()}</strong>
                                    </span>
                                </div>

                                <div className={`live-point-score ${isTiebreak ? 'is-tiebreak' : ''}`}>
                                    <div className="live-point-player">
                                        <span className="live-point-role">{isTiebreak ? 'Inicia el tie-break' : 'Servidor'}</span>
                                        <strong>{state.current_server === 'A' ? state.player_a : state.player_b}</strong>
                                        <span className="live-point-value" aria-label={`${serverPoints} puntos ganados`}>{pointScore.server}</span>
                                    </div>

                                    <div className="live-point-status" aria-live="polite">
                                        <span>{isTiebreak ? 'Tie-break' : 'Puntuación del juego'}</span>
                                        <strong>{pointScore.status}</strong>
                                        <small>{serverPoints + returnerPoints} puntos disputados</small>
                                    </div>

                                    <div className="live-point-player returner">
                                        <span className="live-point-role">{isTiebreak ? 'Rival' : 'Restador'}</span>
                                        <strong>{state.current_server === 'A' ? state.player_b : state.player_a}</strong>
                                        <span className="live-point-value" aria-label={`${returnerPoints} puntos ganados`}>{pointScore.returner}</span>
                                    </div>
                                </div>

                                <div className="live-point-actions">
                                    <button
                                        type="button"
                                        className="live-point-btn server"
                                        disabled={updating || pointScore.completed}
                                        onClick={() => handlePoint('server')}
                                        id="log-point-server"
                                    >
                                        {updating ? <Loader2 size={14} className="scouting-spin" /> : <Plus size={14} />}
                                        Punto para {state.current_server === 'A' ? state.player_a.split(' ').pop() : state.player_b.split(' ').pop()}
                                    </button>

                                    <button
                                        type="button"
                                        className="live-point-btn returner"
                                        disabled={updating || pointScore.completed}
                                        onClick={() => handlePoint('returner')}
                                        id="log-point-returner"
                                    >
                                        {updating ? <Loader2 size={14} className="scouting-spin" /> : <Plus size={14} />}
                                        Punto para {state.current_server === 'A' ? state.player_b.split(' ').pop() : state.player_a.split(' ').pop()}
                                    </button>

                                    <button
                                        type="button"
                                        className="live-point-undo"
                                        disabled={updating || pointHistory.length === 0}
                                        onClick={undoLastPoint}
                                    >
                                        <Undo2 size={14} /> Deshacer
                                    </button>
                                </div>

                                <p className="live-point-help">
                                    {isTiebreak
                                        ? 'Puntuación numérica: gana quien llegue al menos a 7 con dos puntos de diferencia.'
                                        : 'El juego se registra automáticamente al alcanzar cuatro puntos con dos de diferencia.'}
                                </p>
                            </div>
                        ) : (
                            <div className="coach-sim-card" style={{ border: '1px solid rgba(52, 211, 153, 0.3)', background: 'rgba(52, 211, 153, 0.03)' }}>
                                <div className="live-score-header">
                                    <span className="live-score-title" style={{ color: '#34d399', fontWeight: 800 }}><Trophy size={17} aria-hidden="true" /> Ganador: {state.winner === 'A' ? state.player_a : state.player_b}</span>
                                </div>
                                <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.55 }}>
                                    El partido ha finalizado. Puedes revisar el histórico final y los parámetros estimados de servicio acumulados en el panel derecho.
                                </p>
                            </div>
                        )}

                        <button className="coach-reset-btn" onClick={handleReset} style={{ alignSelf: 'flex-start' }}>
                            <RefreshCw size={13} /> Reiniciar rastreador (Nuevo partido)
                        </button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

                        <div className="coach-results-panel" style={{ padding: '1.25rem' }}>
                            <span className="coach-results-title" style={{ fontSize: '0.85rem', color: '#f1f5f9' }}>Probabilidad en Vivo (Momentum)</span>
                            <LiveProbabilityChart
                                events={state.events}
                                playerA={state.player_a}
                                playerB={state.player_b}
                                width={360}
                                height={150}
                            />

                            <div className="live-metrics-summary" style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.76rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.5rem' }}>
                                <span style={{ color: '#22d3ee', fontWeight: 700 }}>Live P({state.player_a.split(' ').pop()}): {Math.round(state.p_live_a * 100)}%</span>
                                <span style={{ color: '#64748b' }}>Incertidumbre: {(state.uncertainty * 100).toFixed(0)}pp</span>
                                <span style={{ color: '#a78bfa', fontWeight: 700 }}>Live P({state.player_b.split(' ').pop()}): {Math.round((1 - state.p_live_a) * 100)}%</span>
                            </div>
                        </div>

                        <div className="scouting-stats-panel" style={{ padding: '1.25rem' }}>
                            <span className="scouting-stats-center-label" style={{ textAlign: 'left', marginBottom: '0.5rem' }}>Inferencia Bayesiana de Saque</span>

                            <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '0.5rem' }}>
                                El modelo actualiza continuamente la probabilidad estimada de ganar puntos de servicio a medida que se acumulan observaciones ({state.n_observations} puntos).
                            </p>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.4rem' }}>
                                    <span style={{ color: '#22d3ee', fontWeight: 600 }}>{state.player_a.split(' ').pop()}</span>
                                    <span style={{ color: '#94a3b8' }}>Prior: {(state.p_prior_a * 100).toFixed(1)}%</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.4rem' }}>
                                    <span style={{ color: '#a78bfa', fontWeight: 600 }}>{state.player_b.split(' ').pop()}</span>
                                    <span style={{ color: '#94a3b8' }}>Prior: {((1 - state.p_prior_a) * 100).toFixed(1)}%</span>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>
            )}
        </div>
    );
}
