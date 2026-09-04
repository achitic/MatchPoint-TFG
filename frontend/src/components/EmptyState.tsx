// frontend/src/components/EmptyState.tsx
import { Activity, Lightbulb, Search, Trophy } from 'lucide-react';

interface EmptyStateProps {
    mode: 'predict' | 'simulate' | 'tournament';
}

const CONTENT = {
    predict: {
        icon: Search,
        title: 'Predice el ganador de un partido',
        steps: [
            'Selecciona dos jugadores del ranking ATP',
            'Elige la superficie y la fecha de referencia',
            'Escoge el modelo de Machine Learning',
            'Pulsa "Predecir partido" para ver las probabilidades',
        ],
        hint: 'Prueba: Djokovic vs Alcaraz en Hard Court',
    },
    simulate: {
        icon: Activity,
        title: 'Simula un partido punto a punto',
        steps: [
            'Selecciona los dos jugadores y la superficie',
            'Elige el modo de timeline (juegos o puntos)',
            'Ajusta la semilla para reproducibilidad',
            'Pulsa "Simular partido" y mira el resultado',
        ],
        hint: 'Activa "Puntos (detallado)" para ver el gráfico de momentum',
    },
    tournament: {
        icon: Trophy,
        title: 'Simula un torneo de eliminación directa',
        steps: [
            'Elige el tamaño: 8 o 16 jugadores',
            'Busca y añade jugadores (admite repetición si quieres)',
            'Selecciona la superficie y tipo de seeding',
            'Pulsa "Simular torneo" para ver el bracket completo',
        ],
        hint: 'El modo "Seeding por ELO" sitúa al mejor jugador en cabeza de serie',
    },
};

export function EmptyState({ mode }: EmptyStateProps) {
    const c = CONTENT[mode];
    const Icon = c.icon;
    return (
        <div className="empty-state">
            <div className="empty-state-icon">
                <Icon size={36} strokeWidth={1.8} aria-hidden="true" />
            </div>
            <h3 className="empty-state-title">{c.title}</h3>
            <ol className="empty-state-steps">
                {c.steps.map((step, i) => (
                    <li key={i} className="empty-state-step">
                        <span className="step-num">{i + 1}</span>
                        <span>{step}</span>
                    </li>
                ))}
            </ol>
            <div className="empty-state-hint">
                <Lightbulb size={14} strokeWidth={2} aria-hidden="true" />
                <span className="hint-label">Sugerencia:</span> {c.hint}
            </div>
        </div>
    );
}
