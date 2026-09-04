import { useState, useEffect } from 'react';
import { Shield, Zap, Target, TrendingUp, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Search, Loader2, BarChart2, Crosshair, Scale, Info, ArrowRight, Sliders } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { ScoutingReportResponse, TacticalInsight, ScoutingCompareStats } from '../api/client';
import { fetchScoutingReport, fetchPlayers } from '../api/client';
import { TacticalRadar } from './TacticalRadar';
import { buildFallbackOpportunities, buildTacticalPlan } from './coachTacticalPlan';

// ── Category icon mapping ─────────────────────────────────────────────────────
function CategoryIcon({ category, size = 16 }: { category: string; size?: number }) {
    const props = { size, strokeWidth: 2 };
    if (category === 'serve') return <Zap {...props} />;
    if (category === 'return') return <Target {...props} />;
    if (category === 'mental') return <Shield {...props} />;
    if (category === 'surface') return <TrendingUp {...props} />;
    return <CheckCircle {...props} />;
}

// ── Severity color mapping ────────────────────────────────────────────────────
function severityClass(severity: string, type: string) {
    if (type === 'weakness') {
        if (severity === 'high') return 'insight-weakness-high';
        if (severity === 'medium') return 'insight-weakness-medium';
        return 'insight-weakness-low';
    }
    if (type === 'strength') {
        if (severity === 'high') return 'insight-strength-high';
        if (severity === 'medium') return 'insight-strength-medium';
        return 'insight-strength-low';
    }
    return 'insight-neutral';
}

// ── Single stat bar row ───────────────────────────────────────────────────────
function StatBar({
    label,
    valueA,
    valueB,
    format = 'pct',
    higherIsBetter = true,
}: {
    label: string;
    valueA: number | null;
    valueB: number | null;
    format?: 'pct' | 'elo' | 'raw';
    higherIsBetter?: boolean;
}) {
    const fmt = (v: number | null) => {
        if (v === null) return '—';
        if (format === 'pct') return `${(v * 100).toFixed(1)}%`;
        if (format === 'elo') return v.toFixed(0);
        return v.toFixed(2);
    };

    const normalize = () => {
        if (valueA === null && valueB === null) return { pctA: 50, pctB: 50 };
        const a = valueA ?? 0;
        const b = valueB ?? 0;
        if (a + b === 0) return { pctA: 50, pctB: 50 };
        return {
            pctA: Math.round((a / (a + b)) * 100),
            pctB: Math.round((b / (a + b)) * 100),
        };
    };

    // For ELO: normalize differently (use a 0-3000 scale)
    const getBarWidths = () => {
        if (format === 'elo') {
            const a = valueA ?? 1500;
            const b = valueB ?? 1500;
            const sum = a + b;
            return { pctA: Math.round((a / sum) * 100), pctB: Math.round((b / sum) * 100) };
        }
        return normalize();
    };

    const { pctA, pctB } = getBarWidths();

    const isWinnerA = valueA !== null && valueB !== null && (higherIsBetter ? valueA > valueB : valueA < valueB);
    const isWinnerB = valueA !== null && valueB !== null && (higherIsBetter ? valueB > valueA : valueB < valueA);

    return (
        <div className="scouting-stat-row">
            <span className="scouting-stat-label">{label}</span>
            <span className={`scouting-stat-val scouting-stat-a ${isWinnerA ? 'scouting-stat-winner' : ''}`}>
                {fmt(valueA)} {isWinnerA && '★'}
            </span>
            <div className="scouting-stat-bar-wrap">
                <div className="scouting-stat-bar">
                    <div className="scouting-stat-fill-a" style={{ width: `${pctA}%` }} />
                    <div className="scouting-stat-fill-b" style={{ width: `${pctB}%` }} />
                </div>
            </div>
            <span className={`scouting-stat-val scouting-stat-b ${isWinnerB ? 'scouting-stat-winner' : ''}`}>
                {isWinnerB && '★'} {fmt(valueB)}
            </span>
        </div>
    );
}

