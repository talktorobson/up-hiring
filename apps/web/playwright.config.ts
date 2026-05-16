import { defineConfig, devices } from "@playwright/test";

/**
 * Sprint 4 #89: 1 happy-path em chromium desktop. A stack (DB+API+web) sobe
 * fora do Playwright (docker compose no CI / `make dev` local) — ver RUNBOOK.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
