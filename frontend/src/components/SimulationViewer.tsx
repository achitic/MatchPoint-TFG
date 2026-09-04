// frontend/src/components/SimulationViewer.tsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { AlertTriangle, CheckCircle2, Clapperboard, Download, Info, RefreshCw, SlidersHorizontal, Trophy } from 'lucide-react';
import type { GameEvent, SimulateResponse } from '../api/client';
import { MatchScoreboard } from './MatchScoreboard';
import { MatchCourt2D } from './MatchCourt2D';
import { MomentumChart } from './MomentumChart';
import { PlaybackControls } from './PlaybackControls';
import { PointInspector } from './PointInspector';
import { useToast } from './toastContext';

interface SimulationViewerProps {
    result: SimulateResponse;
    onRerunSameSeed?: () => void;
    showVisualCourt?: boolean;
}

interface PlaybackState {
    setIndex: number;
    gameIndex: number;
    pointIndex: number;
    setsA: number;
    setsB: number;
    gamesA: number;
    gamesB: number;
    currentSetScore: string;
}

function getInitialState(): PlaybackState {
    return {
        setIndex: 0,
        gameIndex: -1,
        pointIndex: -1,
        setsA: 0,
        setsB: 0,
        gamesA: 0,
        gamesB: 0,
        currentSetScore: "0-0",
    };
}

