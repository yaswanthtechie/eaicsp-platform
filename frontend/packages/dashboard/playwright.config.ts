import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "dashboard.auth.spec.ts",
  use: {
    baseURL: "http://localhost:4173",
    headless: true,
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      VITE_AUTH_BASE_URL: "http://127.0.0.1:8005",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

