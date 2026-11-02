
import "dotenv/config";
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "dashboard.auth.spec.ts",
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev -- --host localhost --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      VITE_AUTH_BASE_URL:
        process.env.VITE_AUTH_BASE_URL ?? "http://127.0.0.1:8005",
      VITE_ALERTS_WS_URL:
        process.env.VITE_ALERTS_WS_URL ??
        "ws://localhost:8000/api/v1/analytics/kpis/real-time",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
