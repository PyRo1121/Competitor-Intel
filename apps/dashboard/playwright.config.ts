import { defineConfig, devices } from "@playwright/test";

const apiPort = 3000;
const previewPort = 4173;
const root = new URL("../..", import.meta.url).pathname;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: `http://127.0.0.1:${previewPort}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `bash -c 'cd "${root}" && export CI_DB_PATH="${process.env.CI_DB_PATH ?? root + "/data/ci_test.db"}" && PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/migrate_ci_db.py && uv run python scripts/seed_ci_e2e.py && cd apps/api && bun run start'`,
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `PUBLIC_CI_API_URL=http://127.0.0.1:${apiPort} bun run build && PUBLIC_CI_API_URL=http://127.0.0.1:${apiPort} bun run preview --port ${previewPort} --host 127.0.0.1`,
      url: `http://127.0.0.1:${previewPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
