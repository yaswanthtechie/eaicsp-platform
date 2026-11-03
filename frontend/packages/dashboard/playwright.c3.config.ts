import "dotenv/config";
import { defineConfig, devices } from "@playwright/test";

// The live-alerts suite runs against the real stack unless told otherwise.
process.env.ALERTS_E2E_MODE ??= "real";
const useRealBackend = process.env.ALERTS_E2E_MODE === "real";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "live-alerts.spec.ts",
  timeout: 90_000,
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
      VITE_USE_MOCK_AUTH: "false",
      VITE_AUTH_BASE_URL:
        process.env.VITE_AUTH_BASE_URL ?? "http://127.0.0.1:8005",
      VITE_USE_MOCK_WS: useRealBackend ? "false" : "true",
      VITE_ALERTS_WS_URL: useRealBackend
        ? (process.env.VITE_ALERTS_WS_URL ??
          "ws://localhost:8000/api/v1/analytics/kpis/real-time")
        : "ws://localhost:8080",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
