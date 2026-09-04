import { useState, useCallback, useRef, useEffect } from 'react';
import { Sliders, RefreshCw, TrendingUp, TrendingDown, Minus, AlertTriangle, Loader2, BookOpen, ChevronDown, ChevronUp, Play, MoveHorizontal, Info, Trophy, ClipboardCheck, ArrowRight } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import type { PredictResponse, SimulateResponse } from '../api/client';
import { fetchPlayers, predict, simulateMatch } from '../api/client';
import { applyBoosts } from './coachProbability';
import type { BoostParams } from './coachProbability';
import type { TacticalPlanPayload } from './coachTacticalPlan';

interface SliderConfig {
    id: string;
    label: string;
    sublabel: string;
    min: number;
    max: number;
    step: number;
    default: number;
    unit: string;
    positive_helps: 'A' | 'B' | 'both';
}

interface WhatIfResult {
    base_pa: number;
    adjusted_pa: number;
    delta: number;
    boosts: BoostParams;
    player_a: string;
    player_b: string;
    surface: string;
}

const SLIDER_CONFIGS: SliderConfig[] = [
    {
        id: 'first_serve_boost',
        label: '% 1er servicio',
        sublabel: 'Ajusta la efectividad del primer saque del jugador A',
        min: -0.20,
        max: 0.20,
        step: 0.01,
        default: 0,
        unit: '%',
        positive_helps: 'A',
    },
    {
        id: 'ace_boost',
        label: 'Potencia de saque',
        sublabel: 'Simula un saque más / menos dominante (efecto ace)',
        min: -0.15,
        max: 0.15,
        step: 0.01,
        default: 0,
        unit: '%',
        positive_helps: 'A',
    },
    {
        id: 'bp_resilience_boost',
        label: 'Resiliencia mental',
        sublabel: 'Gestión de break points (presión en puntos clave)',
        min: -0.20,
        max: 0.20,
        step: 0.01,
        default: 0,
        unit: '%',
        positive_helps: 'A',
    },
    {
        id: 'fatigue_factor',
        label: 'Fatiga / forma física',
        sublabel: 'Simula el desgaste acumulado en el torneo',
        min: -0.25,
        max: 0.10,
        step: 0.01,
        default: 0,
        unit: '%',
        positive_helps: 'A',
    },
    {
        id: 'surface_adaptation',
        label: 'Adaptación a superficie',
        sublabel: 'Nivel de comodidad del jugador A en esta superficie',
        min: -0.15,
        max: 0.15,
        step: 0.01,
        default: 0,
        unit: '%',
        positive_helps: 'A',
    },
];

function InlinePlayerSearch({
    value,
    onChange,
    players,
    placeholder,
    id,
}: {
    value: string;
    onChange: (v: string) => void;
    players: string[];
    placeholder: string;
    id: string;
}) {
    const [query, setQuery] = useState(value);
    const [open, setOpen] = useState(false);
    const [activeIdx, setActiveIdx] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);

    const filtered = players
        .filter(p => p.toLowerCase().includes(query.toLowerCase().trim()))
        .slice(0, 8);

    const select = (p: string) => {
        setQuery(p);
        onChange(p);
        setOpen(false);
    };
    const listboxId = `${id}-options`;
    const showOptions = open && filtered.length > 0 && query.length >= 2;

    return (
        <div className="coach-player-search" style={{ position: 'relative' }}>
            <input
                ref={inputRef}
                id={id}
                name={id}
                type="text"
                className="coach-player-input"
                value={query}
                placeholder={placeholder}
                onChange={e => { setQuery(e.target.value); setOpen(true); setActiveIdx(0); onChange(''); }}
                onFocus={() => setOpen(true)}
                onBlur={() => setTimeout(() => setOpen(false), 150)}
                onKeyDown={e => {
                    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, filtered.length - 1)); }
                    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
                    if (e.key === 'Enter' && showOptions && filtered[activeIdx]) { e.preventDefault(); select(filtered[activeIdx]); }
                    if (e.key === 'Escape') setOpen(false);
                }}
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={showOptions}
                aria-controls={listboxId}
                aria-activedescendant={showOptions ? `${listboxId}-${activeIdx}` : undefined}
            />
            {showOptions && (
                <ul className="coach-player-dropdown" id={listboxId} role="listbox">
                    {filtered.map((p, i) => (
                        <li
                            key={p}
                            id={`${listboxId}-${i}`}
                            className={i === activeIdx ? 'active' : ''}
                            role="option"
                            aria-selected={i === activeIdx}
                            onMouseEnter={() => setActiveIdx(i)}
                            onMouseDown={event => { event.preventDefault(); select(p); }}
                        >{p}</li>
                    ))}
                </ul>
            )}
        </div>
    );
}

