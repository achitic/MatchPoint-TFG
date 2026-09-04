// frontend/src/components/HeadToHead.tsx
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Swords } from 'lucide-react';
import type { H2HResponse } from '../api/client';
import { fetchH2H } from '../api/client';

interface HeadToHeadProps {
    playerA: string;
    playerB: string;
}

export function HeadToHead({ playerA, playerB }: HeadToHeadProps) {
    const requestKey = `${playerA}|${playerB}`;
    const [requestState, setRequestState] = useState<{
        key: string;
        data: H2HResponse | null;
        error: string | null;
    }>({ key: '', data: null, error: null });
    const [expanded, setExpanded] = useState(true);

    useEffect(() => {
        if (!playerA || !playerB) return;
        let active = true;
        fetchH2H(playerA, playerB)
            .then((data) => {
                if (active) setRequestState({ key: requestKey, data, error: null });
            })
            .catch((error: unknown) => {
                if (active) {
                    setRequestState({
                        key: requestKey,
                        data: null,
                        error: error instanceof Error ? error.message : 'No se pudo cargar el historial directo.',
                    });
                }
            });
        return () => { active = false; };
    }, [playerA, playerB, requestKey]);

    const loading = requestState.key !== requestKey;
    const data = loading ? null : requestState.data;
    const error = loading ? null : requestState.error;

    if (loading) return (
        <div className="h2h-card">
            <div className="h2h-header">
                <span className="h2h-title"><Swords size={17} aria-hidden="true" /> Head-to-Head</span>
            </div>
            <div className="h2h-loading">Cargando historial...</div>
        </div>
    );

    if (error) return (
        <div className="h2h-card">
            <div className="h2h-header">
                <span className="h2h-title"><Swords size={17} aria-hidden="true" /> Head-to-Head</span>
            </div>
            <div className="h2h-empty">{error}</div>
        </div>
    );

    if (!data) return null;

    const { stats, matches } = data;
    const totalPct = stats.total > 0 ? (stats.wins_a / stats.total) * 100 : 50;

    return (
        <div className="h2h-card">
            <button
                type="button"
                className="h2h-header"
                onClick={() => setExpanded(e => !e)}
                aria-expanded={expanded}
                aria-controls="h2h-content"
            >
                <span className="h2h-title"><Swords size={17} aria-hidden="true" /> Head-to-Head: {playerA} vs {playerB}</span>
                <span className="h2h-toggle" aria-hidden="true">{expanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}</span>
            </button>

            {expanded && (
                <div id="h2h-content">
                    {stats.total === 0 ? (
                        <div className="h2h-empty">Sin enfrentamientos directos registrados en el dataset.</div>
                    ) : (
                        <>
                            {/* Visual ratio bar */}
                            <div className="h2h-ratio">
                                <div className="h2h-ratio-name h2h-name-a">{playerA}</div>
                                <div className="h2h-ratio-bar-wrap">
                                    <div className="h2h-ratio-bar">
                                        <div
                                            className="h2h-ratio-fill-a"
                                            style={{ width: `${totalPct}%` }}
                                        />
                                        <div
                                            className="h2h-ratio-fill-b"
                                            style={{ width: `${100 - totalPct}%` }}
                                        />
                                    </div>
                                    <div className="h2h-ratio-counts">
                                        <span className="h2h-count-a">{stats.wins_a}V</span>
                                        <span className="h2h-total">{stats.total} partidos</span>
                                        <span className="h2h-count-b">{stats.wins_b}V</span>
                                    </div>
                                </div>
                                <div className="h2h-ratio-name h2h-name-b">{playerB}</div>
                            </div>

                            {/* Surface breakdown */}
                            {Object.keys(stats.by_surface).length > 0 && (
                                <div className="h2h-surfaces">
                                    {Object.entries(stats.by_surface).map(([surf, s]) => (
                                        <div key={surf} className="h2h-surface-row">
                                            <span className="h2h-surf-label">{surf}</span>
                                            <span className="h2h-surf-a">{s.wins_a}</span>
                                            <div className="h2h-surf-bar">
                                                <div
                                                    className="h2h-surf-fill-a"
                                                    style={{ width: `${s.total > 0 ? (s.wins_a / s.total) * 100 : 50}%` }}
                                                />
                                            </div>
                                            <span className="h2h-surf-b">{s.wins_b}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Match history table */}
                            {matches.length > 0 && (
                                <div className="h2h-matches">
                                    <table className="h2h-table">
                                        <thead>
                                            <tr>
                                                <th>Fecha</th>
                                                <th>Torneo</th>
                                                <th>Superficie</th>
                                                <th>Ganador</th>
                                                <th>Resultado</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {matches.map((m: import('../api/client').H2HMatch, i: number) => (
                                                <tr key={i} className={m.winner === playerA ? 'h2h-row-a' : 'h2h-row-b'}>
                                                    <td>{m.date}</td>
                                                    <td className="h2h-tournament">{m.tournament}</td>
                                                    <td>{m.surface}</td>
                                                    <td className="h2h-winner">{m.winner}</td>
                                                    <td className="h2h-score">{m.score}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
