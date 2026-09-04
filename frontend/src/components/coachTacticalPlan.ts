import type { ScoutingCompareStats, TacticalInsight } from '../api/client';
import type { BoostParams } from './coachProbability';

export interface TacticalPlanReason {
    weakness: string;
    action: string;
    adjustments: string[];
}

export interface TacticalPlanPayload {
    playerA: string;
    playerB: string;
    surface: string;
    boosts: BoostParams;
    reasons: TacticalPlanReason[];
}

const NEUTRAL_BOOSTS: BoostParams = {
    first_serve_boost: 0,
    ace_boost: 0,
    bp_resilience_boost: 0,
    fatigue_factor: 0,
    surface_adaptation: 0,
};

const BOOST_LIMITS: Record<keyof BoostParams, number> = {
    first_serve_boost: 0.20,
    ace_boost: 0.15,
    bp_resilience_boost: 0.20,
    fatigue_factor: 0.10,
    surface_adaptation: 0.15,
};

type Adjustment = Partial<BoostParams>;

function severityFactor(severity: TacticalInsight['severity']): number {
    if (severity === 'high') return 1;
    if (severity === 'medium') return 0.8;
    return 0.6;
}

function describeAdjustment(key: keyof BoostParams, value: number): string {
    const labels: Record<keyof BoostParams, string> = {
        first_serve_boost: 'Primer servicio',
        ace_boost: 'Potencia de saque',
        bp_resilience_boost: 'Resiliencia mental',
        fatigue_factor: 'Forma física',
        surface_adaptation: 'Adaptación táctica',
    };
    return `${labels[key]} +${Math.round(value * 100)}%`;
}

function ruleFor(insight: TacticalInsight): { action: string; adjustment: Adjustment } {
    const title = insight.title.toLowerCase();

    if (title.includes('dobles faltas')) {
        return {
            action: 'Adelantar la posición de resto y presionar especialmente el segundo servicio.',
            adjustment: { bp_resilience_boost: 0.04, surface_adaptation: 0.05 },
        };
    }
    if (title.includes('primer servicio')) {
        return {
            action: 'Buscar segundos saques, tomar pronto la iniciativa y jugar la primera bola con profundidad.',
            adjustment: { ace_boost: 0.04, surface_adaptation: 0.05 },
        };
    }
    if (title.includes('pocos aces') || title.includes('sin mucho poder') || title.includes('potencia de saque')) {
        return {
            action: 'Restar desde una posición más ofensiva y atacar la primera bola disponible.',
            adjustment: { surface_adaptation: 0.05 },
        };
    }
    if (title.includes('break point') || insight.category === 'mental') {
        return {
            action: 'Construir puntos con margen en situaciones de presión y obligar al rival a jugar una bola adicional.',
            adjustment: { bp_resilience_boost: 0.08 },
        };
    }
    if (title.includes('juego de resto') || insight.category === 'return') {
        return {
            action: 'Proteger los juegos de saque con un alto porcentaje de primeros y una primera bola agresiva.',
            adjustment: { first_serve_boost: 0.08, ace_boost: 0.04 },
        };
    }
    if (insight.category === 'surface') {
        return {
            action: 'Usar patrones propios de la superficie y mover al rival fuera de sus zonas cómodas.',
            adjustment: { surface_adaptation: 0.10 },
        };
    }
    if (insight.category === 'consistency') {
        return {
            action: 'Priorizar regularidad, profundidad y selección de golpe antes que riesgo innecesario.',
            adjustment: { bp_resilience_boost: 0.05, fatigue_factor: 0.03 },
        };
    }

    return {
        action: 'Aumentar la disciplina táctica y mantener patrones de juego consistentes.',
        adjustment: { bp_resilience_boost: 0.03 },
    };
}

interface OpportunityCandidate {
    score: number;
    insight: TacticalInsight;
}

function opportunity(
    score: number,
    category: TacticalInsight['category'],
    title: string,
    description: string,
    metricValue: number | null,
    metricLabel: string,
): OpportunityCandidate {
    return {
        score,
        insight: {
            type: 'weakness',
            category,
            severity: 'low',
            title: `Área relativa: ${title}`,
            description,
            metric_value: metricValue,
            metric_label: metricLabel,
        },
    };
}

export function buildFallbackOpportunities(stats: ScoutingCompareStats): TacticalInsight[] {
    const candidates: OpportunityCandidate[] = [];
    const addPct = (
        value: number | null,
        score: number,
        category: TacticalInsight['category'],
        title: string,
        metricLabel: string,
    ) => {
        if (value === null) return;
        candidates.push(opportunity(
            score,
            category,
            title,
            `No alcanza el umbral de debilidad significativa, pero es una de las áreas menos dominantes del perfil de ${stats.player}.`,
            Math.round(value * 1000) / 10,
            metricLabel,
        ));
    };

    if (stats.first_serve_pct !== null) addPct(stats.first_serve_pct, (0.66 - stats.first_serve_pct) / 0.12, 'serve', 'primer servicio', '% 1er Servicio');
    if (stats.ace_rate !== null) addPct(stats.ace_rate, (0.08 - stats.ace_rate) / 0.08, 'serve', 'potencia de saque', '% Aces');
    if (stats.double_fault_rate !== null) addPct(stats.double_fault_rate, (stats.double_fault_rate - 0.025) / 0.05, 'serve', 'dobles faltas', '% Dobles Faltas');
    if (stats.bp_saved_pct !== null) addPct(stats.bp_saved_pct, (0.66 - stats.bp_saved_pct) / 0.16, 'mental', 'break points', '% BP Salvados');
    if (stats.return_points_won_pct !== null) addPct(stats.return_points_won_pct, (0.40 - stats.return_points_won_pct) / 0.12, 'return', 'juego de resto', '% Puntos Resto');
    if (stats.win_rate_surface !== null) addPct(stats.win_rate_surface, (0.65 - stats.win_rate_surface) / 0.25, 'consistency', `regularidad en ${stats.surface}`, '% Victorias');

    if (stats.elo_global !== null && stats.elo_surface !== null) {
        const gap = stats.elo_global - stats.elo_surface;
        candidates.push(opportunity(
            gap / 150,
            'surface',
            `adaptación a ${stats.surface}`,
            `No existe una desventaja significativa, pero la adaptación específica a ${stats.surface} ofrece margen táctico relativo.`,
            Math.round(gap),
            'Diferencia ELO global-superficie',
        ));
    }

    return candidates
        .sort((a, b) => b.score - a.score)
        .slice(0, 2)
        .map(candidate => candidate.insight);
}

export function buildTacticalPlan(
    playerA: string,
    playerB: string,
    surface: string,
    weaknesses: TacticalInsight[],
): TacticalPlanPayload {
    const boosts = { ...NEUTRAL_BOOSTS };
    const reasons = weaknesses.map((insight) => {
        const rule = ruleFor(insight);
        const factor = severityFactor(insight.severity);
        const scaledEntries = Object.entries(rule.adjustment).map(([rawKey, rawValue]) => {
            const key = rawKey as keyof BoostParams;
            const value = Number(rawValue) * factor;
            boosts[key] = Math.min(BOOST_LIMITS[key], boosts[key] + value);
            return describeAdjustment(key, value);
        });

        return {
            weakness: insight.title,
            action: rule.action,
            adjustments: scaledEntries,
        };
    });

    return { playerA, playerB, surface, boosts, reasons };
}
