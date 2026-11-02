import "dotenv/config";
import { test, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(
  fileURLToPath(new URL("../../../../", import.meta.url)),
);

const anomalyDir = resolve(
  repoRoot,
  "ml-services",
  "anomaly-detection",
);

const runLiveAlerts = process.env.RUN_LIVE_ALERTS_E2E === "true";
const useRealBackend = process.env.ALERTS_E2E_MODE === "real";

const ALERT_TIMEOUT_MS = 10_000;
const DEMO_EXIT_TIMEOUT_MS = 30_000;
const CLEANUP_TIMEOUT_MS = 5_000;

function waitForProcessExit(
  child: ChildProcess,
  timeoutMs: number,
): Promise<number> {
  return new Promise((resolveExit, reject) => {
    const timer = setTimeout(() => {
      reject(
        new Error(
          `K3 demo anomaly did not exit within ${timeoutMs} ms.`,
        ),
      );
    }, timeoutMs);

    child.once("error", (error: Error) => {
      clearTimeout(timer);
      reject(error);
    });

    child.once("close", (code: number | null) => {
      clearTimeout(timer);
      resolveExit(code ?? 1);
    });
  });
}

async function stopProcess(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) {
    return;
  }

  await new Promise<void>((resolveStop) => {
    const timer = setTimeout(() => {
      resolveStop();
    }, CLEANUP_TIMEOUT_MS);

    child.once("close", () => {
      clearTimeout(timer);
      resolveStop();
    });

    child.kill();
  });
}

test("shows the K3 anomaly alert within 10 seconds", async ({ page }) => {
  test.skip(
    !runLiveAlerts,
    "Set RUN_LIVE_ALERTS_E2E=true to run the alert test.",
  );

  const accessToken = process.env.E2E_ACCESS_TOKEN;
  const refreshToken = process.env.E2E_REFRESH_TOKEN;

  if (useRealBackend && (!accessToken || !refreshToken)) {
    throw new Error(
      "Real mode requires E2E_ACCESS_TOKEN and E2E_REFRESH_TOKEN from a successful platform login.",
    );
  }

  const configuredWsUrl =
    process.env.VITE_ALERTS_WS_URL ??
    (useRealBackend
      ? "ws://localhost:8000/api/v1/analytics/kpis/real-time"
      : "ws://localhost:8080");

  const expectedWsUrl = new URL(configuredWsUrl);

  const token = useRealBackend
    ? accessToken!
    : (() => {
        const payload = Buffer.from(
          JSON.stringify({
            role: "ceo",
            exp: Math.floor(Date.now() / 1000) + 3600,
          }),
        ).toString("base64url");

        return `test.${payload}.signature`;
      })();

  // Seed authentication and monitor the actual application WebSocket.
  await page.addInitScript(
    ({ token: sessionToken, refreshToken: sessionRefreshToken, gatewayPath }) => {
      sessionStorage.setItem(
        "dashboard_auth",
        JSON.stringify({
          access_token: sessionToken,
          refresh_token: sessionRefreshToken,
          token_type: "bearer",
          role: "ceo",
        }),
      );

      const NativeWebSocket = window.WebSocket;

      class MonitoredWebSocket extends NativeWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          super(url, protocols);

          const parsedUrl = new URL(String(url));

          if (parsedUrl.pathname === gatewayPath) {
            sessionStorage.setItem(
              "c3_gateway_ws_state",
              "connecting",
            );

            this.addEventListener("open", () => {
              sessionStorage.setItem(
                "c3_gateway_ws_state",
                "open",
              );
            });

            this.addEventListener("error", () => {
              sessionStorage.setItem(
                "c3_gateway_ws_state",
                "error",
              );
            });

            this.addEventListener("close", (event) => {
              sessionStorage.setItem(
                "c3_gateway_ws_state",
                `closed:${event.code}`,
              );
            });
          }
        }
      }

      window.WebSocket = MonitoredWebSocket;
    },
    {
      token,
      refreshToken: useRealBackend
        ? refreshToken!
        : "mock-refresh-token",
      gatewayPath: expectedWsUrl.pathname,
    },
  );

  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Executive Dashboard" }),
  ).toBeVisible({ timeout: 15_000 });

  const alert = page.getByText(/Cold-Chain Anomaly/);

  // Mock mode checks the mock event without starting the Python demo.
  if (!useRealBackend) {
    await expect(alert.first()).toBeVisible({
      timeout: ALERT_TIMEOUT_MS,
    });
    return;
  }

  // Wait for the actual gateway WebSocket open event.
  await expect
    .poll(
      () =>
        page.evaluate(() =>
          sessionStorage.getItem("c3_gateway_ws_state"),
        ),
      { timeout: ALERT_TIMEOUT_MS },
    )
    .toBe("open");

  const python =
    process.platform === "win32"
      ? resolve(anomalyDir, ".venv", "Scripts", "python.exe")
      : resolve(anomalyDir, ".venv", "bin", "python");

  const initialAlertCount = await alert.count();
  const output: string[] = [];

  const demo = spawn(
    python,
    ["-m", "src.demo_anomaly"],
    {
      cwd: anomalyDir,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  demo.stdout?.setEncoding("utf8");
  demo.stderr?.setEncoding("utf8");

  demo.stdout?.on("data", (chunk: string) => output.push(chunk));
  demo.stderr?.on("data", (chunk: string) => output.push(chunk));

  const alertPromise = expect(alert).toHaveCount(
    initialAlertCount + 1,
    { timeout: ALERT_TIMEOUT_MS },
  );

  const demoExit = waitForProcessExit(
    demo,
    DEMO_EXIT_TIMEOUT_MS,
  );

  try {
    await alertPromise;

    const exitCode = await demoExit;

    expect(
      exitCode,
      `K3 demo failed. Output:\n${output.join("")}`,
    ).toBe(0);
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : String(error);

    console.error(message);
    console.error("K3 demo output:\n", output.join(""));

    throw error;
  } finally {
    await stopProcess(demo);
  }
});