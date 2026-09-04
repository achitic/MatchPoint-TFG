export const PROCESS_STEPS = [
    {
        eyebrow: 'Predicción',
        title: 'Estima la probabilidad de victoria',
        description: 'Los datos históricos y el modelo calibrado comparan el rendimiento de ambos jugadores antes del partido.',
    },
    {
        eyebrow: 'Simulación',
        title: 'Reproduce el partido punto a punto',
        description: 'La predicción alimenta un motor sintético que recorre juegos, sets y momentos de presión.',
    },
    {
        eyebrow: 'Visualización',
        title: 'Explica una jugada plausible',
        description: 'La pista representa la simulación generada por el modelo. No utiliza tracking real de pelota ni jugadores.',
    },
] as const;

export const LANDING_FEATURES = [
    {
        number: '01',
        title: 'Predice y explica',
        description: 'Compara jugadores y descubre qué variables influyen en el resultado: ELO, superficie, saque y rendimiento reciente.',
    },
    {
        number: '02',
        title: 'Simula el partido',
        description: 'Reproduce el encuentro punto a punto y observa cómo cambia la ventaja durante una simulación sintética.',
    },
    {
        number: '03',
        title: 'Analiza rivales',
        description: 'Consulta el historial H2H, perfiles de scouting y estadísticas históricas de saque y resto.',
    },
    {
        number: '04',
        title: 'Simula torneos',
        description: 'Explora cuadros completos y usa Monte Carlo para estimar probabilidades de avance y victoria.',
    },
] as const;

export const PREVIEW_PLAYERS = [
    { label: 'Jugador A', name: 'C. Alcaraz', ranking: 'ATP #3', probability: 42 },
    { label: 'Jugador B', name: 'J. Sinner', ranking: 'ATP #1', probability: 58 },
] as const;
