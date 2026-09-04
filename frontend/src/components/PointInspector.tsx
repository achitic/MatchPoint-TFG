import type { GameEvent } from '../api/client';
import { MiniCourt } from './MiniCourt';

type PointEvent = NonNullable<GameEvent['points']>[number];

interface PointInspectorProps {
    game: GameEvent;
    point: PointEvent;
    playerA: string;
    playerB: string;
    formatPercent: (value?: number) => string;
}

export function PointInspector({ game, point, playerA, playerB, formatPercent }: PointInspectorProps) {
    const pointServer = point.server ?? game.server;
    const serverName = pointServer === 'A' ? playerA : playerB;
    const returnerName = pointServer === 'A' ? playerB : playerA;
    const pointWinnerName = point.winner === 'A'
        ? playerA
        : point.winner === 'B'
            ? playerB
            : point.winner === 'server'
                ? serverName
                : returnerName;
    const pointWinnerIsServer = point.winner === 'server' || point.winner === pointServer;

    return (
        <div className="point-inspector">
            <MiniCourt server={pointServer} pointWinnerIsServer={pointWinnerIsServer} />
            <div className="point-details">
                <div className="point-title">
                    Punto {point.point} - {point.score}
                </div>
                <div className="point-winner">
                    Ganador del punto: <strong>{pointWinnerName}</strong>
                </div>
                <div className="point-metrics">
                    <span>Presión {(point.pressure ?? 0).toFixed(2)}</span>
                    <span>Fatiga {((point.fatigue_factor ?? game.fatigue_factor ?? 0) * 100).toFixed(0)}%</span>
                    <span>P saque {formatPercent(point.p_server_eff)}</span>
                    {typeof point.p_server_bayes_after === 'number' && (
                        <span>
                            Bayes {formatPercent(point.p_server_bayes_before)} {'->'} {formatPercent(point.p_server_bayes_after)}
                        </span>
                    )}
                </div>
                {point.trace_factors && point.trace_factors.length > 0 && (
                    <div className="point-trace">
                        <span className="point-trace-title">Por que cambia</span>
                        <ul>
                            {point.trace_factors.map((factor) => (
                                <li key={factor}>{factor}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
}