export function SimulationViewer({ result, onRerunSameSeed, showVisualCourt = false }: SimulationViewerProps) {
    const toast = useToast();
    const [isPlaying, setIsPlaying] = useState(false);
    const [speed, setSpeed] = useState(1);
    const [playbackState, setPlaybackState] = useState<PlaybackState>(getInitialState());
    const [isFinished, setIsFinished] = useState(false);
    const intervalRef = useRef<number | null>(null);

    const timeline = result.timeline;
    const engineMethod = result.params.proxy_method;
    const engineLabel = engineMethod.startsWith('bayes_live_v1') ? 'bayes live v1' : 'proxy v0';
    const hasTimeline = timeline && timeline.length > 0;
    const hasPointTimeline = Boolean(timeline?.some((set) =>
        set.games?.some((game) => game.points && game.points.length > 0)
    ));
    const activeSet = timeline?.[playbackState.setIndex];
    const activeGame = playbackState.gameIndex >= 0
        ? activeSet?.games?.[playbackState.gameIndex]
        : undefined;
    const activePoint = activeGame?.points?.[playbackState.pointIndex];

    // Calculate total events for progress
    const totalEvents = hasTimeline
        ? timeline.reduce((sum, set) => sum + (set.games?.reduce((gameSum, game) =>
            gameSum + (hasPointTimeline ? Math.max(game.points?.length || 0, 1) : 1), 0
        ) || 0), 0)
        : 0;

    const currentEventIndex = hasTimeline
        ? timeline.slice(0, playbackState.setIndex).reduce((sum, set) => sum + (set.games?.reduce((gameSum, game) =>
            gameSum + (hasPointTimeline ? Math.max(game.points?.length || 0, 1) : 1), 0
        ) || 0), 0)
        + (timeline[playbackState.setIndex]?.games?.slice(0, Math.max(playbackState.gameIndex, 0)).reduce((gameSum, game) =>
            gameSum + (hasPointTimeline ? Math.max(game.points?.length || 0, 1) : 1), 0
        ) || 0)
        + (playbackState.gameIndex >= 0 ? Math.max(playbackState.pointIndex, 0) + 1 : 0)
        : 0;

    const keyPoints = hasPointTimeline && timeline
        ? timeline.flatMap((set, setIndex) =>
            (set.games || []).flatMap((game) =>
                (game.points || []).map((point) => {
                    const pointServer = point.server ?? game.server;
                    const serverName = pointServer === 'A' ? result.player_a : result.player_b;
                    const returnerName = pointServer === 'A' ? result.player_b : result.player_a;
                    const winnerName = point.winner === 'A'
                        ? result.player_a
                        : point.winner === 'B'
                            ? result.player_b
                            : point.winner === 'server'
                                ? serverName
                                : returnerName;
                    const pressure = point.pressure ?? 0;
                    const label = game.type === 'tiebreak' && pressure >= 1
                        ? 'Set point'
                        : game.type === 'tiebreak' && pressure >= 0.7
                            ? 'Tiebreak cerrado'
                            : pressure >= 1
                                ? 'Deuce / ventaja'
                                : pressure >= 0.5
                                    ? 'Break o game point'
                                    : '';

                    return {
                        set: setIndex + 1,
                        game: game.game,
                        point: point.point,
                        score: point.score,
                        label,
                        pressure,
                        fatigue: point.fatigue_factor ?? game.fatigue_factor ?? 0,
                        serverName,
                        winnerName,
                    };
                })
            )
        )
            .filter((point) => point.label)
            .sort((a, b) => b.pressure - a.pressure || b.fatigue - a.fatigue)
            .slice(0, 8)
        : [];

    const advancePlayback = useCallback(() => {
        if (!timeline) return;

        setPlaybackState((prev) => {
            const currentSet = timeline[prev.setIndex];
            if (!currentSet?.games) return prev;

            const currentGame = prev.gameIndex >= 0 ? currentSet.games[prev.gameIndex] : null;
            const currentPoints = currentGame?.points || [];
            if (hasPointTimeline && currentPoints.length > 0 && prev.pointIndex < currentPoints.length - 1) {
                return {
                    ...prev,
                    pointIndex: prev.pointIndex + 1,
                };
            }

            const nextGameIndex = prev.gameIndex + 1;

            // Check if we've finished the current set
            if (nextGameIndex >= currentSet.games.length) {
                // Move to next set
                const nextSetIndex = prev.setIndex + 1;

                // Update sets score
                const newSetsA = prev.setsA + (currentSet.winner === 'A' ? 1 : 0);
                const newSetsB = prev.setsB + (currentSet.winner === 'B' ? 1 : 0);

                if (nextSetIndex >= timeline.length) {
                    // Match finished
                    setIsFinished(true);
                    setIsPlaying(false);
                    return {
                        ...prev,
                        setIndex: prev.setIndex,
                        gameIndex: currentSet.games.length - 1,
                        pointIndex: -1,
                        setsA: newSetsA,
                        setsB: newSetsB,
                        gamesA: 0,
                        gamesB: 0,
                        currentSetScore: currentSet.score,
                    };
                }

                // Start new set
                return {
                    setIndex: nextSetIndex,
                    gameIndex: -1,
                    pointIndex: -1,
                    setsA: newSetsA,
                    setsB: newSetsB,
                    gamesA: 0,
                    gamesB: 0,
                    currentSetScore: "0-0",
                };
            }

            // Process next game in current set
            const game = currentSet.games[nextGameIndex];
            const [gA, gB] = game.score.split('-').map(Number);

            return {
                ...prev,
                gameIndex: nextGameIndex,
                pointIndex: hasPointTimeline && game.points && game.points.length > 0 ? 0 : -1,
                gamesA: gA,
                gamesB: gB,
                currentSetScore: game.score,
            };
        });
    }, [timeline, hasPointTimeline]);

    // Playback interval
    useEffect(() => {
        if (isPlaying && hasTimeline && !isFinished) {
            const interval = 1000 / speed;
            intervalRef.current = window.setInterval(advancePlayback, interval);
        }
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        };
    }, [isPlaying, speed, hasTimeline, isFinished, advancePlayback]);

    const handlePlay = () => {
        if (isFinished) {
            handleReset();
        }
        setIsPlaying(true);
    };

    const handlePause = () => {
        setIsPlaying(false);
    };

    const handleReset = () => {
        setIsPlaying(false);
        setIsFinished(false);
        setPlaybackState(getInitialState());
    };

    // Format percentage
    const fmt = (n?: number) => typeof n === 'number' ? (n * 100).toFixed(1) + '%' : 'n/d';
    const fmtProb = (n?: number) => typeof n === 'number' ? n.toFixed(4) : 'n/d';

    const handleExportCSV = () => {
        const winner = result.result.winner === 'A' ? result.player_a : result.player_b;
        const rows = [
            ['Jugador A', 'Jugador B', 'Superficie', 'Modelo', 'Motor', 'Fecha datos', 'Semilla', 'Resultado (sets)', 'Ganador'],
            [
                result.player_a,
                result.player_b,
                result.surface,
                result.model,
                engineMethod,
                result.as_of_used,
                String(result.seed_used),
                result.result.sets.join(' '),
                winner,
            ],
        ];
        const csv = rows.map(r => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `simulacion_${result.player_a.replace(/\s/g, '_')}_vs_${result.player_b.replace(/\s/g, '_')}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Simulación exportada como CSV');
    };

    const renderCurrentEvent = (game: GameEvent) => {
        const activePoint = game.points?.[playbackState.pointIndex];
        const pointServer = activePoint?.server ?? game.server;
        const serverName = pointServer === 'A' ? result.player_a : result.player_b;

        return (
            <div className="event-card">
                <div className="event-mainline">
                    <strong>Game {game.game}</strong>
                    <span>Servidor: {serverName}</span>
                    {game.type === 'tiebreak' && <span>Tiebreak</span>}
                    <span>Juego: <strong>{game.winner === 'A' ? result.player_a : result.player_b}</strong></span>
                </div>
                {activePoint && (
                    <PointInspector
                        game={game}
                        point={activePoint}
                        playerA={result.player_a}
                        playerB={result.player_b}
                        formatPercent={fmt}
                    />
                )}
            </div>
        );
    };

    return (
        <div className="simulation-viewer">
            {/* Summary Panel */}
            <div className="sim-summary">
                <div className="sim-header">
                <h2>Resultado de simulación</h2>
                    <div className="sim-badges">
                        <span className="surface-badge">{result.surface}</span>
                        <span className="model-badge">{result.model}</span>
                        <span className="engine-badge">{engineLabel}</span>
                        <span className="date-badge">datos al {result.as_of_used}</span>
                        <span className="seed-badge">semilla: {result.seed_used}</span>
                    </div>
                </div>

                {/* Warnings */}
                {result.warnings && result.warnings.length > 0 && (
                    <div className="warnings-section">
                        <h4 className="section-heading"><AlertTriangle size={17} aria-hidden="true" /> Avisos</h4>
                        <ul className="warnings-list">
                            {result.warnings.map((w, i) => (
                                <li key={i}>{w}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Model Probabilities */}
                <div className="sim-probabilities">
                    <div className="prob-item">
                        <span className="prob-label">{result.player_a}</span>
                        <span className="prob-value player-a-color">{fmt(result.p_a)}</span>
                    </div>
                    <div className="prob-item">
                        <span className="prob-label">{result.player_b}</span>
                        <span className="prob-value player-b-color">{fmt(result.p_b)}</span>
                    </div>
                </div>

                {/* Simulation Parameters */}
                <div className="sim-params">
                    <h4 className="section-heading"><SlidersHorizontal size={17} aria-hidden="true" /> Parámetros de simulación</h4>
                    <div className="params-grid">
                        <div className="param">
                            <span className="param-label">P(saque) {result.player_a}</span>
                            <span className="param-value">{fmt(result.params.p_point_on_serve_a)}</span>
                        </div>
                        <div className="param">
                            <span className="param-label">P(saque) {result.player_b}</span>
                            <span className="param-value">{fmt(result.params.p_point_on_serve_b)}</span>
                        </div>
                        <div className="param">
                            <span className="param-label">Fuerza A</span>
                            <span className="param-value">{fmtProb(result.params.strength_a)}</span>
                        </div>
                        <div className="param">
                            <span className="param-label">Motor efectivo</span>
                            <span className="param-value">{engineMethod}</span>
                        </div>
                    </div>
                </div>

                {/* Final Result */}
                <div className="sim-final-result">
                    <h4 className="section-heading"><Trophy size={17} aria-hidden="true" /> Resultado final</h4>
                    <div className="final-score">
                        <span className={`winner ${result.result.winner === 'A' ? 'winner-highlight' : ''}`}>
                            {result.player_a}
                        </span>
                        <span className="sets-score">
                            {result.result.sets.join(' ')}
                        </span>
                        <span className={`winner ${result.result.winner === 'B' ? 'winner-highlight' : ''}`}>
                            {result.player_b}
                        </span>
                    </div>
                    <div className="winner-announcement">
                        Ganador: <strong>{result.result.winner === 'A' ? result.player_a : result.player_b}</strong>
                    </div>
                    <div className="sim-action-row">
                        <button type="button" className="export-btn" onClick={handleExportCSV} title="Exportar resultado como CSV">
                            <Download size={16} aria-hidden="true" /> Exportar CSV
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
            </div>

            {/* Momentum Chart */}
            <MomentumChart result={result} />


            {hasTimeline && (
                <div className="sim-playback">
                    <h4 className="section-heading"><Clapperboard size={17} aria-hidden="true" /> Reproducción del partido</h4>

                    <MatchScoreboard
                        playerA={result.player_a}
                        playerB={result.player_b}
                        setsA={playbackState.setsA}
                        setsB={playbackState.setsB}
                        gamesA={playbackState.gamesA}
                        gamesB={playbackState.gamesB}
                        setIndex={playbackState.setIndex}
                        totalSets={result.result.sets.length}
                    />

                    {showVisualCourt && activeGame && (
                        <MatchCourt2D
                            game={activeGame}
                            point={activePoint}
                            playerA={result.player_a}
                            playerB={result.player_b}
                            surface={result.surface}
                            setIndex={playbackState.setIndex}
                            gameIndex={playbackState.gameIndex}
                        />
                    )}

                    {/* Current Event Info */}
                    {playbackState.setIndex < timeline.length && playbackState.gameIndex >= 0 && (
                        <div className="current-event">
                            {(() => {
                                const set = timeline[playbackState.setIndex];
                                const game = set.games?.[playbackState.gameIndex];
                                if (!game) return null;
                                return renderCurrentEvent(game);
                            })()}
                        </div>
                    )}

                    {keyPoints.length > 0 && (
                        <div className="key-points-panel">
                            <div className="key-points-header">
                                <h5>Puntos clave detectados</h5>
                                <span>{keyPoints.length} momentos</span>
                            </div>
                            <div className="key-points-list">
                                {keyPoints.map((point) => (
                                    <div
                                        className="key-point-row"
                                        key={`${point.set}-${point.game}-${point.point}-${point.label}`}
                                    >
                                        <span className="key-point-tag">{point.label}</span>
                                        <span>Set {point.set}, Game {point.game}, Punto {point.point}</span>
                                        <span>{point.score}</span>
                                        <span>{point.serverName} saca</span>
                                        <strong>{point.winnerName}</strong>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Progress Bar */}
                    <div className="playback-progress">
                        <div
                            className="progress-fill"
                            style={{ width: `${(currentEventIndex / totalEvents) * 100}%` }}
                        />
                    </div>
                    <div className="progress-label">
                        {hasPointTimeline ? 'Evento' : 'Juego'} {currentEventIndex} de {totalEvents}
                    </div>

                    <PlaybackControls
                        isPlaying={isPlaying}
                        isFinished={isFinished}
                        speed={speed}
                        onPlay={handlePlay}
                        onPause={handlePause}
                        onReset={handleReset}
                        onSpeedChange={setSpeed}
                    />

                    {isFinished && (
                        <div className="playback-finished">
                            <CheckCircle2 size={16} aria-hidden="true" /> ¡Partido completado!
                        </div>
                    )}
                </div>
            )}

            {!hasTimeline && (
                <div className="no-timeline">
                    <Info size={16} aria-hidden="true" /> Sin línea de tiempo (timeline_mode era "none")
                </div>
            )}
        </div>
    );
}

