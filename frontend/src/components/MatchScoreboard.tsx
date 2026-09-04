interface MatchScoreboardProps {
    playerA: string;
    playerB: string;
    setsA: number;
    setsB: number;
    gamesA: number;
    gamesB: number;
    setIndex: number;
    totalSets: number;
}

export function MatchScoreboard({
    playerA,
    playerB,
    setsA,
    setsB,
    gamesA,
    gamesB,
    setIndex,
    totalSets,
}: MatchScoreboardProps) {
    return (
        <div className="scoreboard">
            <div className="scoreboard-header">
                <span className="sb-label"></span>
                <span className="sb-label sb-sets">Sets</span>
                <span className="sb-label sb-games">Games</span>
            </div>
            <div className="scoreboard-row player-a-row">
                <span className="sb-player">{playerA}</span>
                <span className="sb-sets-value">{setsA}</span>
                <span className="sb-games-value">{gamesA}</span>
            </div>
            <div className="scoreboard-row player-b-row">
                <span className="sb-player">{playerB}</span>
                <span className="sb-sets-value">{setsB}</span>
                <span className="sb-games-value">{gamesB}</span>
            </div>
            <div className="scoreboard-set-indicator">
                Set {setIndex + 1} de {totalSets}
            </div>
        </div>
    );
}
