import { afterEach, describe, expect, it, vi } from 'vitest';
import { deleteInplayState, simulateMatch } from './client';
import type { SimulateRequest } from './client';

afterEach(() => vi.unstubAllGlobals());

describe('API client contracts', () => {
    it('forwards the coach probability override to simulation', async () => {
        const payload: SimulateRequest = {
            player_a: 'Carlos Alcaraz',
            player_b: 'Jannik Sinner',
            surface: 'Hard',
            as_of: null,
            model: 'calibrated_logreg',
            best_of: 3,
            seed: 42,
            first_server: 'A',
            timeline_mode: 'none',
            p_a_override: 0.73,
        };
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ result: { winner: 'A' } }),
        });
        vi.stubGlobal('fetch', fetchMock);

        await simulateMatch(payload);

        const [, init] = fetchMock.mock.calls[0];
        expect(JSON.parse(init.body)).toMatchObject({ p_a_override: 0.73 });
    });

    it('uses DELETE and URL-encodes the live match id', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ match_id: 'match/id', deleted: true }),
        });
        vi.stubGlobal('fetch', fetchMock);

        await deleteInplayState('match/id');

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining('/inplay/match%2Fid'),
            { method: 'DELETE' },
        );
    });

    it('surfaces the API error detail', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            statusText: 'Bad Request',
            json: async () => ({ detail: 'invalid completed game score' }),
        }));

        await expect(deleteInplayState('missing')).rejects.toThrow('invalid completed game score');
    });
});
