import { defineConfig, devices } from '@playwright/test';

const pythonExecutable = process.env.MATCHPOINT_PYTHON ?? 'python';

export default defineConfig({
    testDir: './e2e',
    fullyParallel: false,
    timeout: 120_000,
    expect: { timeout: 15_000 },
    reporter: 'list',
    use: {
        baseURL: 'http://127.0.0.1:5173',
        trace: 'retain-on-failure',
    },
    projects: [
        {
            name: 'desktop-chrome',
            use: { ...devices['Desktop Chrome'], channel: 'chrome' },
        },
    ],
    webServer: [
        {
            command: `"${pythonExecutable}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`,
            cwd: '..',
            url: 'http://127.0.0.1:8000/health',
            timeout: 180_000,
            reuseExistingServer: !process.env.CI,
        },
        {
            command: 'npm run dev -- --host 127.0.0.1',
            url: 'http://127.0.0.1:5173',
            timeout: 60_000,
            reuseExistingServer: !process.env.CI,
        },
    ],
});
