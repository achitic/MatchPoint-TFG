import { motion, useReducedMotion } from 'framer-motion';
import type { GameEvent } from '../api/client';

type PointEvent = NonNullable<GameEvent['points']>[number];

interface MatchCourt2DProps {
    game: GameEvent;
    point?: PointEvent;
    playerA: string;
    playerB: string;
    surface: string;
    setIndex: number;
    gameIndex: number;
}

function pct(value?: number) {
    return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'n/d';
}

function sideName(side: 'A' | 'B', playerA: string, playerB: string) {
    return side === 'A' ? playerA : playerB;
}

function resolveWinner(point: PointEvent | undefined, game: GameEvent, playerA: string, playerB: string) {
    return sideName(resolveWinnerSide(point, game), playerA, playerB);
}

function resolveWinnerSide(point: PointEvent | undefined, game: GameEvent): 'A' | 'B' {
    if (!point) return game.winner;

    const server = point.server ?? game.server;
    const returner = server === 'A' ? 'B' : 'A';
    return point.winner === 'server'
        ? server
        : point.winner === 'returner'
            ? returner
            : point.winner === 'A' || point.winner === 'B'
                ? point.winner
                : game.winner;
}

interface RallyPoint {
    left: string;
    top: string;
}

function buildRallyPath(server: 'A' | 'B', winner: 'A' | 'B', pointNumber: number, pressure: number): RallyPoint[] {
    const rallyLength = 4 + ((pointNumber + Math.round(pressure * 6)) % 5);
    const path: RallyPoint[] = [];
    const startTop = server === 'A' ? 78 : 22;
    const startLeft = server === 'A' ? 30 : 70;

    path.push({ left: `${startLeft}%`, top: `${startTop}%` });

    for (let i = 1; i < rallyLength - 1; i += 1) {
        const toTopCourt = (server === 'A' && i % 2 === 1) || (server === 'B' && i % 2 === 0);
        const laneShift = ((pointNumber + i * 3) % 5) - 2;
        const left = 50 + laneShift * 9 + (i % 2 === 0 ? -6 : 6);
        const top = toTopCourt ? 26 + ((pointNumber + i) % 3) * 6 : 62 + ((pointNumber + i) % 3) * 6;
        path.push({ left: `${Math.max(18, Math.min(82, left))}%`, top: `${top}%` });
    }

    // The winning shot lands on the opponent side.
    path.push(
        winner === 'A'
            ? { left: `${58 + (pointNumber % 3) * 7}%`, top: `${20 + (pointNumber % 2) * 8}%` }
            : { left: `${30 + (pointNumber % 3) * 7}%`, top: `${70 - (pointNumber % 2) * 8}%` },
    );

    return path;
}

