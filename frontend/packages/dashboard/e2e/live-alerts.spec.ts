import "dotenv/config";
import { test, expect, type APIRequestContext } from "@playwright/test";
import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AUTH_BASE_URL =
  process.env.VITE_AUTH_BASE_URL ?? "http://127.0.0.1:8005";

async function loginToPlatform(request: APIRequestContext) {
  const username = process.env.E2E_USERNAME ?? "ceo@company.com";
  const password = process.env.E2E_PASSWORD;

  if (!password) {
    throw new Error(
      "Set E2E_PASSWORD (the seeded CEO_PASSWORD) for real mode.",
    );
  }

  const response = await request.post(
    `${AUTH_BASE_URL}/api/v1/auth/login`,
    {
      form: { username, password },
    },
  );

  expect(
    response.ok(),
    `Platform login failed: ${response.status()}`,
  ).toBe(true);

  const body = await response.json();

  return {
    accessToken: body.access_token as string,
    refreshToken: body.refresh_token as string,
  };
}

const repoRoot = resolve(
  fileURLToPath(new URL("../../../../", import.meta.url)),
);

const useRealBackend = process.env.ALERTS_E2E_MODE === "real";

function mockToken(): string {
  const payload = Buffer.from(
    JSON.stringify({
      role: "ceo",
      exp: Math.floor(Date.now() / 1000) + 3600,
    }),
  ).toString("base64url");

  return `test.${payload}.signature`;
}

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

test("shows the K3 anomaly alert within 10 seconds", async ({ page, request }) => {
  const tokens = useRealBackend
    ? await loginToPlatform(request)
    : {
        accessToken: mockToken(), 
        refreshToken: "mock-refresh-token",
      };
 
  const configuredWsUrl =
    process.env.VITE_ALERTS_WS_URL ??
    (useRealBackend
      ? "ws://localhost:8000/api/v1/analytics/kpis/real-time"
      : "ws://localhost:8080");

  const expectedWsUrl = new URL(configuredWsUrl);


  // Seed authentication and monitor the actual application WebSocket.
  await page.addInitScript(
    ({ accessToken, refreshToken, gatewayPath }) => {
      sessionStorage.setItem(
        "dashboard_auth",
        JSON.stringify({
          access_token: accessToken,
          refresh_token: refreshToken,
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
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
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


  const initialAlertCount = await alert.count();
  const output: string[] = [];

  const demo = spawn("make", ["demo-anomaly",`PYTHON="${process.env.PYTHON ?? "python"}"`], {
      cwd: repoRoot,
      shell: process.platform === "win32",
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
  });

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