function BoostSlider({
    config,
    value,
    onChange,
}: {
    config: SliderConfig;
    value: number;
    onChange: (v: number) => void;
}) {
    const pct = value * 100;
    const sliderId = `coach-slider-${config.id}`;
    const descriptionId = `${sliderId}-description`;
    const isNeutral = Math.abs(value) < 0.005;
    const isPositive = value > 0.005;
    const isNegative = value < -0.005;

    const trackStyle = (() => {
        const center = 50;
        const spread = Math.abs(value / (config.max || 0.2)) * 50;
        if (isNeutral) return {};
        if (isPositive) return { background: `linear-gradient(90deg, transparent ${center}%, rgba(52,211,153,0.35) ${center}%, rgba(52,211,153,0.35) ${center + spread}%, transparent ${center + spread}%)` };
        return { background: `linear-gradient(90deg, transparent ${center - spread}%, rgba(248,113,113,0.35) ${center - spread}%, rgba(248,113,113,0.35) ${center}%, transparent ${center}%)` };
    })();

    return (
        <div className="coach-slider-wrap">
            <div className="coach-slider-header">
                <div>
                    <label className="coach-slider-label" htmlFor={sliderId}>{config.label}</label>
                    <span className="coach-slider-sublabel" id={descriptionId}>{config.sublabel}</span>
                </div>
                <div className={`coach-slider-value ${isPositive ? 'coach-val-pos' : isNegative ? 'coach-val-neg' : 'coach-val-zero'}`}>
                    {isPositive && '+'}{pct.toFixed(0)}{config.unit}
                </div>
            </div>
            <div className="coach-slider-track-wrap" style={trackStyle}>
                <input
                    id={sliderId}
                    name={config.id}
                    type="range"
                    className="coach-range"
                    min={config.min}
                    max={config.max}
                    step={config.step}
                    value={value}
                    onChange={e => onChange(parseFloat(e.target.value))}
                    aria-describedby={descriptionId}
                    aria-valuetext={`${pct > 0 ? '+' : ''}${pct.toFixed(0)} por ciento`}
                />
                <div className="coach-slider-center-mark" />
            </div>
            <div className="coach-slider-extremes">
                <span className="coach-slider-extreme-neg"><TrendingDown size={11} /> Peor</span>
                <span className="coach-slider-extreme-neutral"><Minus size={11} /> Base</span>
                <span className="coach-slider-extreme-pos"><TrendingUp size={11} /> Mejor</span>
            </div>
        </div>
    );
}

function ProbGauge({ pa, playerA, playerB, delta }: { pa: number; playerA: string; playerB: string; delta?: number }) {
    const pct = Math.round(pa * 100);
    const color = pa > 0.55 ? '#34d399' : pa < 0.45 ? '#f87171' : '#22d3ee';

    return (
        <div className="coach-gauge-wrap">
            <div className="coach-gauge-ring" style={{ '--gauge-pct': pct, '--gauge-color': color } as React.CSSProperties}>
                <div className="coach-gauge-inner">
                    <span className="coach-gauge-pct" style={{ color }}>{pct}%</span>
                    <span className="coach-gauge-name">{playerA.split(' ').pop()}</span>
                </div>
            </div>
            <div className="coach-gauge-labels">
                <span className="coach-gauge-a" style={{ color }}>{playerA.split(' ').pop()}: {pct}%</span>
                <span className="coach-gauge-sep">·</span>
                <span className="coach-gauge-b">{playerB.split(' ').pop()}: {100 - pct}%</span>
            </div>
            {delta !== undefined && Math.abs(delta) > 0.002 && (
                <div className={`coach-delta-badge ${delta > 0 ? 'coach-delta-pos' : 'coach-delta-neg'}`}>
                    {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}pp vs base
                </div>
            )}
        </div>
    );
}

