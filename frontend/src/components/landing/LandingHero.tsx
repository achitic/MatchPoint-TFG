import { ArrowDown, ArrowRight } from 'lucide-react';

interface LandingHeroProps {
    onEnter: () => void;
}

function EditorialCourt() {
    return (
        <figure className="landing-v3-court-figure">
            <div className="landing-v3-court-stage" aria-hidden="true">
                <span className="landing-v3-orbit landing-v3-orbit-one" />
                <span className="landing-v3-orbit landing-v3-orbit-two" />
                <svg className="landing-v3-court" viewBox="0 0 620 760" role="img" aria-label="Pista de tenis utilizada como representación editorial de una simulación">
                    <defs>
                        <linearGradient id="court-surface" x1="0" y1="0" x2="0.85" y2="1">
                            <stop offset="0" stopColor="#0e4c3c" />
                            <stop offset="1" stopColor="#1c7659" />
                        </linearGradient>
                        <radialGradient id="ball-glow">
                            <stop offset="0" stopColor="#efff71" stopOpacity="1" />
                            <stop offset="0.38" stopColor="#cfee55" stopOpacity="0.84" />
                            <stop offset="1" stopColor="#bada45" stopOpacity="0" />
                        </radialGradient>
                    </defs>
                    <path className="landing-v3-court-shadow" d="M155 84H465L574 682H46L155 84Z" />
                    <path className="landing-v3-court-surface" d="M160 74H460L564 672H56L160 74Z" fill="url(#court-surface)" />
                    <g className="landing-v3-court-lines">
                        <path d="M160 74H460L564 672H56L160 74Z" />
                        <path d="M199 74L157 672M421 74L463 672M310 74V672" />
                        <path d="M106 390H514M133 244H487M157 535H463" />
                    </g>
                    <path className="landing-v3-ball-trail" d="M220 253C285 224 356 263 381 343C397 395 420 427 468 447" />
                    <circle className="landing-v3-ball-glow" cx="468" cy="447" r="42" fill="url(#ball-glow)" />
                    <circle className="landing-v3-ball" cx="468" cy="447" r="9" />
                </svg>
                <div className="landing-v3-court-stat landing-v3-court-stat-top">
                    <span>Superficie</span>
                    <strong>Dura</strong>
                </div>
                <div className="landing-v3-court-stat landing-v3-court-stat-bottom">
                    <span>Ventaja estimada</span>
                    <strong>58 / 42</strong>
                    <small>Ejemplo ilustrativo</small>
                </div>
            </div>
            <figcaption>Recreación visual de una simulación sintética</figcaption>
        </figure>
    );
}

export function LandingHero({ onEnter }: LandingHeroProps) {
    return (
        <section className="landing-v3-hero" id="inicio">
            <div className="landing-v3-hero-copy">
                <p className="landing-v3-eyebrow">
                    <span aria-hidden="true" />
                    Análisis de tenis con machine learning
                </p>
                <h1>
                    Predice el partido.
                    <span>Comprende cada punto.</span>
                </h1>
                <p className="landing-v3-hero-description">
                    MatchPoint convierte datos históricos y modelos predictivos en una experiencia clara para comparar jugadores, simular partidos y entender qué puede decidir el resultado.
                </p>
                <div className="landing-v3-hero-actions">
                    <button className="landing-v3-button" type="button" onClick={onEnter}>
                        Abrir aplicación
                        <ArrowRight size={17} aria-hidden="true" />
                    </button>
                    <a className="landing-v3-button landing-v3-button-secondary" href="#como-funciona">
                        Ver cómo funciona
                        <ArrowDown size={16} aria-hidden="true" />
                    </a>
                </div>
                <dl className="landing-v3-hero-proof" aria-label="Resumen del proyecto">
                    <div><dt>Datos</dt><dd>Histórico ATP</dd></div>
                    <div><dt>Modelos</dt><dd>Calibrados</dd></div>
                    <div><dt>Detalle</dt><dd>Punto a punto</dd></div>
                </dl>
            </div>

            <EditorialCourt />
        </section>
    );
}
