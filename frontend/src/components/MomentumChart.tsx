// frontend/src/components/MomentumChart.tsx
import type { SimulateResponse, SetEvent } from '../api/client';
import { LineChart } from 'lucide-react';

interface MomentumChartProps {
    result: SimulateResponse;
}

interface MomentumPoint {
    index: number;
    pA: number;       // running win probability estimate for A
    setChange: boolean;
    label: string;
}

/**
 * Builds the running probability of A winning the match.
 * Prefer backend live probabilities when available; keep the score-based
 * heuristic as a fallback for legacy/proxy timelines.
 */
function buildMomentumPoints(result: SimulateResponse): MomentumPoint[] {
    const timeline = result.timeline;
    if (!timeline) return [];

    const points: MomentumPoint[] = [];
    let idx = 0;
    let setsA = 0;
    let setsB = 0;
    const totalSets = result.result.sets.length;
    const basePa = result.p_a;

    for (let si = 0; si < timeline.length; si++) {
        const set: SetEvent = timeline[si];
        const games = set.games;
        if (!games) continue;

        let gamesA = 0;
        let gamesB = 0;

        for (let gi = 0; gi < games.length; gi++) {
            const game = games[gi];

            // Update game score from the score string e.g. "3-2"
            const parts = game.score.split('-').map(Number);
            if (parts.length === 2) {
                gamesA = parts[0];
                gamesB = parts[1];
            }

            // Heuristic momentum: weighted blend of base probability and current advantage
            // Set advantage
            const setsDiff = (setsA - setsB) / Math.max(totalSets - 1, 1);
            // Game advantage within set (normalized)
            const maxGames = 7; // up to 7 in tiebreak
            const gamesDiff = (gamesA - gamesB) / maxGames;

            // Fallback blend: 60% base model, 30% set score, 10% current games
            const heuristicMomentum = Math.max(0.02, Math.min(0.98,
                basePa * 0.6 + (0.5 + setsDiff * 0.5) * 0.3 + (0.5 + gamesDiff * 0.5) * 0.1
            ));
            const momentum = typeof game.p_live_a === 'number'
                ? Math.max(0.02, Math.min(0.98, game.p_live_a))
                : heuristicMomentum;

            points.push({
                index: idx++,
                pA: momentum,
                setChange: gi === 0 && si > 0,
                label: `Set ${si + 1}, Juego ${game.game}`,
            });

            // Check if we're at "points" mode - look for nested points data
            if (game.points && game.points.length > 0) {
                // We have point-by-point data — add sub-points with finer momentum
                for (let pi = 0; pi < game.points.length; pi++) {
                    const pProgress = (pi + 1) / game.points.length;
                    // Interpolate momentum within the game
                    const prevPa = points[points.length - 1]?.pA ?? momentum;
                    const pt = points[points.length - 1];
                    if (pt) {
                        points.push({
                            index: idx++,
                            pA: Math.max(0.02, Math.min(0.98,
                                prevPa * (1 - pProgress * 0.05) + momentum * pProgress * 0.05
                            )),
                            setChange: false,
                            label: `Set ${si + 1}, J${game.game}, P${pi + 1}`,
                        });
                    }
                }
            }
        }

        // Update sets after this set completes
        if (set.winner === 'A') setsA++;
        else setsB++;
    }

    return points;
}

