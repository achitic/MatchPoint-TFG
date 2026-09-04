// frontend/src/components/ConfidenceGauge.tsx
import { motion } from 'framer-motion';
import { useAnimatedValue } from './useAnimatedValue';

/* ------------------------------------------------------------------ */
/*  Semicircular SVG gauge that visualises prediction confidence       */
/*  Receives the winner's probability (0-1) and renders a colored     */
/*  arc from 0° to 180° proportional to the confidence level.         */
/* ------------------------------------------------------------------ */

interface ConfidenceGaugeProps {
  /** Winner's probability, 0–1 */
  probability: number;
  /** Delay before the arc starts animating (seconds) */
  delay?: number;
}

/* ── Confidence tiers ── */
function getTier(p: number): {
  label: string;
  description: string;
  color: string;
  glowColor: string;
} {
  if (p >= 0.80) return {
    label: 'Muy alta confianza',
    description: 'El modelo esta muy seguro de este resultado',
    color: '#22d3ee',       // cyan — primary
    glowColor: 'rgba(34, 211, 238, 0.25)',
  };
  if (p >= 0.70) return {
    label: 'Alta confianza',
    description: 'El modelo tiene buena certeza sobre el resultado',
    color: '#34d399',       // emerald — secondary
    glowColor: 'rgba(52, 211, 153, 0.25)',
  };
  if (p >= 0.60) return {
    label: 'Confianza moderada',
    description: 'El favorito tiene ventaja, pero no es definitiva',
    color: '#fbbf24',       // amber — warning
    glowColor: 'rgba(251, 191, 36, 0.25)',
  };
  if (p >= 0.55) return {
    label: 'Partido equilibrado',
    description: 'Diferencia minima entre ambos jugadores',
    color: '#fb923c',       // orange
    glowColor: 'rgba(251, 146, 60, 0.25)',
  };
  return {
    label: 'Resultado impredecible',
    description: 'Practicamente un 50/50 — cualquiera puede ganar',
    color: '#f87171',       // red — error
    glowColor: 'rgba(248, 113, 113, 0.25)',
  };
}

/* ── SVG arc path helper ── */
function describeArc(
  cx: number, cy: number, radius: number,
  startAngle: number, endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? '0' : '1';
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

function polarToCartesian(
  cx: number, cy: number, radius: number, angleDeg: number,
): { x: number; y: number } {
  const rad = ((angleDeg - 180) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad),
  };
}

export function ConfidenceGauge({ probability, delay = 0.6 }: ConfidenceGaugeProps) {
  const tier = getTier(probability);

  // Map probability to arc sweep: 0.5 = 0°, 1.0 = 180°
  // Clamp to [0.5, 1.0] since we always show the winner's probability
  const clamped = Math.max(0.5, Math.min(1.0, probability));
  const sweepDegrees = ((clamped - 0.5) / 0.5) * 180;

  // SVG dimensions
  const W = 200;
  const H = 115;
  const CX = W / 2;
  const CY = 100;
  const R = 80;
  const STROKE = 8;

  // Paths
  const bgArc = describeArc(CX, CY, R, 0, 180);
  const fgArc = sweepDegrees > 0.5 ? describeArc(CX, CY, R, 0, sweepDegrees) : '';

  // Animated display value
  const displayPct = useAnimatedValue(probability * 100, 900, 1);

  return (
    <motion.div
      className="confidence-gauge"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay: delay * 0.5, ease: 'easeOut' }}
    >
      <div className="gauge-svg-wrapper">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          className="gauge-svg"
        >
          {/* Glow filter */}
          <defs>
            <filter id="gauge-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background arc */}
          <path
            d={bgArc}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={STROKE}
            strokeLinecap="round"
          />

          {/* Animated foreground arc */}
          {fgArc && (
            <motion.path
              d={fgArc}
              fill="none"
              stroke={tier.color}
              strokeWidth={STROKE}
              strokeLinecap="round"
              filter="url(#gauge-glow)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 1.2, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
            />
          )}

          {/* Center percentage */}
          <text
            x={CX}
            y={CY - 20}
            textAnchor="middle"
            className="gauge-pct-text"
            fill={tier.color}
          >
            {displayPct}%
          </text>
        </svg>
      </div>

      {/* Label + description */}
      <div className="gauge-info">
        <span className="gauge-label" style={{ color: tier.color }}>
          {tier.label}
        </span>
        <span className="gauge-description">
          {tier.description}
        </span>
      </div>
    </motion.div>
  );
}
