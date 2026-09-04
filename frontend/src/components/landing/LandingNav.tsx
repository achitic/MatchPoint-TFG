import { ArrowUpRight } from 'lucide-react';

interface LandingNavProps {
    onEnter: () => void;
}

export function LandingNav({ onEnter }: LandingNavProps) {
    return (
        <header className="landing-v3-nav">
            <a className="landing-v3-brand" href="#inicio" aria-label="MatchPoint, volver al inicio">
                <span className="landing-v3-brand-mark" aria-hidden="true">MP</span>
                <span>MatchPoint</span>
            </a>

            <nav className="landing-v3-nav-links" aria-label="Navegación de la landing">
                <a href="#capacidades">Capacidades</a>
                <a href="#como-funciona">Cómo funciona</a>
            </nav>

            <button className="landing-v3-button landing-v3-button-small" type="button" onClick={onEnter}>
                Abrir aplicación
                <ArrowUpRight size={16} aria-hidden="true" />
            </button>
        </header>
    );
}
