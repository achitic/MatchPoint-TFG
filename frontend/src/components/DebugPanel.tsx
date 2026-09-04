// frontend/src/components/DebugPanel.tsx
import type { DebugInfo } from '../api/client';

interface DebugPanelProps {
    debug: DebugInfo;
    playerA: string;
    playerB: string;
}

export function DebugPanel({ debug, playerA, playerB }: DebugPanelProps) {
    return (
        <div className="debug-panel">
            <h3>🔍 Debug: Feature Analysis</h3>

            <div className="debug-section">
                <h4>Top Feature Differences</h4>
                <table className="debug-table">
                    <thead>
                        <tr>
                            <th>Feature</th>
                            <th>{playerA}</th>
                            <th>{playerB}</th>
                            <th>|Diff|</th>
                        </tr>
                    </thead>
                    <tbody>
                        {debug.top_diffs.map((diff) => (
                            <tr key={diff.feature}>
                                <td className="feature-name">{diff.feature}</td>
                                <td className="value">{diff.a.toFixed(4)}</td>
                                <td className="value">{diff.b.toFixed(4)}</td>
                                <td className="value diff">{diff.diff.toFixed(4)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="debug-columns">
                <div className="debug-section">
                    <h4>{playerA} Features</h4>
                    <table className="debug-table compact">
                        <tbody>
                            {Object.entries(debug.features_a).map(([key, value]) => (
                                <tr key={key}>
                                    <td className="feature-name">{key}</td>
                                    <td className="value">{value.toFixed(4)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="debug-section">
                    <h4>{playerB} Features</h4>
                    <table className="debug-table compact">
                        <tbody>
                            {Object.entries(debug.features_b).map(([key, value]) => (
                                <tr key={key}>
                                    <td className="feature-name">{key}</td>
                                    <td className="value">{value.toFixed(4)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
