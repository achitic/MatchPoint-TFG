// frontend/src/components/ResultsDisplay.tsx
import { motion, useReducedMotion } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { Link } from 'react-router-dom';
import { AlertTriangle, Download, Info } from 'lucide-react';
import type { PredictResponse } from '../api/client';
import { DebugPanel } from './DebugPanel';
import { ExplainPanel } from './ExplainPanel';
import { AnimatedCounter } from './AnimatedCounter';
import { ConfidenceGauge } from './ConfidenceGauge';
import { useToast } from './toastContext';

interface ResultsDisplayProps {
    result: PredictResponse;
    showDebug: boolean;
}

/* ── Staggered animation variants ── */
const smoothEase = [0.25, 0.46, 0.45, 0.94] as [number, number, number, number];

const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.04,
            delayChildren: 0.02,
        },
    },
};

const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20, scale: 0.97 },
    visible: {
        opacity: 1, y: 0, scale: 1,
        transition: { duration: 0.22, ease: smoothEase },
    },
};

const cardVariants: Variants = {
    hidden: { opacity: 0, y: 30, scale: 0.92 },
    visible: {
        opacity: 1, y: 0, scale: 1,
        transition: { duration: 0.24, ease: smoothEase },
    },
};

const vsVariants: Variants = {
    hidden: { opacity: 0, scale: 0.5, rotate: -10 },
    visible: {
        opacity: 1, scale: 1, rotate: 0,
        transition: { duration: 0.18, ease: 'easeOut' as const, delay: 0.04 },
    },
};

const summaryVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1, y: 0,
        transition: { duration: 0.22, ease: 'easeOut' as const, delay: 0.04 },
    },
};

function exportPrediccionCSV(result: PredictResponse) {
    const rows = [
        ['Jugador A', 'Jugador B', 'Superficie', 'Modelo', 'Fecha datos', 'P(A gana)', 'P(B gana)', 'Ganador predicho'],
        [
            result.player_a,
            result.player_b,
            result.surface,
            result.model,
            result.as_of_used,
            result.p_a.toFixed(4),
            result.p_b.toFixed(4),
            result.p_a > result.p_b ? result.player_a : result.player_b,
        ],
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prediccion_${result.player_a.replace(/\s/g, '_')}_vs_${result.player_b.replace(/\s/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

export function ResultsDisplay({ result, showDebug }: ResultsDisplayProps) {
    const toast = useToast();
    const reduceMotion = useReducedMotion();
    const pA = result.p_a * 100;
    const pB = result.p_b * 100;

    const winner = result.p_a > result.p_b ? result.player_a : result.player_b;
    const winnerProb = Math.max(result.p_a, result.p_b) * 100;

    const handleExport = () => {
        exportPrediccionCSV(result);
        toast.success('Predicción exportada como CSV.');
    };

    return (
        <motion.div
            className="results-container"
            variants={containerVariants}
            initial={reduceMotion ? false : "hidden"}
            animate="visible"
        >
            {/* Header — badges + export */}
            <motion.div className="results-header" variants={itemVariants}>
                <h2>Resultado de predicción</h2>
                <div className="results-header-actions">
                    <div className="match-info">
                        <span className="surface-badge">{result.surface}</span>
                        <span className="model-badge">{result.model}</span>
                        <span className="date-badge">datos al {result.as_of_used}</span>
                    </div>
                    <button className="export-btn" onClick={handleExport} title="Exportar resultado como CSV">
                        <Download size={15} strokeWidth={2} aria-hidden="true" />
                        <span>Exportar CSV</span>
                    </button>
                </div>
            </motion.div>

            {result.warnings && result.warnings.length > 0 && (
                <motion.div className="warnings-section" variants={itemVariants}>
                    <h4>
                        <AlertTriangle size={15} strokeWidth={2} aria-hidden="true" />
                        Avisos
                    </h4>
                    <ul className="warnings-list">
                        {result.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                        ))}
                    </ul>
                </motion.div>
            )}

            {/* Probability cards — staggered entry */}
            <div className="probability-display">
                <motion.div className="player-card player-a" variants={cardVariants}>
                    <Link className="player-name player-profile-link" to={`/app/player/${encodeURIComponent(result.player_a)}`}>
                        {result.player_a}
                    </Link>
                    <div className="probability">
                        <AnimatedCounter value={pA} duration={reduceMotion ? 0 : 320} decimals={1} />
                    </div>
                    <div className="prob-bar">
                        <motion.div
                            className="prob-fill"
                            initial={reduceMotion ? { width: `${pA}%` } : { width: 0 }}
                            animate={{ width: `${pA}%` }}
                            transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.25, 0.46, 0.45, 0.94], delay: reduceMotion ? 0 : 0.08 }}
                        />
                    </div>
                </motion.div>

                <motion.div className="vs-divider" variants={vsVariants}>
                    VS
                </motion.div>

                <motion.div className="player-card player-b" variants={cardVariants}>
                    <Link className="player-name player-profile-link" to={`/app/player/${encodeURIComponent(result.player_b)}`}>
                        {result.player_b}
                    </Link>
                    <div className="probability">
                        <AnimatedCounter value={pB} duration={reduceMotion ? 0 : 320} decimals={1} />
                    </div>
                    <div className="prob-bar">
                        <motion.div
                            className="prob-fill"
                            initial={reduceMotion ? { width: `${pB}%` } : { width: 0 }}
                            animate={{ width: `${pB}%` }}
                            transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.25, 0.46, 0.45, 0.94], delay: reduceMotion ? 0 : 0.1 }}
                        />
                    </div>
                </motion.div>
            </div>

            {/* Winner summary */}
            <motion.div className="prediction-summary" variants={summaryVariants}>
                <span className="winner-label">Ganador predicho:</span>
                <span className="winner-name">{winner}</span>
                <span className="winner-confidence">
                    (<AnimatedCounter value={winnerProb} duration={reduceMotion ? 0 : 360} decimals={1} /> de confianza)
                </span>
            </motion.div>

            {/* Confidence gauge */}
            <motion.div variants={itemVariants}>
                <ConfidenceGauge probability={Math.max(result.p_a, result.p_b)} delay={reduceMotion ? 0 : 0.12} />
            </motion.div>

            {/* Debug and Explain panels */}
            {result.debug && (
                <motion.div variants={itemVariants}>
                    <DebugPanel
                        debug={result.debug}
                        playerA={result.player_a}
                        playerB={result.player_b}
                    />
                </motion.div>
            )}

            {showDebug && result.explain && (
                <motion.div variants={itemVariants}>
                    <ExplainPanel
                        explain={result.explain}
                        playerA={result.player_a}
                        playerB={result.player_b}
                    />
                </motion.div>
            )}

            {showDebug && !result.explain && (
                <motion.div className="explain-unavailable" variants={itemVariants}>
                    <Info size={16} strokeWidth={2} aria-hidden="true" />
                    Explicabilidad no disponible para este modelo.
                </motion.div>
            )}
        </motion.div>
    );
}
