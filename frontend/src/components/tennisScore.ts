export type PointWinner = 'server' | 'returner';

export interface DisplayScore {
    server: string;
    returner: string;
    status: string;
    completed: boolean;
}

export function isCompletedGame(serverPoints: number, returnerPoints: number, isTiebreak: boolean): boolean {
    const minimum = isTiebreak ? 7 : 4;
    return Math.max(serverPoints, returnerPoints) >= minimum
        && Math.abs(serverPoints - returnerPoints) >= 2;
}

export function formatTennisScore(serverPoints: number, returnerPoints: number, isTiebreak: boolean): DisplayScore {
    const completed = isCompletedGame(serverPoints, returnerPoints, isTiebreak);

    if (isTiebreak) {
        return {
            server: String(serverPoints),
            returner: String(returnerPoints),
            status: completed ? 'Tie-break completado' : 'Tie-break · primero a 7 con dos de diferencia',
            completed,
        };
    }

    if (completed) {
        return {
            server: serverPoints > returnerPoints ? 'JUEGO' : '—',
            returner: returnerPoints > serverPoints ? 'JUEGO' : '—',
            status: 'Juego completado',
            completed,
        };
    }

    if (serverPoints >= 3 && returnerPoints >= 3) {
        if (serverPoints === returnerPoints) {
            return { server: '40', returner: '40', status: 'Iguales', completed: false };
        }
        if (serverPoints > returnerPoints) {
            return { server: 'AD', returner: '40', status: 'Ventaja servidor', completed: false };
        }
        return { server: '40', returner: 'AD', status: 'Ventaja restador', completed: false };
    }

    const labels = ['0', '15', '30', '40'];
    return {
        server: labels[Math.min(serverPoints, 3)],
        returner: labels[Math.min(returnerPoints, 3)],
        status: 'Juego normal',
        completed: false,
    };
}

