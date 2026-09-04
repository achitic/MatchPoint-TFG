import { ArrowRight, CircleDot, Database, Sparkles } from 'lucide-react';
import { PREVIEW_PLAYERS } from './landingContent';

interface LandingPreviewProps {
    onEnter: () => void;
}

export function LandingPreview({ onEnter }: LandingPreviewProps) {
    return (
        <section className="landing-v3-section landing-v3-preview-section" aria-labelledby="landing-preview-title">
            <div className="landing-v3-section-heading landing-v3-section-heading-centered">
                <p className="landing-v3-eyebrow">Vista previa del producto</p>
                <h2 id="landing-preview-title">El simulador en acción</h2>
                <p>Una muestra de cómo MatchPoint organiza el enfrentamiento, la superficie y la ventaja estimada.</p>
            </div>

            <div className="landing-v3-preview-card">
                <div className="landing-v3-preview-toolbar">
                    <div aria-hidden="true"><span /><span /><span /></div>
                    <strong>MatchPoint — Predicción</strong>
                    <span>Ejemplo ilustrativo</span>
                </div>

                <div className="landing-v3-preview-body">
                    <div className="landing-v3-preview-form">
                        <p className="landing-v3-preview-label">Enfrentamiento</p>
                        <div className="landing-v3-player-stack">
                            {PREVIEW_PLAYERS.map((player, index) => (
                                <div className="landing-v3-player-row" key={player.name}>
                                    <div>
                                        <span>{player.label}</span>
                                        <strong>{player.name}</strong>
                                    </div>
                                    <em>{player.ranking}</em>
                                    {index === 0 ? <b aria-hidden="true">VS</b> : null}
                                </div>
                            ))}
                        </div>

                        <div className="landing-v3-preview-options">
                            <div>
                                <p className="landing-v3-preview-label">Superficie</p>
                                <div className="landing-v3-surface-pills" aria-label="Superficie seleccionada: dura">
                                    <span className="active">Dura</span><span>Tierra</span><span>Hierba</span>
                                </div>
                            </div>
                            <div>
                                <p className="landing-v3-preview-label">Modelo</p>
                                <div className="landing-v3-model-chip"><Database size={14} aria-hidden="true" /> Modelo calibrado</div>
                            </div>
                        </div>

                        <button className="landing-v3-button landing-v3-preview-submit" type="button" onClick={onEnter}>
                            Abrir predicción real
                            <ArrowRight size={16} aria-hidden="true" />
                        </button>
                    </div>

                    <div className="landing-v3-preview-results">
                        <div className="landing-v3-preview-court" aria-hidden="true">
                            <div className="landing-v3-mini-court"><span /></div>
                            <p>Vista sintética · pista dura</p>
                        </div>

                        <div className="landing-v3-probability-panel">
                            <div className="landing-v3-panel-title"><CircleDot size={14} aria-hidden="true" /> Probabilidad de victoria</div>
                            {PREVIEW_PLAYERS.map((player) => (
                                <div className="landing-v3-probability-row" key={player.name}>
                                    <span>{player.name.split(' ')[1]}</span>
                                    <div><i style={{ width: `${player.probability}%` }} /></div>
                                    <strong>{player.probability}%</strong>
                                </div>
                            ))}
                        </div>

                        <div className="landing-v3-advantage-panel">
                            <Sparkles size={18} aria-hidden="true" />
                            <div><span>Ventaja estimada</span><strong>Ligera · Sinner</strong><small>+16 puntos porcentuales</small></div>
                            <div className="landing-v3-confidence-bars" aria-label="Nivel de ventaja 2 de 5"><i /><i /><span /><span /><span /></div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