function ResultsPanel({ base, adjusted }: { base: WhatIfResult; adjusted: WhatIfResult | null }) {
    const [showLegend, setShowLegend] = useState(false);

    return (
        <div className="coach-results-panel">
            <div className="coach-results-header">
                <span className="coach-results-title">Simulación What-If</span>
                <button type="button" className="coach-legend-btn" onClick={() => setShowLegend(v => !v)} aria-expanded={showLegend} aria-controls="coach-legend-content">
                    <BookOpen size={13} />
                    Cómo funciona
                    {showLegend ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </button>
            </div>

            {showLegend && (
                <div className="coach-legend" id="coach-legend-content">
                    <p>
                        Los sliders ajustan la probabilidad base del modelo mediante un
                        desplazamiento en el espacio logit (log-odds). Cada slider modela un
                        factor táctico: un boost de +10% en "1er Servicio" equivale a subir
                        la probabilidad base como si el jugador A mejorara su efectividad de
                        saque en esa proporción. Los efectos son aditivos en logit space y se
                        convierten de vuelta a probabilidad con la función sigmoide, garantizando
                        que el resultado siempre esté en [0, 1].
                    </p>
                </div>
            )}

            <div className="coach-gauges-row">
                <div className="coach-gauge-col">
                    <span className="coach-gauge-col-label">Base (sin ajustes)</span>
                    <ProbGauge pa={base.base_pa} playerA={base.player_a} playerB={base.player_b} />
                </div>
                {adjusted && (
                    <>
                        <div className="coach-gauges-arrow">→</div>
                        <div className="coach-gauge-col">
                            <span className="coach-gauge-col-label">Ajustado (What-If)</span>
                            <ProbGauge
                                pa={adjusted.adjusted_pa}
                                playerA={adjusted.player_a}
                                playerB={adjusted.player_b}
                                delta={adjusted.delta}
                            />
                        </div>
                    </>
                )}
            </div>

            {adjusted && (
                <div className="coach-insight-bar">
                    {Math.abs(adjusted.delta) < 0.005 ? (
                        <span className="coach-insight-neutral">
                            <Minus size={14} /> Los ajustes no cambian significativamente el pronóstico.
                        </span>
                    ) : adjusted.delta > 0 ? (
                        <span className="coach-insight-positive">
                            <TrendingUp size={14} />
                            Con estos ajustes, <strong>{adjusted.player_a.split(' ').pop()}</strong> mejora su pronóstico
                            en <strong>+{(adjusted.delta * 100).toFixed(1)} pp</strong> ({Math.round(adjusted.base_pa * 100)}% → {Math.round(adjusted.adjusted_pa * 100)}%).
                        </span>
                    ) : (
                        <span className="coach-insight-negative">
                            <TrendingDown size={14} />
                            Con estos ajustes, <strong>{adjusted.player_a.split(' ').pop()}</strong> reduce su pronóstico
                            en <strong>{(adjusted.delta * 100).toFixed(1)} pp</strong> ({Math.round(adjusted.base_pa * 100)}% → {Math.round(adjusted.adjusted_pa * 100)}%).
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}

function TacticalPlanCard({ plan }: { plan: TacticalPlanPayload }) {
    return (
        <section className="coach-imported-plan" aria-labelledby="coach-imported-plan-title">
            <div className="coach-imported-plan-heading">
                <div className="coach-imported-plan-icon" aria-hidden="true"><ClipboardCheck size={20} /></div>
                <div>
                    <span className="coach-imported-plan-kicker">Plan generado desde Scouting</span>
                    <h3 id="coach-imported-plan-title">
                        Cómo explotar las debilidades de {plan.playerB.split(' ').pop()}
                    </h3>
                    <p>
                        Los ajustes son moderados y editables. Representan un escenario táctico hipotético,
                        no una mejora garantizada del rendimiento.
                    </p>
                </div>
            </div>
            <div className="coach-imported-plan-list">
                {plan.reasons.map((reason, index) => (
                    <article className="coach-imported-plan-item" key={`${reason.weakness}-${index}`}>
                        <span className="coach-imported-plan-number">{index + 1}</span>
                        <div>
                            <strong>{reason.weakness}</strong>
                            <p>{reason.action}</p>
                            <div className="coach-imported-plan-tags">
                                {reason.adjustments.map(adjustment => <span key={adjustment}>{adjustment}</span>)}
                            </div>
                        </div>
                    </article>
                ))}
            </div>
            <div className="coach-imported-plan-next">
                <ArrowRight size={15} aria-hidden="true" /> Revisa los controles, ajusta la intensidad si lo necesitas y simula el partido.
            </div>
        </section>
    );
}

function CoachSimulationScoreboard({
    result,
    onRerun,
    loading,
}: {
    result: SimulateResponse;
    onRerun: () => void;
    loading: boolean;
}) {
    const isWinnerA = result.result.winner === 'A';
    const isWinnerB = result.result.winner === 'B';

    const sets = result.result.sets;
    const maxSets = result.timeline ? result.timeline.length : 3;

    const getSetGames = (setIdx: number, player: 'A' | 'B') => {
        const setScore = sets[setIdx];
        if (!setScore) return '—';
        const parts = setScore.split('-');
        return player === 'A' ? parts[0] : parts[1];
    };

    return (
        <div className="coach-sim-card">
            <div className="coach-sim-header">
                <Play size={15} />
                <span>Simulación de partido (what-if)</span>
                <span className="coach-sim-engine">Motor: {result.params.proxy_method.split('+')[0]}</span>
            </div>

            <p className="coach-sim-warning" data-testid="coach-effective-probability">
                <Info size={14} aria-hidden="true" />
                Probabilidad efectiva usada por el simulador: {(result.p_a * 100).toFixed(1)}% para {result.player_a}.
            </p>

            <div className="coach-sim-scoreboard">
                <div className="coach-scoreboard-row header">
                    <span className="col-player">Jugador</span>
                    {Array.from({ length: maxSets }).map((_, idx) => (
                        <span key={idx} className="col-set">Set {idx + 1}</span>
                    ))}
                    <span className="col-sets">Sets</span>
                </div>

                <div className={`coach-scoreboard-row ${isWinnerA ? 'winner' : ''}`}>
                    <span className="col-player">
                        {result.player_a} {isWinnerA && <Trophy className="inline-champion-icon" size={14} aria-label="Ganador" />}
                    </span>
                    {Array.from({ length: maxSets }).map((_, idx) => (
                        <span key={idx} className="col-set">{getSetGames(idx, 'A')}</span>
                    ))}
                    <span className="col-sets">{result.result.sets_a}</span>
                </div>

                <div className={`coach-scoreboard-row ${isWinnerB ? 'winner' : ''}`}>
                    <span className="col-player">
                        {result.player_b} {isWinnerB && <Trophy className="inline-champion-icon" size={14} aria-label="Ganador" />}
                    </span>
                    {Array.from({ length: maxSets }).map((_, idx) => (
                        <span key={idx} className="col-set">{getSetGames(idx, 'B')}</span>
                    ))}
                    <span className="col-sets">{result.result.sets_b}</span>
                </div>
            </div>

            {result.warnings.length > 0 && (
                <div className="coach-sim-warnings">
                    {result.warnings.map((w, idx) => (
                        <p key={idx} className="coach-sim-warning"><Info size={14} aria-hidden="true" /> {w}</p>
                    ))}
                </div>
            )}

            <div className="coach-sim-actions">
                <button type="button" className="coach-sim-rerun-btn" onClick={onRerun} disabled={loading}>
                    {loading ? (
                        <>
                            <Loader2 size={13} className="coach-spin" />
                            Simulando...
                        </>
                    ) : (
                        <>
                            <RefreshCw size={13} />
                            Simular otro partido
                        </>
                    )}
                </button>
                <span className="coach-sim-seed">Semilla: {result.seed_used}</span>
            </div>
        </div>
    );
}

export function CoachMode() {
    const location = useLocation();
    const importedPlan = (location.state as { tacticalPlan?: TacticalPlanPayload } | null)?.tacticalPlan ?? null;
    const [players, setPlayers] = useState<string[]>([]);
    const [playerA, setPlayerA] = useState(importedPlan?.playerA ?? '');
    const [playerB, setPlayerB] = useState(importedPlan?.playerB ?? '');
    const [surface, setSurface] = useState(importedPlan?.surface ?? 'Hard');
    const [model] = useState('core');
    const [boosts, setBoosts] = useState<BoostParams>(importedPlan?.boosts ?? {
        first_serve_boost: 0,
        ace_boost: 0,
        bp_resilience_boost: 0,
        fatigue_factor: 0,
        surface_adaptation: 0,
    });
    const [activePlan, setActivePlan] = useState<TacticalPlanPayload | null>(importedPlan);
    const [baseResult, setBaseResult] = useState<WhatIfResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [simResult, setSimResult] = useState<SimulateResponse | null>(null);
    const [simLoading, setSimLoading] = useState(false);
    const importedPlanLoaded = useRef(false);
    const surfaces = ['Hard', 'Clay', 'Grass'];

    useEffect(() => {
        fetchPlayers().then(setPlayers).catch(() => {});
    }, []);

    useEffect(() => {
        if (!importedPlan || importedPlanLoaded.current) return;
        importedPlanLoaded.current = true;
        setLoading(true);
        setError(null);
        predict({
            player_a: importedPlan.playerA,
            player_b: importedPlan.playerB,
            surface: importedPlan.surface,
            model,
            as_of: null,
            debug: false,
        }).then((res: PredictResponse) => {
            setBaseResult({
                base_pa: res.p_a,
                adjusted_pa: res.p_a,
                delta: 0,
                boosts: importedPlan.boosts,
                player_a: res.player_a,
                player_b: res.player_b,
                surface: res.surface,
            });
        }).catch((err) => {
            setError(err instanceof Error ? err.message : 'Error al obtener predicción base');
        }).finally(() => setLoading(false));
    }, [importedPlan, model]);

    const hasBoosts = Object.values(boosts).some(v => Math.abs(v) > 0.001);

    const adjustedPa = baseResult && hasBoosts
        ? applyBoosts(baseResult.base_pa, boosts)
        : null;
    const adjusted: WhatIfResult | null = baseResult && adjustedPa !== null ? {
        ...baseResult,
        adjusted_pa: adjustedPa,
        delta: adjustedPa - baseResult.base_pa,
        boosts,
    } : null;

    const handlePredict = useCallback(async () => {
        if (!playerA || !playerB || playerA === playerB) return;
        setLoading(true);
        setError(null);
        setSimResult(null); // Clear simulation when predicting new match
        try {
            const res: PredictResponse = await predict({
                player_a: playerA,
                player_b: playerB,
                surface,
                model,
                as_of: null,
                debug: false,
            });
            setBaseResult({
                base_pa: res.p_a,
                adjusted_pa: res.p_a,
                delta: 0,
                boosts,
                player_a: res.player_a,
                player_b: res.player_b,
                surface: res.surface,
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error al obtener predicción base');
        } finally {
            setLoading(false);
        }
    }, [playerA, playerB, surface, model, boosts]);

    const handleSimulate = async (forceNewSeed = false) => {
        if (!baseResult) return;
        setSimLoading(true);
        setError(null);
        try {
            const targetPa = adjusted ? adjusted.adjusted_pa : baseResult.base_pa;
            const res = await simulateMatch({
                player_a: baseResult.player_a,
                player_b: baseResult.player_b,
                surface: baseResult.surface,
                model: 'calibrated_logreg',
                as_of: null,
                best_of: 3,
                seed: forceNewSeed ? null : (simResult?.seed_used ?? null),
                first_server: 'random',
                timeline_mode: 'games',
                engine_mode: 'bayes_live_v1',
                p_a_override: targetPa, // Custom what-if probability override
            });
            setSimResult(res);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error al simular partido con ajustes');
        } finally {
            setSimLoading(false);
        }
    };

    const resetBoosts = () => {
        setBoosts({ first_serve_boost: 0, ace_boost: 0, bp_resilience_boost: 0, fatigue_factor: 0, surface_adaptation: 0 });
        setActivePlan(null);
    };

    const invalidateScenario = () => {
        setBaseResult(null);
        setSimResult(null);
        if (activePlan) {
            setActivePlan(null);
            setBoosts({ first_serve_boost: 0, ace_boost: 0, bp_resilience_boost: 0, fatigue_factor: 0, surface_adaptation: 0 });
        }
    };

    const changePlayerA = (value: string) => {
        setPlayerA(value);
        invalidateScenario();
    };

    const changePlayerB = (value: string) => {
        setPlayerB(value);
        invalidateScenario();
    };

    const changeSurface = (value: string) => {
        setSurface(value);
        invalidateScenario();
    };

    return (
        <div className="coach-container">
            <div className="coach-setup-card">
                <div className="coach-setup-header">
                    <Sliders size={20} strokeWidth={2} />
                    <div>
                        <h3>Modo entrenador — simulación what-if</h3>
                        <p>Selecciona los jugadores y ajusta los sliders para simular escenarios tácticos alternativos</p>
                    </div>
                </div>

                <div className="coach-setup-grid">
                    <div className="coach-setup-field">
                        <label className="coach-field-label" htmlFor="coach-player-a">Tu jugador (A)</label>
                        <InlinePlayerSearch
                            id="coach-player-a"
                            value={playerA}
                            onChange={changePlayerA}
                            players={players}
                            placeholder="Buscar jugador A..."
                        />
                    </div>

                    <div className="coach-vs-pill">VS</div>

                    <div className="coach-setup-field">
                        <label className="coach-field-label" htmlFor="coach-player-b">Rival (B)</label>
                        <InlinePlayerSearch
                            id="coach-player-b"
                            value={playerB}
                            onChange={changePlayerB}
                            players={players.filter(p => p !== playerA)}
                            placeholder="Buscar jugador B..."
                        />
                    </div>
                </div>

                <div className="coach-surface-row">
                    <span className="coach-field-label" id="coach-surface-label">Superficie</span>
                    <div className="coach-surface-btns" role="group" aria-labelledby="coach-surface-label">
                        {surfaces.map(s => (
                            <button
                                key={s}
                                type="button"
                                className={`coach-surface-btn coach-surface-${s.toLowerCase()} ${surface === s ? 'active' : ''}`}
                                onClick={() => changeSurface(s)}
                                aria-pressed={surface === s}
                            >
                                <span className={`surface-swatch surface-swatch-${s.toLowerCase()}`} aria-hidden="true" />
                                {s === 'Hard' ? 'Dura' : s === 'Clay' ? 'Tierra' : 'Hierba'}
                            </button>
                        ))}
                    </div>
                </div>

                <button
                    type="button"
                    className="coach-predict-btn"
                    onClick={handlePredict}
                    disabled={!playerA || !playerB || playerA === playerB || loading}
                    id="coach-predict-btn"
                >
                    {loading ? (
                        <><Loader2 size={16} className="coach-spin" /> Calculando...</>
                    ) : (
                        <><TrendingUp size={16} /> {baseResult ? 'Recalcular base' : 'Obtener predicción base'}</>
                    )}
                </button>
                {playerA === playerB && playerA && (
                    <p className="coach-form-error">Selecciona dos jugadores diferentes.</p>
                )}
                {error && (
                    <div className="coach-error-banner"><AlertTriangle size={15} /> {error}</div>
                )}
            </div>

            {activePlan && <TacticalPlanCard plan={activePlan} />}

            {baseResult && (
                <div className="coach-results-row-wrapper">
                    <ResultsPanel base={baseResult} adjusted={adjusted} />

                    <div className="coach-quick-sim-trigger-wrap">
                        <button
                            type="button"
                            className="coach-predict-btn coach-quick-sim-btn"
                            onClick={() => handleSimulate(true)}
                            disabled={simLoading}
                            style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}
                        >
                            {simLoading ? (
                                <><Loader2 size={16} className="coach-spin" /> Simulando partido...</>
                            ) : (
                                <><Play size={16} /> Simular partido punto a punto con estos ajustes</>
                            )}
                        </button>
                    </div>
                </div>
            )}

            {simResult && (
                <CoachSimulationScoreboard
                    result={simResult}
                    onRerun={() => handleSimulate(true)}
                    loading={simLoading}
                />
            )}

            {baseResult && (
                <div className="coach-sliders-card">
                    <div className="coach-sliders-header">
                        <div>
                            <span className="coach-sliders-title">Ajustes tácticos — {baseResult.player_a.split(' ').pop()}</span>
                            <span className="coach-sliders-subtitle">
                                Valores positivos mejoran el rendimiento de <strong>{baseResult.player_a.split(' ').pop()}</strong> respecto a la predicción base
                            </span>
                        </div>
                        {hasBoosts && (
                            <button type="button" className="coach-reset-btn" onClick={resetBoosts}>
                                <RefreshCw size={13} /> Resetear
                            </button>
                        )}
                    </div>

                    <div className="coach-sliders-grid">
                        {SLIDER_CONFIGS.map(cfg => (
                            <BoostSlider
                                key={cfg.id}
                                config={cfg}
                                value={boosts[cfg.id as keyof BoostParams]}
                                onChange={v => setBoosts(prev => ({ ...prev, [cfg.id]: v }))}
                            />
                        ))}
                    </div>

                    {!hasBoosts && (
                        <p className="coach-sliders-hint">
                            <MoveHorizontal size={16} aria-hidden="true" />
                            Mueve los controles para explorar escenarios tácticos. Los cambios se aplican en tiempo real.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}
