// frontend/src/components/TournamentBracket.tsx
import type { TournamentResponse, TournamentMatch } from '../api/client';
import { Trophy } from 'lucide-react';

interface TournamentBracketProps {
    result: TournamentResponse;
}

// Layout constants
const MATCH_W = 180;
const MATCH_H = 72;
const COL_GAP = 60;
const ROW_GAP = 16;

interface LayoutMatch {
    match: TournamentMatch;
    x: number;
    y: number;
    roundIdx: number;
    matchIdx: number;
}

function buildLayout(result: TournamentResponse): {
    items: LayoutMatch[];
    svgWidth: number;
    svgHeight: number;
} {
    const rounds = result.rounds;
    const numRounds = rounds.length;
    const svgWidth = numRounds * (MATCH_W + COL_GAP) + 8;

    const items: LayoutMatch[] = [];

    // For each round, distribute matches evenly in the vertical space
    // The first round has the most matches; each subsequent round has half.
    const firstRoundCount = rounds[0]?.matches.length ?? 1;
    const totalHeight = firstRoundCount * (MATCH_H + ROW_GAP) - ROW_GAP;
    const svgHeight = totalHeight + 40; // padding top/bottom

    for (let ri = 0; ri < rounds.length; ri++) {
        const round = rounds[ri];
        const matchCount = round.matches.length;
        const slotH = totalHeight / matchCount;
        const x = 8 + ri * (MATCH_W + COL_GAP);

        for (let mi = 0; mi < matchCount; mi++) {
            // Center each match within its slot
            const y = 20 + mi * slotH + (slotH - MATCH_H) / 2;
            items.push({
                match: round.matches[mi],
                x,
                y,
                roundIdx: ri,
                matchIdx: mi,
            });
        }
    }

    return { items, svgWidth, svgHeight };
}

