export interface BoostParams {
    first_serve_boost: number;
    ace_boost: number;
    bp_resilience_boost: number;
    fatigue_factor: number;
    surface_adaptation: number;
}

export const MIN_PROBABILITY_OVERRIDE = 0.01;
export const MAX_PROBABILITY_OVERRIDE = 0.99;

export function clampProbabilityOverride(value: number): number {
    return Math.max(MIN_PROBABILITY_OVERRIDE, Math.min(MAX_PROBABILITY_OVERRIDE, value));
}

export function applyBoosts(baseP: number, boosts: BoostParams): number {
    const clamp = (x: number) => Math.max(1e-6, Math.min(1 - 1e-6, x));
    const logit = (p: number) => Math.log(clamp(p) / (1 - clamp(p)));
    const sigmoid = (z: number) => 1 / (1 + Math.exp(-z));
    const sensitivity = 4.5;
    const totalLogitDelta =
        (boosts.first_serve_boost * sensitivity) +
        (boosts.ace_boost * sensitivity * 0.7) +
        (boosts.bp_resilience_boost * sensitivity * 1.1) +
        (boosts.fatigue_factor * sensitivity * 0.9) +
        (boosts.surface_adaptation * sensitivity * 0.8);

    return clampProbabilityOverride(sigmoid(logit(baseP) + totalLogitDelta));
}
