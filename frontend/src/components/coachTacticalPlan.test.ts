import { describe, expect, it } from 'vitest';
import type { TacticalInsight } from '../api/client';
import { buildFallbackOpportunities, buildTacticalPlan } from './coachTacticalPlan';

function weakness(title: string, category: TacticalInsight['category'], severity: TacticalInsight['severity'] = 'high'): TacticalInsight {
    return {
        type: 'weakness',
        category,
        severity,
        title,
        description: 'Test',
        metric_value: null,
        metric_label: null,
    };
}

describe('scouting to coach tactical plan', () => {
    it('keeps a plan neutral when scouting found no weaknesses', () => {
        const plan = buildTacticalPlan('A', 'B', 'Hard', []);
        expect(plan.reasons).toHaveLength(0);
        expect(Object.values(plan.boosts).every(value => value === 0)).toBe(true);
    });

    it('translates rival return weakness into serve adjustments', () => {
        const plan = buildTacticalPlan('A', 'B', 'Clay', [weakness('Débil en el juego de resto', 'return')]);
        expect(plan.boosts.first_serve_boost).toBeCloseTo(0.08);
        expect(plan.boosts.ace_boost).toBeCloseTo(0.04);
        expect(plan.reasons[0].action).toContain('juegos de saque');
    });

    it('scales by severity and caps accumulated recommendations', () => {
        const insights = Array.from({ length: 5 }, (_, index) =>
            weakness(`Poca adaptación a superficie ${index}`, 'surface', index === 0 ? 'medium' : 'high'),
        );
        const plan = buildTacticalPlan('A', 'B', 'Grass', insights);
        expect(plan.boosts.surface_adaptation).toBe(0.15);
    });

    it('offers two clearly labelled relative opportunities when no threshold was crossed', () => {
        const opportunities = buildFallbackOpportunities({
            player: 'Jugador equilibrado',
            surface: 'Hard',
            first_serve_pct: 0.64,
            ace_rate: 0.05,
            double_fault_rate: 0.035,
            bp_saved_pct: 0.62,
            return_points_won_pct: 0.36,
            matches_counted: 100,
            elo_global: 1800,
            elo_surface: 1760,
            win_rate: 0.62,
            win_rate_surface: 0.58,
        });
        expect(opportunities).toHaveLength(2);
        expect(opportunities.every(item => item.title.startsWith('Área relativa:'))).toBe(true);
        expect(opportunities.every(item => item.severity === 'low')).toBe(true);
    });
});
