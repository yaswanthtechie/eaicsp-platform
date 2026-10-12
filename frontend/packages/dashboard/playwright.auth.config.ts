import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "dashboard.auth.spec.ts",
  retries: 1,

  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    trace: "on-first-retry",
  },

  webServer: {
    command: "npm run dev -- --host localhost --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
        VITE_USE_MOCK_AUTH: "false",
        VITE_AUTH_BASE_URL: "",
    },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});