import { ArrowRight } from 'lucide-react';

interface LandingFinalCtaProps {
    onEnter: () => void;
}

export function LandingFinalCta({ onEnter }: LandingFinalCtaProps) {
    return (
        <section className="landing-v3-final" aria-labelledby="landing-final-title">
            <div>
                <p className="landing-v3-eyebrow">Tu próximo enfrentamiento</p>
                <h2 id="landing-final-title">Convierte los datos en una lectura del partido.</h2>
            </div>
            <button className="landing-v3-button landing-v3-button-light" type="button" onClick={onEnter}>
                Explorar MatchPoint
                <ArrowRight size={17} aria-hidden="true" />
            </button>
        </section>
    );
}
