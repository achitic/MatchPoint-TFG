import { ArrowUpRight } from 'lucide-react';
import { LANDING_FEATURES } from './landingContent';

interface LandingFeaturesProps {
    onEnter: () => void;
}

export function LandingFeatures({ onEnter }: LandingFeaturesProps) {
    return (
        <section className="landing-v3-section landing-v3-features" id="capacidades" aria-labelledby="landing-features-title">
            <div className="landing-v3-features-heading">
                <div className="landing-v3-section-heading">
                    <p className="landing-v3-eyebrow">Capacidades</p>
                    <h2 id="landing-features-title">Qué puede hacer MatchPoint</h2>
                </div>
                <button className="landing-v3-text-link" type="button" onClick={onEnter}>
                    Explorar la aplicación <ArrowUpRight size={16} aria-hidden="true" />
                </button>
            </div>

            <ol className="landing-v3-features-grid">
                {LANDING_FEATURES.map((feature) => (
                    <li key={feature.number}>
                        <span aria-hidden="true">{feature.number}</span>
                        <h3>{feature.title}</h3>
                        <p>{feature.description}</p>
                    </li>
                ))}
            </ol>
        </section>
    );
}
