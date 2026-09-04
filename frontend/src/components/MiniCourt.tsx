interface MiniCourtProps {
    server: 'A' | 'B';
    pointWinnerIsServer: boolean;
}

export function MiniCourt({ server, pointWinnerIsServer }: MiniCourtProps) {
    return (
        <div className="court-mini" aria-hidden="true">
            <div className={`court-player court-player-a ${server === 'A' ? 'serving' : ''}`} />
            <div className={`court-player court-player-b ${server === 'B' ? 'serving' : ''}`} />
            <div className={`court-ball ${pointWinnerIsServer ? 'server-win' : 'returner-win'}`} />
        </div>
    );
}
