import { describe, expect, it } from 'vitest';
import { applyBoosts, clampProbabilityOverride } from './coachProbability';
import type { BoostParams } from './coachProbability';

const neutral: BoostParams = {
    first_serve_boost: 0,
    ace_boost: 0,
    bp_resilience_boost: 0,
    fatigue_factor: 0,
    surface_adaptation: 0,
};

describe('coach probability adjustments', () => {
    it('preserves a neutral base probability', () => {
        expect(applyBoosts(0.62, neutral)).toBeCloseTo(0.62, 10);
    });

    it('moves probability in the expected direction', () => {
        const positive = { ...neutral, first_serve_boost: 0.2 };
        const negative = { ...neutral, fatigue_factor: -0.25 };
        expect(applyBoosts(0.5, positive)).toBeGreaterThan(0.5);
        expect(applyBoosts(0.5, negative)).toBeLessThan(0.5);
    });

    it('clamps every override to the backend operational range', () => {
        expect(clampProbabilityOverride(-5)).toBe(0.01);
        expect(clampProbabilityOverride(5)).toBe(0.99);
        expect(applyBoosts(0, neutral)).toBe(0.01);
        expect(applyBoosts(1, neutral)).toBe(0.99);
    });
});