export function TournamentBracket({ result }: TournamentBracketProps) {
    const { items, svgWidth, svgHeight } = buildLayout(result);

    // Group items by round for connector lines
    const byRound: LayoutMatch[][] = [];
    for (const item of items) {
        if (!byRound[item.roundIdx]) byRound[item.roundIdx] = [];
        byRound[item.roundIdx].push(item);
    }

    // Build connector lines: for each match in round R+1, connect from
    // the two matches in round R that feed into it.
    const connectors: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (let ri = 0; ri < byRound.length - 1; ri++) {
        const currRound = byRound[ri];
        const nextRound = byRound[ri + 1];
        for (let ni = 0; ni < nextRound.length; ni++) {
            const nextMatch = nextRound[ni];
            // Each next match gets the winners of matches 2*ni and 2*ni+1
            const srcA = currRound[ni * 2];
            const srcB = currRound[ni * 2 + 1];
            if (!srcA || !srcB) continue;

            const srcMidY = (srcA.y + MATCH_H / 2 + srcB.y + MATCH_H / 2) / 2;
            const srcRightX = srcA.x + MATCH_W;
            const dstLeftX = nextMatch.x;
            const dstMidY = nextMatch.y + MATCH_H / 2;
            const midX = (srcRightX + dstLeftX) / 2;

            // Horizontal from source right, vertical to center, horizontal to dest
            connectors.push({ x1: srcA.x + MATCH_W, y1: srcA.y + MATCH_H / 2, x2: midX, y2: srcA.y + MATCH_H / 2 });
            connectors.push({ x1: srcB.x + MATCH_W, y1: srcB.y + MATCH_H / 2, x2: midX, y2: srcB.y + MATCH_H / 2 });
            connectors.push({ x1: midX, y1: srcA.y + MATCH_H / 2, x2: midX, y2: srcMidY });
            connectors.push({ x1: midX, y1: srcMidY, x2: dstLeftX, y2: dstMidY });
        }
    }

    return (
        <div className="tournament-bracket">
            {/* Round headers */}
            <div
                className="bracket-headers"
                style={{ gridTemplateColumns: `repeat(${result.rounds.length}, ${MATCH_W}px)`, gap: `${COL_GAP}px` }}
            >
                {result.rounds.map((r) => (
                    <div key={r.round} className="bracket-round-header">{r.name}</div>
                ))}
            </div>

            {/* SVG bracket */}
            <div className="bracket-svg-container">
                <svg
                    viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                    width={svgWidth}
                    height={svgHeight}
                    className="bracket-svg"
                    role="img"
                    aria-label="Cuadro de eliminación directa"
                >
                    {/* Connector lines */}
                    {connectors.map((c, i) => (
                        <line
                            key={i}
                            x1={c.x1} y1={c.y1} x2={c.x2} y2={c.y2}
                            stroke="rgba(34,211,238,0.3)"
                            strokeWidth="1.5"
                        />
                    ))}

                    {/* Match boxes */}
                    {items.map((item) => {
                        const { match, x, y, roundIdx } = item;
                        const aWins = match.result.winner === 'A';
                        const bWins = !aWins;
                        const isLastRound = roundIdx === result.rounds.length - 1;
                        const winnerName = aWins ? match.player_a : match.player_b;
                        const isChampion = isLastRound && winnerName === result.champion;

                        return (
                            <g key={`${item.roundIdx}-${item.matchIdx}`}>
                                {/* Box background */}
                                <rect
                                    x={x} y={y}
                                    width={MATCH_W} height={MATCH_H}
                                    rx="6" ry="6"
                                    fill={isChampion ? 'rgba(234,179,8,0.12)' : 'rgba(15,23,42,0.85)'}
                                    stroke={isChampion ? 'rgba(234,179,8,0.6)' : 'rgba(34,211,238,0.2)'}
                                    strokeWidth="1"
                                />

                                {/* Player A row */}
                                <g>
                                    <rect
                                        x={x + 1} y={y + 1}
                                        width={MATCH_W - 2} height={MATCH_H / 2 - 1}
                                        rx="5" ry="5"
                                        fill={aWins ? 'rgba(34,211,238,0.1)' : 'transparent'}
                                    />
                                    <text
                                        x={x + 8} y={y + MATCH_H / 4 + 4}
                                        fontSize="11"
                                        fill={aWins ? '#22d3ee' : 'rgba(255,255,255,0.55)'}
                                        fontWeight={aWins ? '600' : '400'}
                                        clipPath={`url(#clip-${item.roundIdx}-${item.matchIdx}-a)`}
                                    >
                                        {aWins ? <Trophy className="inline-champion-icon" size={13} aria-label="Ganador" /> : null}{match.player_a}
                                    </text>
                                    <text
                                        x={x + MATCH_W - 6} y={y + MATCH_H / 4 + 4}
                                        textAnchor="end"
                                        fontSize="10"
                                        fill="rgba(255,255,255,0.4)"
                                    >
                                        {(match.p_a * 100).toFixed(0)}%
                                    </text>
                                </g>

                                {/* Divider */}
                                <line
                                    x1={x + 6} y1={y + MATCH_H / 2}
                                    x2={x + MATCH_W - 6} y2={y + MATCH_H / 2}
                                    stroke="rgba(255,255,255,0.08)"
                                    strokeWidth="0.8"
                                />

                                {/* Player B row */}
                                <g>
                                    <rect
                                        x={x + 1} y={y + MATCH_H / 2}
                                        width={MATCH_W - 2} height={MATCH_H / 2 - 1}
                                        rx="5" ry="5"
                                        fill={bWins ? 'rgba(34,211,238,0.1)' : 'transparent'}
                                    />
                                    <text
                                        x={x + 8} y={y + MATCH_H * 3 / 4 + 4}
                                        fontSize="11"
                                        fill={bWins ? '#22d3ee' : 'rgba(255,255,255,0.55)'}
                                        fontWeight={bWins ? '600' : '400'}
                                    >
                                        {bWins ? <Trophy className="inline-champion-icon" size={13} aria-label="Ganador" /> : null}{match.player_b}
                                    </text>
                                    <text
                                        x={x + MATCH_W - 6} y={y + MATCH_H * 3 / 4 + 4}
                                        textAnchor="end"
                                        fontSize="10"
                                        fill="rgba(255,255,255,0.4)"
                                    >
                                        {(match.p_b * 100).toFixed(0)}%
                                    </text>
                                </g>

                                {/* Score label */}
                                <text
                                    x={x + MATCH_W / 2} y={y + MATCH_H / 2}
                                    textAnchor="middle"
                                    fontSize="9"
                                    fill="rgba(255,255,255,0.3)"
                                    dy="-2"
                                >
                                    {match.result.sets.join(' ')}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>

            {/* Champion banner */}
            <div className="bracket-champion">
                <span className="bracket-champion-icon"><Trophy size={28} aria-hidden="true" /></span>
                <span className="bracket-champion-name">{result.champion}</span>
            </div>
        </div>
    );
}
