import { expect, test } from '@playwright/test';

test.describe('Fase 1 — regresiones funcionales', () => {
    test('Entrenador limita un escenario extremo y completa la simulación', async ({ page }) => {
        let submittedOverride: number | undefined;
        page.on('request', (request) => {
            if (request.url().endsWith('/simulate_match') && request.method() === 'POST') {
                submittedOverride = request.postDataJSON().p_a_override;
            }
        });

        await page.goto('/app/coach');

        const playerA = page.getByLabel('Tu jugador (A)');
        await playerA.fill('Novak Djokovic');
        await expect(page.getByRole('option', { name: 'Novak Djokovic', exact: true })).toBeVisible();
        await playerA.press('Enter');

        const playerB = page.getByLabel('Rival (B)');
        await playerB.fill('Aaro Pollanen');
        await expect(page.getByRole('option', { name: 'Aaro Pollanen', exact: true })).toBeVisible();
        await playerB.press('Enter');

        await page.getByRole('button', { name: 'Obtener predicción base' }).click();
        await expect(page.getByText('Ajustado (What-If)')).not.toBeVisible();
        await expect(page.getByText('Base (sin ajustes)')).toBeVisible();

        for (const slider of await page.locator('input[type="range"]').all()) {
            await slider.evaluate((element) => {
                const input = element as HTMLInputElement;
                const valueSetter = Object.getOwnPropertyDescriptor(
                    HTMLInputElement.prototype,
                    'value',
                )?.set;
                valueSetter?.call(input, input.max);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            });
        }

        await expect(page.getByText('Ajustado (What-If)')).toBeVisible();
        await page.getByRole('button', { name: 'Simular partido punto a punto con estos ajustes' }).click();

        await expect.poll(() => submittedOverride).toBeCloseTo(0.99, 8);
        await expect(page.getByTestId('coach-effective-probability')).toContainText('99.0%');
        await expect(page.locator('.coach-error-banner')).toHaveCount(0);
    });

    test('la API no etiqueta un 7-5 como tie-break', async ({ request }) => {
        const response = await request.post('http://127.0.0.1:8000/simulate_match', {
            data: {
                player_a: 'Carlos Alcaraz',
                player_b: 'Jannik Sinner',
                surface: 'Hard',
                as_of: '2024-01-01',
                model: 'calibrated_logreg',
                best_of: 3,
                seed: 3,
                first_server: 'random',
                timeline_mode: 'games',
                engine_mode: 'bayes_live_v1',
                p_a_override: 0.61,
            },
        });

        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        const sevenFiveSets = body.timeline.filter(
            (set: { score: string }) => set.score === '7-5' || set.score === '5-7',
        );

        expect(sevenFiveSets.length).toBeGreaterThan(0);
        for (const set of sevenFiveSets) {
            expect(set.tiebreak).toBe(false);
            expect(set.games.at(-1).type).toBe('game');
        }
    });
});
