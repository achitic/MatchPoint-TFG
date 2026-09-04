// frontend/src/components/TacticalRadar.tsx
import { useEffect, useRef } from 'react';

interface TacticalRadarProps {
    statsA: {
        player: string;
        first_serve_pct: number | null;
        ace_rate: number | null;
        double_fault_rate: number | null;
        bp_saved_pct: number | null;
        return_points_won_pct: number | null;
        win_rate_surface: number | null;
        elo_surface: number | null;
    };
    statsB: {
        player: string;
        first_serve_pct: number | null;
        ace_rate: number | null;
        double_fault_rate: number | null;
        bp_saved_pct: number | null;
        return_points_won_pct: number | null;
        win_rate_surface: number | null;
        elo_surface: number | null;
    };
    size?: number;
}

type RadarStats = TacticalRadarProps['statsA'];
type RadarMetricKey = Exclude<keyof RadarStats, 'player'>;

const METRICS: Array<{ key: RadarMetricKey; label: string; max: number; min: number; invert?: boolean }> = [
    { key: 'first_serve_pct', label: '1er Saque', max: 0.85, min: 0.40 },
    { key: 'ace_rate', label: 'Aces', max: 0.20, min: 0.0 },
    { key: 'double_fault_rate', label: 'DF (Invertido)', max: 0.15, min: 0.01, invert: true },
    { key: 'bp_saved_pct', label: 'BP Salvados', max: 0.85, min: 0.35 },
    { key: 'return_points_won_pct', label: 'Resto', max: 0.48, min: 0.25 },
    { key: 'win_rate_surface', label: 'Win Rate', max: 0.88, min: 0.25 },
];

export function TacticalRadar({ statsA, statsB, size = 320 }: TacticalRadarProps) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const sansFont = getComputedStyle(document.documentElement).getPropertyValue('--font-sans').trim()
            || 'system-ui, sans-serif';

        // Support high DPI screens (retina)
        const dpr = window.devicePixelRatio || 1;
        canvas.width = size * dpr;
        canvas.height = size * dpr;
        canvas.style.width = `${size}px`;
        canvas.style.height = `${size}px`;
        ctx.scale(dpr, dpr);

        const center = size / 2;
        const radius = (size / 2) * 0.70;
        const totalAxes = METRICS.length;

        // Clear canvas
        ctx.clearRect(0, 0, size, size);

        // Helper: get value scaled [0, 1]
        const getScaledValue = (val: number | null, min: number, max: number, invert = false) => {
            if (val === null) return 0.5;
            let norm = (val - min) / (max - min);
            norm = Math.max(0, Math.min(1, norm));
            return invert ? 1 - norm : norm;
        };

        // 1. Draw web grid levels
        const levels = 4;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;

        for (let l = 1; l <= levels; l++) {
            const currentRadius = (radius / levels) * l;
            ctx.beginPath();
            for (let i = 0; i < totalAxes; i++) {
                const angle = (i * 2 * Math.PI) / totalAxes - Math.PI / 2;
                const x = center + currentRadius * Math.cos(angle);
                const y = center + currentRadius * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.stroke();

            // Draw grid concentric lines background
            ctx.fillStyle = 'rgba(255, 255, 255, 0.01)';
            ctx.fill();
        }

        // 2. Draw axis lines + labels
        METRICS.forEach((m, i) => {
            const angle = (i * 2 * Math.PI) / totalAxes - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);

            // Axis line
            ctx.beginPath();
            ctx.moveTo(center, center);
            ctx.lineTo(x, y);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.09)';
            ctx.stroke();

            // Label position placement
            const labelDist = radius + 20;
            const lx = center + labelDist * Math.cos(angle);
            const ly = center + labelDist * Math.sin(angle);

            ctx.fillStyle = '#9eadbb';
            ctx.font = `bold 10px ${sansFont}`;
            ctx.textAlign = Math.abs(lx - center) < 10 ? 'center' : lx < center ? 'end' : 'start';
            ctx.textBaseline = Math.abs(ly - center) < 10 ? 'middle' : ly < center ? 'bottom' : 'top';
            ctx.fillText(m.label, lx, ly);
        });

        // 3. Helper to draw player polygon
        const drawPlayerPolygon = (
            stats: RadarStats,
            fillColor: string,
            strokeColor: string,
            shadowColor: string
        ) => {
            ctx.beginPath();
            METRICS.forEach((m, i) => {
                const rawVal = stats[m.key];
                const val = getScaledValue(rawVal, m.min, m.max, m.invert);
                const angle = (i * 2 * Math.PI) / totalAxes - Math.PI / 2;
                const x = center + radius * val * Math.cos(angle);
                const y = center + radius * val * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.closePath();

            // Styling
            ctx.fillStyle = fillColor;
            ctx.fill();

            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = 2.5;
            ctx.shadowBlur = 12;
            ctx.shadowColor = shadowColor;
            ctx.stroke();

            // Reset shadow
            ctx.shadowBlur = 0;

            // Draw small point nodes
            METRICS.forEach((m, i) => {
                const rawVal = stats[m.key];
                const val = getScaledValue(rawVal, m.min, m.max, m.invert);
                const angle = (i * 2 * Math.PI) / totalAxes - Math.PI / 2;
                const x = center + radius * val * Math.cos(angle);
                const y = center + radius * val * Math.sin(angle);

                ctx.beginPath();
                ctx.arc(x, y, 3.5, 0, 2 * Math.PI);
                ctx.fillStyle = strokeColor;
                ctx.fill();
                ctx.strokeStyle = '#07111f';
                ctx.lineWidth = 1;
                ctx.stroke();
            });
        };

        // Draw Player B (technical cyan)
        drawPlayerPolygon(
            statsB,
            'rgba(54, 197, 217, 0.14)',
            '#36c5d9',
            'rgba(54, 197, 217, 0.24)'
        );

        // Draw Player A (tennis green)
        drawPlayerPolygon(
            statsA,
            'rgba(81, 200, 146, 0.14)',
            '#51c892',
            'rgba(81, 200, 146, 0.24)'
        );

    }, [statsA, statsB, size]);

    return (
        <div className="scouting-radar-wrap" style={{ display: 'flex', justifyContent: 'center', margin: '0.75rem 0' }}>
            <canvas
                ref={canvasRef}
                role="img"
                aria-label={`Comparativa táctica entre ${statsA.player} y ${statsB.player}`}
            />
        </div>
    );
}
