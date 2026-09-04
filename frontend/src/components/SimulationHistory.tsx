import { useState } from 'react';
import { ChevronDown, ChevronUp, History } from 'lucide-react';
import type { SimulateResponse } from '../api/client';
import type { HistoryEntry } from './useSimulationHistory';

interface SimulationHistoryProps {
    history: HistoryEntry[];
    onSelect: (result: SimulateResponse) => void;
}

export function SimulationHistory({ history, onSelect }: SimulationHistoryProps) {
    const [expanded, setExpanded] = useState(false);

    if (history.length === 0) return null;

    return (
        <div className="sim-history">
            <button
                type="button"
                className="sim-history-toggle"
                onClick={() => setExpanded((current) => !current)}
                aria-expanded={expanded}
                aria-controls="simulation-history-list"
            >
                <History className="sim-history-icon" size={16} aria-hidden="true" />
                <span>Historial de simulaciones ({history.length})</span>
                {expanded
                    ? <ChevronUp className="sim-history-chevron" size={16} aria-hidden="true" />
                    : <ChevronDown className="sim-history-chevron" size={16} aria-hidden="true" />}
            </button>

            {expanded && (
                <div className="sim-history-list" id="simulation-history-list">
                    {history.map((entry) => (
                        <button
                            type="button"
                            key={entry.id}
                            className="sim-history-entry"
                            onClick={() => onSelect(entry.result)}
                            title="Cargar este resultado"
                        >
                            <span className="sim-history-players">
                                <span className="sim-history-winner">Ganador: {entry.winner}</span>
                                <span className="sim-history-vs">{entry.playerA} vs {entry.playerB}</span>
                            </span>
                            <span className="sim-history-meta">
                                <span className="sim-history-sets">{entry.sets.join(' ')}</span>
                                <span className="sim-history-surface">{entry.surface}</span>
                                <span className="sim-history-date">{entry.timestamp}</span>
                            </span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