export function MomentumChart({ result }: MomentumChartProps) {
    const hasPointsData = result.timeline && result.timeline.some(
        (s) => s.games?.some((g) => g.points && g.points.length > 0)
    );
    const hasLiveData = result.timeline && result.timeline.some(
        (s) => s.games?.some((g) => typeof g.p_live_a === 'number')
    );

    const hasTimeline = result.timeline && result.timeline.length > 0;

    if (!hasTimeline) {
        return (
            <div className="momentum-chart momentum-chart--empty">
                <h4 className="section-heading"><LineChart size={17} aria-hidden="true" /> Gráfico de momentum</h4>
                <p className="momentum-hint">
                    Selecciona el modo <strong>"Puntos (detallado)"</strong> en el formulario de simulación para ver la evolución del momentum punto a punto.
                </p>
            </div>
        );
    }

    const points = buildMomentumPoints(result);
    if (points.length < 2) return null;

    // SVG dimensions
    const W = 600;
    const H = 180;
    const PADDING = { top: 20, right: 16, bottom: 28, left: 44 };
    const chartW = W - PADDING.left - PADDING.right;
    const chartH = H - PADDING.top - PADDING.bottom;

    // Scale functions
    const xScale = (i: number) => PADDING.left + (i / (points.length - 1)) * chartW;
    const yScale = (p: number) => PADDING.top + (1 - p) * chartH;

    // Build SVG path
    const pathD = points
        .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(1)} ${yScale(pt.pA).toFixed(1)}`)
        .join(' ');

    // Gradient area path (closed)
    const areaD = pathD +
        ` L ${xScale(points.length - 1).toFixed(1)} ${yScale(0.5).toFixed(1)}` +
        ` L ${xScale(0).toFixed(1)} ${yScale(0.5).toFixed(1)} Z`;

    // Set change markers
    const setChanges = points.filter((p) => p.setChange);

    // Colors: cyan for A advantage, red for B advantage
    const midY = yScale(0.5);

    return (
        <div className="momentum-chart">
            <h4 className="section-heading">
                <LineChart size={17} aria-hidden="true" /> Gráfico de momentum
                {!hasPointsData && !hasLiveData && (
                    <span className="momentum-subtitle"> - estimacion por juegos</span>
                )}
                {hasLiveData && (
                    <span className="momentum-subtitle"> - probabilidad live bayesiana</span>
                )}
                {hasPointsData && !hasLiveData && (
                    <span className="momentum-subtitle"> - estimacion punto a punto</span>
                )}
            </h4>

            <div className="momentum-players-legend">
                <span className="legend-a"><span className="momentum-legend-swatch" aria-hidden="true" /> {result.player_a}</span>
                <span className="legend-b"><span className="momentum-legend-swatch" aria-hidden="true" /> {result.player_b}</span>
            </div>

            <svg
                viewBox={`0 0 ${W} ${H}`}
                className="momentum-svg"
                role="img"
                aria-label={`Gráfico de momentum del partido entre ${result.player_a} y ${result.player_b}`}
            >
                {/* Gradient definition */}
                <defs>
                    <linearGradient id="momentum-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgba(34,211,238,0.3)" />
                        <stop offset="50%" stopColor="rgba(34,211,238,0.05)" />
                        <stop offset="100%" stopColor="rgba(239,68,68,0.1)" />
                    </linearGradient>
                </defs>

                {/* Grid lines */}
                {[0.25, 0.5, 0.75].map((p) => (
                    <line
                        key={p}
                        x1={PADDING.left} y1={yScale(p)}
                        x2={W - PADDING.right} y2={yScale(p)}
                        stroke={p === 0.5 ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.07)'}
                        strokeWidth={p === 0.5 ? 1.5 : 0.8}
                        strokeDasharray={p === 0.5 ? 'none' : '4 4'}
                    />
                ))}

                {/* Y axis labels */}
                {[
                    { p: 0.75, label: '75%' },
                    { p: 0.5, label: '50%' },
                    { p: 0.25, label: '25%' },
                ].map(({ p, label }) => (
                    <text
                        key={p}
                        x={PADDING.left - 6}
                        y={yScale(p) + 4}
                        textAnchor="end"
                        fontSize="10"
                        fill="rgba(255,255,255,0.4)"
                    >
                        {label}
                    </text>
                ))}

                {/* Area fill */}
                <path d={areaD} fill="url(#momentum-grad)" opacity="0.6" />

                {/* Main line */}
                <path
                    d={pathD}
                    fill="none"
                    stroke="#22d3ee"
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                />

                {/* 50% baseline */}
                <line
                    x1={PADDING.left} y1={midY}
                    x2={W - PADDING.right} y2={midY}
                    stroke="rgba(255,255,255,0.2)"
                    strokeWidth="1"
                />

                {/* Set change markers */}
                {setChanges.map((pt) => (
                    <line
                        key={pt.index}
                        x1={xScale(pt.index)} y1={PADDING.top}
                        x2={xScale(pt.index)} y2={H - PADDING.bottom}
                        stroke="rgba(255,255,255,0.25)"
                        strokeWidth="1"
                        strokeDasharray="3 3"
                    />
                ))}

                {/* Final point highlight */}
                <circle
                    cx={xScale(points.length - 1)}
                    cy={yScale(points[points.length - 1].pA)}
                    r="4"
                    fill="#22d3ee"
                    stroke="rgba(15,23,42,0.8)"
                    strokeWidth="1.5"
                />

                {/* X axis label */}
                <text
                    x={W / 2}
                    y={H - 4}
                    textAnchor="middle"
                    fontSize="10"
                    fill="rgba(255,255,255,0.35)"
                >
                    Progreso del partido →
                </text>
            </svg>

            {/* Set labels */}
            <div className="momentum-set-labels">
                {result.result.sets.map((s, i) => (
                    <span key={i} className="momentum-set-label">Set {i + 1}: {s}</span>
                ))}
            </div>
        </div>
    );
}