export function MatchCourt2D({
    game,
    point,
    playerA,
    playerB,
    surface,
    setIndex,
    gameIndex,
}: MatchCourt2DProps) {
    const reduceMotion = useReducedMotion();
    const server = point?.server ?? game.server;
    const winnerSide = resolveWinnerSide(point, game);
    const winnerName = resolveWinner(point, game, playerA, playerB);
    const serverName = sideName(server, playerA, playerB);
    const returnerName = sideName(server === 'A' ? 'B' : 'A', playerA, playerB);
    const pressure = point?.pressure ?? 0;
    const fatigue = point?.fatigue_factor ?? game.fatigue_factor ?? 0;
    const surfaceClass = surface.toLowerCase();
    const pointWinnerIsServer = point
        ? point.winner === 'server' || point.winner === server
        : game.winner === server;
    const pointNumber = point?.point ?? game.game;
    const rallyPath = buildRallyPath(server, winnerSide, pointNumber, pressure);
    const ballPath = `${server}-${winnerSide}-${pointWinnerIsServer ? 'server' : 'returner'}-${pointNumber}-${game.score}`;
    const rallyDuration = Math.min(1.9, 0.72 + rallyPath.length * 0.16);
    const aMovement = winnerSide === 'A'
        ? { x: [0, 18, 5], y: [0, -8, 0] }
        : { x: [0, -12, 0], y: [0, 7, 0] };
    const bMovement = winnerSide === 'B'
        ? { x: [0, -18, -5], y: [0, 8, 0] }
        : { x: [0, 12, 0], y: [0, -7, 0] };

    return (
        <section className={`match-court-panel surface-${surfaceClass}`}>
            <div className="match-court-header">
                <div>
                    <span className="match-court-kicker">Replay visual</span>
                    <h5>Set {setIndex + 1}, Game {gameIndex + 1}</h5>
                </div>
                <div className="match-court-score">{point ? point.score : game.score}</div>
            </div>

            <div className="match-court-layout">
                <div className="match-court-stage" role="img" aria-label={`Pista 2D del punto actual: saca ${serverName} y gana ${winnerName}`}>
                    <div className="court-lines">
                        <span className="court-line court-line-net" />
                        <span className="court-line court-line-service-top" />
                        <span className="court-line court-line-service-bottom" />
                        <span className="court-line court-line-center" />
                    </div>

                    <div className="rally-trail" aria-hidden="true">
                        {rallyPath.slice(1, -1).map((step, index) => (
                            <span
                                key={`${step.left}-${step.top}-${index}`}
                                style={{
                                    left: step.left,
                                    top: step.top,
                                    opacity: 0.16 + index * 0.06,
                                }}
                            />
                        ))}
                    </div>

                    <motion.div
                        className={`court-avatar court-avatar-a ${server === 'A' ? 'serving' : ''} ${winnerSide === 'A' ? 'point-winner-avatar' : ''}`}
                        animate={reduceMotion ? undefined : aMovement}
                        transition={{ duration: rallyDuration, ease: [0.23, 1, 0.32, 1] }}
                    >
                        <span>{playerA.slice(0, 2).toUpperCase()}</span>
                    </motion.div>
                    <motion.div
                        className={`court-avatar court-avatar-b ${server === 'B' ? 'serving' : ''} ${winnerSide === 'B' ? 'point-winner-avatar' : ''}`}
                        animate={reduceMotion ? undefined : bMovement}
                        transition={{ duration: rallyDuration, ease: [0.23, 1, 0.32, 1] }}
                    >
                        <span>{playerB.slice(0, 2).toUpperCase()}</span>
                    </motion.div>

                    <motion.div
                        key={ballPath}
                        className="match-ball"
                        initial={reduceMotion ? false : { left: rallyPath[0].left, top: rallyPath[0].top }}
                        animate={{
                            left: rallyPath.map((step) => step.left),
                            top: rallyPath.map((step) => step.top),
                            scale: rallyPath.map((_, index) => index === rallyPath.length - 1 && pressure >= 0.8 ? 1.22 : 1),
                        }}
                        transition={{ duration: reduceMotion ? 0 : rallyDuration, ease: 'linear' }}
                    />

                    <div className="rally-caption">
                        <span>{server === 'A' ? playerA : playerB} saca</span>
                        <strong>{rallyPath.length - 1} golpes</strong>
                    </div>
                </div>

                <div className="point-story">
                    <div className="story-row">
                        <span>Servidor</span>
                        <strong>{serverName}</strong>
                    </div>
                    <div className="story-row">
                        <span>Restador</span>
                        <strong>{returnerName}</strong>
                    </div>
                    <div className="story-row story-winner">
                        <span>Ganador del punto</span>
                        <strong>{winnerName}</strong>
                    </div>
                    <div className="story-meter">
                        <div>
                            <span>Presión</span>
                            <strong>{pressure.toFixed(2)}</strong>
                        </div>
                        <div className="story-meter-track">
                            <span style={{ width: `${Math.min(pressure, 1) * 100}%` }} />
                        </div>
                    </div>
                    <div className="story-tags">
                        <span>Intercambio {rallyPath.length - 1} golpes</span>
                        <span>Fatiga {pct(fatigue)}</span>
                        <span>P saque {pct(point?.p_server_eff)}</span>
                        {game.type === 'tiebreak' && <span>Tiebreak</span>}
                    </div>
                    {point?.trace_factors && point.trace_factors.length > 0 && (
                        <div className="story-explain">
                            <span>Lectura del modelo</span>
                            <ul>
                                {point.trace_factors.slice(0, 3).map((factor) => (
                                    <li key={factor}>{factor}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}
