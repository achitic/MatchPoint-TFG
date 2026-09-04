import { ArrowRight } from 'lucide-react';
import { PROCESS_STEPS } from './landingContent';

export function LandingProcess() {
    return (
        <section className="landing-v3-section landing-v3-process" id="como-funciona" aria-labelledby="landing-process-title">
            <div className="landing-v3-section-heading">
                <p className="landing-v3-eyebrow">Cómo funciona</p>
                <h2 id="landing-process-title">Del dato a la simulación</h2>
            </div>

            <ol className="landing-v3-process-grid">
                {PROCESS_STEPS.map((step, index) => (
                    <li key={step.eyebrow}>
                        <div className="landing-v3-process-topline">
                            <span>{String(index + 1).padStart(2, '0')}</span>
                            {index < PROCESS_STEPS.length - 1 ? <ArrowRight size={18} aria-hidden="true" /> : null}
                        </div>
                        <p>{step.eyebrow}</p>
                        <h3>{step.title}</h3>
                        <div className="landing-v3-process-rule" aria-hidden="true" />
                        <p className="landing-v3-process-description">{step.description}</p>
                    </li>
                ))}
            </ol>
        </section>
    );
}
