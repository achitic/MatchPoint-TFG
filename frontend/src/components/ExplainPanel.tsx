// frontend/src/components/ExplainPanel.tsx
import type { ExplainInfo } from '../api/client';
import { BarChart3 } from 'lucide-react';

interface ExplainPanelProps {
    explain: ExplainInfo;
    playerA: string;
    playerB: string;
}

/** Format number to 4 decimals */
function fmt(n: number): string {
    return n.toFixed(4);
}

export function ExplainPanel({ explain, playerA, playerB }: ExplainPanelProps) {
    const isLogreg = explain.method === 'logreg_coeffs';
    const weightLabel = isLogreg ? 'Coef' : 'Impacto';

    return (
        <div className="explain-panel">
            <h3><BarChart3 size={18} aria-hidden="true" /> Explicación del modelo ({explain.method})</h3>
            <p className="explain-desc">
                Top feature contributions to prediction. Positive contribution favors {playerA}, negative favors {playerB}.
            </p>
            <table className="explain-table">
                <thead>
                    <tr>
                        <th>Feature</th>
                        <th>Value</th>
                        <th>{weightLabel}</th>
                        <th>Contribution</th>
                        <th>Favors</th>
                    </tr>
                </thead>
                <tbody>
                    {explain.top_contributors.map((c) => (
                        <tr key={c.feature} className={c.favors === 'A' ? 'favors-a' : 'favors-b'}>
                            <td className="feature-name">{c.feature}</td>
                            <td className="value">{fmt(c.value)}</td>
                            <td className="value">{fmt(c.coef)}</td>
                            <td className="value contribution">{fmt(c.contribution)}</td>
                            <td className="favors-cell">{c.favors === 'A' ? playerA : playerB}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
