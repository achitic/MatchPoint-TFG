// frontend/src/components/ModelComparison.tsx
import { useId, useState } from 'react';
import { BarChart3, ChevronDown, ChevronUp, Microscope, RefreshCw } from 'lucide-react';
import { predict } from '../api/client';
import type { PredictRequest, PredictResponse } from '../api/client';

const ALL_MODELS = [
    { id: 'baseline_logreg', label: 'Modelo base ELO' },
    { id: 'surface_logreg', label: 'Modelo por superficie' },
    { id: 'calibrated_logreg', label: 'Modelo calibrado' },
    { id: 'stacking_ensemble', label: 'Ensemble avanzado' },
];

interface ModelComparisonProps {
    baseRequest: Omit<PredictRequest, 'model'>;
    playerA: string;
    playerB: string;
}

interface ModelResult {
    model: string;
    label: string;
    p_a: number;
    p_b: number;
    error?: string;
}

export function ModelComparison({ baseRequest, playerA, playerB }: ModelComparisonProps) {
    const [results, setResults] = useState<ModelResult[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [expanded, setExpanded] = useState(true);
    const contentId = useId();

    const runComparison = async () => {
        setLoading(true);
        setResults(null);
        const settled = await Promise.allSettled(
            ALL_MODELS.map(m =>
                predict({ ...baseRequest, model: m.id }).then(
                    (res: PredictResponse) => ({ model: m.id, label: m.label, p_a: res.p_a, p_b: res.p_b })
                )
            )
        );
        const parsed: ModelResult[] = settled.map((r, i) =>
            r.status === 'fulfilled'
                ? r.value
                : { model: ALL_MODELS[i].id, label: ALL_MODELS[i].label, p_a: 0, p_b: 0, error: 'Error al cargar' }
        );
        setResults(parsed);
        setLoading(false);
    };

    // Consensus = average p_a across successful models
    const successResults = results?.filter(r => !r.error) ?? [];
    const consensusA = successResults.length > 0
        ? successResults.reduce((s, r) => s + r.p_a, 0) / successResults.length
        : null;

    return (
        <div className="model-comparison-card">
            <button
                type="button"
                className="model-comparison-header"
                onClick={() => setExpanded(e => !e)}
                aria-expanded={expanded}
                aria-controls={contentId}
            >
                <span className="model-comparison-title"><Microscope size={17} aria-hidden="true" /> Comparativa de modelos</span>
                <span className="h2h-toggle" aria-hidden="true">{expanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}</span>
            </button>

            {expanded && (
                <div id={contentId}>
                    {!results && !loading && (
                        <div className="model-comparison-intro">
                            <p>Ejecuta los {ALL_MODELS.length} modelos para este partido y compara sus predicciones.</p>
                            <button type="button" className="compare-run-btn" onClick={runComparison}>
                                <Microscope size={16} aria-hidden="true" /> Comparar todos los modelos
                            </button>
                        </div>
                    )}

                    {loading && (
                        <div className="model-comparison-loading">
                            <div className="spinner" style={{ margin: '0 auto' }}></div>
                            <p>Ejecutando {ALL_MODELS.length} modelos en paralelo...</p>
                        </div>
                    )}

                    {results && !loading && (
                        <>
                            <div className="model-comparison-table-wrap">
                                <table className="model-comparison-table">
                                    <thead>
                                        <tr>
                                            <th>Modelo</th>
                                            <th>{playerA}</th>
                                            <th>Barra</th>
                                            <th>{playerB}</th>
                                            <th>Favorito</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {results.map(r => {
                                            if (r.error) return (
                                                <tr key={r.model} className="mc-row-error">
                                                    <td>{r.label}</td>
                                                    <td colSpan={4} style={{ textAlign: 'center', color: 'var(--error)' }}>Sin datos</td>
                                                </tr>
                                            );
                                            const pctA = (r.p_a * 100).toFixed(1);
                                            const pctB = (r.p_b * 100).toFixed(1);
                                            const favA = r.p_a >= r.p_b;
                                            return (
                                                <tr key={r.model} className={favA ? 'mc-row-fav-a' : 'mc-row-fav-b'}>
                                                    <td className="mc-model-name">{r.label}</td>
                                                    <td className="mc-prob mc-prob-a">{pctA}%</td>
                                                    <td className="mc-bar-cell">
                                                        <div className="mc-bar">
                                                            <div className="mc-bar-a" style={{ width: `${r.p_a * 100}%` }} />
                                                            <div className="mc-bar-b" style={{ width: `${r.p_b * 100}%` }} />
                                                        </div>
                                                    </td>
                                                    <td className="mc-prob mc-prob-b">{pctB}%</td>
                                                    <td className="mc-favorite">
                                                        {favA ? <span className="mc-badge mc-badge-a">{playerA}</span>
                                                               : <span className="mc-badge mc-badge-b">{playerB}</span>}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        {/* Consensus row */}
                                        {consensusA !== null && (
                                            <tr className="mc-row-consensus">
                                                <td className="mc-model-name"><BarChart3 size={15} aria-hidden="true" /> Consenso</td>
                                                <td className="mc-prob mc-prob-a">{(consensusA * 100).toFixed(1)}%</td>
                                                <td className="mc-bar-cell">
                                                    <div className="mc-bar">
                                                        <div className="mc-bar-a" style={{ width: `${consensusA * 100}%` }} />
                                                        <div className="mc-bar-b" style={{ width: `${(1 - consensusA) * 100}%` }} />
                                                    </div>
                                                </td>
                                                <td className="mc-prob mc-prob-b">{((1 - consensusA) * 100).toFixed(1)}%</td>
                                                <td className="mc-favorite">
                                                    {consensusA >= 0.5
                                                        ? <span className="mc-badge mc-badge-a">{playerA}</span>
                                                        : <span className="mc-badge mc-badge-b">{playerB}</span>}
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                            <button
                                className="compare-run-btn"
                                onClick={runComparison}
                                style={{ marginTop: '0.75rem' }}
                                type="button"
                            >
                                <RefreshCw size={16} aria-hidden="true" /> Volver a comparar
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