// ── Stats panel for one player ────────────────────────────────────────────────
function StatsComparison({ stats_a, stats_b }: { stats_a: ScoutingCompareStats; stats_b: ScoutingCompareStats }) {
    const [viewMode, setViewMode] = useState<'table' | 'radar'>('radar');

    return (
        <div className="scouting-stats-panel">
            {/* Header row */}
            <div className="scouting-stats-header">
                <span className="scouting-player-name-a">{stats_a.player.split(' ').pop()}</span>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.35rem' }}>
                    <span className="scouting-stats-center-label">Estadísticas comparadas — {stats_a.surface}</span>
                    <div className="scouting-view-toggle">
                        <button
                            type="button"
                            className={`scouting-toggle-btn ${viewMode === 'radar' ? 'active' : ''}`}
                            onClick={() => setViewMode('radar')}
                            aria-pressed={viewMode === 'radar'}
                        >
                            <Shield size={12} /> Radar
                        </button>
                        <button
                            type="button"
                            className={`scouting-toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
                            onClick={() => setViewMode('table')}
                            aria-pressed={viewMode === 'table'}
                        >
                            <BarChart2 size={12} /> Tabla
                        </button>
                    </div>
                </div>
                <span className="scouting-player-name-b">{stats_b.player.split(' ').pop()}</span>
            </div>

            {viewMode === 'table' ? (
                <div className="scouting-stat-rows">
                    <StatBar label="1er Servicio" valueA={stats_a.first_serve_pct} valueB={stats_b.first_serve_pct} />
                    <StatBar label="Aces" valueA={stats_a.ace_rate} valueB={stats_b.ace_rate} />
                    <StatBar label="Dobles Faltas" valueA={stats_a.double_fault_rate} valueB={stats_b.double_fault_rate} higherIsBetter={false} />
                    <StatBar label="BP Salvados" valueA={stats_a.bp_saved_pct} valueB={stats_b.bp_saved_pct} />
                    <StatBar label="Ptos. Resto" valueA={stats_a.return_points_won_pct} valueB={stats_b.return_points_won_pct} />
                    <StatBar label="Win Rate" valueA={stats_a.win_rate_surface} valueB={stats_b.win_rate_surface} />
                    <StatBar label="ELO Global" valueA={stats_a.elo_global} valueB={stats_b.elo_global} format="elo" />
                    <StatBar label={`ELO ${stats_a.surface}`} valueA={stats_a.elo_surface} valueB={stats_b.elo_surface} format="elo" />
                </div>
            ) : (
                <TacticalRadar statsA={stats_a} statsB={stats_b} size={300} />
            )}

            <div className="scouting-stats-footer">
                <span>Basado en {stats_a.matches_counted} partidos de {stats_a.player.split(' ').pop()}</span>
                <span>Basado en {stats_b.matches_counted} partidos de {stats_b.player.split(' ').pop()}</span>
            </div>
        </div>
    );
}

// ── Single insight card ───────────────────────────────────────────────────────
function InsightCard({ insight }: { insight: TacticalInsight }) {
    const [expanded, setExpanded] = useState(false);
    const cardClass = severityClass(insight.severity, insight.type);
    const icon = insight.type === 'weakness'
        ? <AlertTriangle size={15} strokeWidth={2} />
        : <CheckCircle size={15} strokeWidth={2} />;

    return (
        <div className={`scouting-insight-card ${cardClass}`}>
            <button type="button" className="scouting-insight-header" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
                <div className="scouting-insight-title-row">
                    <span className="scouting-insight-icon">{icon}</span>
                    <CategoryIcon category={insight.category} size={14} />
                    <span className="scouting-insight-title">{insight.title}</span>
                    {insight.metric_value !== null && (
                        <span className="scouting-insight-metric">
                            {insight.metric_label}: <strong>{insight.metric_value}</strong>
                        </span>
                    )}
                </div>
                <span className="scouting-insight-chevron">
                    {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </span>
            </button>
            {expanded && (
                <div className="scouting-insight-body">
                    <p>{insight.description}</p>
                </div>
            )}
        </div>
    );
}

// ── Advantage banner ──────────────────────────────────────────────────────────
function AdvantageBanner({
    advantage,
    summary,
    playerA,
    playerB,
}: {
    advantage: 'A' | 'B' | 'even';
    summary: string;
    playerA: string;
    playerB: string;
}) {
    const bannerClass =
        advantage === 'A' ? 'scouting-banner-a'
        : advantage === 'B' ? 'scouting-banner-b'
        : 'scouting-banner-even';

    const label =
        advantage === 'A' ? `Ventaja: ${playerA.split(' ').pop()}`
        : advantage === 'B' ? `Ventaja: ${playerB.split(' ').pop()}`
        : 'Partido equilibrado';

    const AdvantageIcon = advantage === 'A' ? Crosshair : advantage === 'B' ? AlertTriangle : Scale;

    return (
        <div className={`scouting-advantage-banner ${bannerClass}`}>
            <div className="scouting-advantage-label"><AdvantageIcon size={17} aria-hidden="true" /> {label}</div>
            <p className="scouting-advantage-summary">{summary}</p>
        </div>
    );
}

// ── Inline player search (same as CoachMode) ─────────────────────────────────
function InlinePlayerSearch({
    value, onChange, players, placeholder, id,
}: { value: string; onChange: (v: string) => void; players: string[]; placeholder: string; id: string; }) {
    const [query, setQuery] = useState(value);
    const [open, setOpen] = useState(false);
    const [activeIdx, setActiveIdx] = useState(0);
    const filtered = players.filter(p => p.toLowerCase().includes(query.toLowerCase().trim())).slice(0, 8);
    const select = (p: string) => { setQuery(p); onChange(p); setOpen(false); };
    const listboxId = `${id}-options`;
    const showOptions = open && filtered.length > 0 && query.length >= 2;
    return (
        <div style={{ position: 'relative' }}>
            <input
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
                    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i+1, filtered.length-1)); }
                    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => Math.max(i-1, 0)); }
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

// ── Setup form ────────────────────────────────────────────────────────────────
function ScoutingForm({
    onSubmit,
    loading,
}: {
    onSubmit: (a: string, b: string, surface: string) => void;
    loading: boolean;
}) {
    const [playerA, setPlayerA] = useState('');
    const [playerB, setPlayerB] = useState('');
    const [surface, setSurface] = useState('Hard');
    const [players, setPlayers] = useState<string[]>([]);
    const surfaces = ['Hard', 'Clay', 'Grass'];

    useEffect(() => { fetchPlayers().then(setPlayers).catch(() => {}); }, []);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (playerA && playerB && playerA !== playerB) {
            onSubmit(playerA, playerB, surface);
        }
    };

    return (
        <form className="scouting-form" onSubmit={handleSubmit}>
            <div className="scouting-form-header">
                <Search size={20} strokeWidth={2} />
                <h3>Análisis de rival</h3>
                <p>Selecciona tu jugador, el rival a analizar y la superficie del partido</p>
            </div>

            <div className="scouting-form-grid">
                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="scouting-player-a">Tu jugador</label>
                    <InlinePlayerSearch
                        id="scouting-player-a"
                        value={playerA}
                        onChange={setPlayerA}
                        players={players}
                        placeholder="Buscar jugador A..."
                    />
                </div>

                <div className="scouting-vs-divider">VS</div>

                <div className="scouting-form-field">
                    <label className="scouting-form-label" htmlFor="scouting-player-b">Rival a analizar</label>
                    <InlinePlayerSearch
                        id="scouting-player-b"
                        value={playerB}
                        onChange={setPlayerB}
                        players={players.filter(p => p !== playerA)}
                        placeholder="Buscar jugador B..."
                    />
                </div>
            </div>

            <div className="scouting-surface-row">
                <span className="scouting-form-label" id="scouting-surface-label">Superficie del partido</span>
                <div className="scouting-surface-buttons" role="group" aria-labelledby="scouting-surface-label">
                    {surfaces.map((s) => (
                        <button
                            key={s}
                            type="button"
                            className={`scouting-surface-btn ${surface === s ? 'active' : ''} scouting-surface-${s.toLowerCase()}`}
                            onClick={() => setSurface(s)}
                            aria-pressed={surface === s}
                        >
                            <span className={`surface-swatch surface-swatch-${s.toLowerCase()}`} aria-hidden="true" />
                            {s === 'Hard' ? 'Dura' : s === 'Clay' ? 'Tierra' : 'Hierba'}
                        </button>
                    ))}
                </div>
            </div>

            <button
                type="submit"
                className="scouting-submit-btn"
                disabled={!playerA || !playerB || playerA === playerB || loading}
                id="scouting-generate-btn"
            >
                {loading ? (
                    <>
                        <Loader2 size={16} className="scouting-spin" />
                        Analizando...
                    </>
                ) : (
                    <>
                        <Shield size={16} />
                        Generar informe de scouting
                    </>
                )}
            </button>
            {playerA === playerB && playerA !== '' && (
                <p className="scouting-error">Selecciona dos jugadores diferentes.</p>
            )}
        </form>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
export function RivalAnalysis() {
    const navigate = useNavigate();
    const [report, setReport] = useState<ScoutingReportResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async (playerA: string, playerB: string, surface: string) => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchScoutingReport(playerA, playerB, surface);
            setReport(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error al generar el informe');
        } finally {
            setLoading(false);
        }
    };

    const handleApplyTacticalPlan = () => {
        if (!report) return;
        const tacticalInputs = report.rival_weaknesses.length > 0
            ? report.rival_weaknesses
            : buildFallbackOpportunities(report.stats_b);
        if (tacticalInputs.length === 0) return;
        const plan = buildTacticalPlan(
            report.player_a,
            report.player_b,
            report.surface,
            tacticalInputs,
        );
        navigate('/app/coach', { state: { tacticalPlan: plan } });
    };

    return (
        <div className="scouting-container">
            <ScoutingForm onSubmit={handleGenerate} loading={loading} />

            {error && (
                <div className="scouting-error-banner">
                    <AlertTriangle size={16} />
                    {error}
                </div>
            )}

            {report && !loading && (
                <div className="scouting-report">
                    {/* Advantage Banner */}
                    <AdvantageBanner
                        advantage={report.overall_advantage}
                        summary={report.advantage_summary}
                        playerA={report.player_a}
                        playerB={report.player_b}
                    />

                    {/* Stats comparison */}
                    <StatsComparison stats_a={report.stats_a} stats_b={report.stats_b} />

                    {/* Three-column insights grid */}
                    <div className="scouting-insights-grid">
                        {/* Weaknesses column */}
                        <div className="scouting-insights-col">
                            <div className="scouting-insights-col-header scouting-col-weaknesses">
                                <AlertTriangle size={16} />
                                <span>Debilidades del Rival</span>
                                <span className="scouting-badge">{report.rival_weaknesses.length}</span>
                            </div>
                            {report.rival_weaknesses.length === 0 ? (
                                <p className="scouting-no-insights">No se detectaron debilidades significativas.</p>
                            ) : (
                                report.rival_weaknesses.map((ins, i) => (
                                    <InsightCard key={i} insight={ins} />
                                ))
                            )}
                        </div>

                        {/* Strengths column */}
                        <div className="scouting-insights-col">
                            <div className="scouting-insights-col-header scouting-col-strengths">
                                <Shield size={16} />
                                <span>Puntos Fuertes del Rival</span>
                                <span className="scouting-badge">{report.rival_strengths.length}</span>
                            </div>
                            {report.rival_strengths.length === 0 ? (
                                <p className="scouting-no-insights">No se detectaron puntos fuertes destacados.</p>
                            ) : (
                                report.rival_strengths.map((ins, i) => (
                                    <InsightCard key={i} insight={ins} />
                                ))
                            )}
                        </div>

                        {/* Recommendations column */}
                        <div className="scouting-insights-col">
                            <div className="scouting-insights-col-header scouting-col-recommendations">
                                <Target size={16} />
                                <span>Plan Estratégico</span>
                                <span className="scouting-badge">{report.recommendations.length}</span>
                            </div>
                            {report.recommendations.length === 0 ? (
                                <p className="scouting-no-insights">
                                    Sin recomendaciones específicas. El rival no presenta debilidades explotables claras.
                                </p>
                            ) : (
                                report.recommendations.map((ins, i) => (
                                    <InsightCard key={i} insight={ins} />
                                ))
                            )}
                        </div>
                    </div>

                    {(report.rival_weaknesses.length > 0 || buildFallbackOpportunities(report.stats_b).length > 0) && (
                        <section className="scouting-coach-bridge" aria-labelledby="scouting-coach-title">
                            <div className="scouting-coach-bridge-icon" aria-hidden="true"><Sliders size={21} /></div>
                            <div className="scouting-coach-bridge-copy">
                                <h4 id="scouting-coach-title">Convertir el scouting en un plan de partido</h4>
                                {report.rival_weaknesses.length > 0 ? (
                                    <p>
                                        Traduce las {report.rival_weaknesses.length} debilidad(es) detectadas en ajustes
                                        moderados para {report.player_a.split(' ').pop()}. Podrás revisarlos y modificarlos
                                        antes de ejecutar la simulación What-If.
                                    </p>
                                ) : (
                                    <p>
                                        El rival no cruza ningún umbral de debilidad. El plan utilizará sus dos áreas
                                        relativamente menos dominantes, sin presentarlas como defectos significativos.
                                    </p>
                                )}
                            </div>
                            <button type="button" className="scouting-coach-bridge-btn" onClick={handleApplyTacticalPlan}>
                                Aplicar plan en Entrenador <ArrowRight size={16} />
                            </button>
                        </section>
                    )}

                    {/* Footer disclaimer */}
                    <p className="scouting-disclaimer">
                        <Info size={14} aria-hidden="true" /> Este informe se basa en datos históricos de la ATP (hasta la fecha del dataset).
                        Las estadísticas reflejan el rendimiento pasado en {report.surface} y deben complementarse
                        con observación reciente del rival.
                    </p>
                </div>
            )}
        </div>
    );
}
