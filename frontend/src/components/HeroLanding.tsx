import { LandingFeatures } from './landing/LandingFeatures';
import { LandingFinalCta } from './landing/LandingFinalCta';
import { LandingHero } from './landing/LandingHero';
import { LandingNav } from './landing/LandingNav';
import { LandingPreview } from './landing/LandingPreview';
import { LandingProcess } from './landing/LandingProcess';

interface HeroLandingProps {
    onEnter: () => void;
}

export function HeroLanding({ onEnter }: HeroLandingProps) {
    return (
        <div className="landing-v3-page">
            <LandingNav onEnter={onEnter} />
            <main>
                <LandingHero onEnter={onEnter} />
                <LandingProcess />
                <LandingPreview onEnter={onEnter} />
                <LandingFeatures onEnter={onEnter} />
                <LandingFinalCta onEnter={onEnter} />
            </main>
            <footer className="landing-v3-footer">
                <a href="#inicio">MatchPoint</a>
            </footer>
        </div>
    );
}
