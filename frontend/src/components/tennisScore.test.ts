import { describe, expect, it } from 'vitest';
import { formatTennisScore, isCompletedGame } from './tennisScore';

describe('tennis point scoring', () => {
    it('formats a regular game using tennis labels', () => {
        expect(formatTennisScore(0, 0, false)).toMatchObject({ server: '0', returner: '0' });
        expect(formatTennisScore(3, 2, false)).toMatchObject({ server: '40', returner: '30' });
        expect(formatTennisScore(3, 3, false).status).toBe('Iguales');
        expect(formatTennisScore(4, 3, false)).toMatchObject({ server: 'AD', returner: '40' });
    });

    it('requires four points and a two-point margin in regular games', () => {
        expect(isCompletedGame(4, 3, false)).toBe(false);
        expect(isCompletedGame(5, 3, false)).toBe(true);
        expect(formatTennisScore(5, 3, false).server).toBe('JUEGO');
    });

    it('uses numeric scoring and a two-point margin in tie-breaks', () => {
        expect(formatTennisScore(6, 6, true)).toMatchObject({ server: '6', returner: '6', completed: false });
        expect(isCompletedGame(7, 6, true)).toBe(false);
        expect(isCompletedGame(8, 6, true)).toBe(true);
        expect(formatTennisScore(8, 6, true).status).toBe('Tie-break completado');
    });
});
