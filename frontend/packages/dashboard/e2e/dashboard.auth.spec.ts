/// <reference types="node" />

import { test, expect, type Page } from "@playwright/test";

const username = process.env.TEST_AUTH_USERNAME ?? "";
const password = process.env.TEST_AUTH_PASSWORD ?? "";

// An unsigned JWT is enough here: the dashboard only reads the
// payload, the platform is what verifies signatures.
function fakeJwt(role: string, expiresInSeconds: number): string {
  const encode = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");

  return [
    encode({ alg: "HS256", typ: "JWT" }),
    encode({
      sub: `${role}@company.com`,
      role,
      exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
    }),
    "test-signature",
  ].join(".");
}

async function signIn(page: Page, email: string, pw: string) {
  await page.goto("/");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill(pw);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function seedSession(page: Page, accessToken: string) {
  await page.addInitScript((token) => {
    sessionStorage.setItem(
      "dashboard_auth",
      JSON.stringify({
        access_token: token,
        refresh_token: "seeded-refresh-token",
        token_type: "bearer",
      }),
    );
  }, accessToken);
}

async function mockLoginAs(page: Page, role: string): Promise<string> {
  const accessToken = fakeJwt(role, 3600);

  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      json: {
        access_token: accessToken,
        refresh_token: "refresh-token-1",
        token_type: "bearer",
      },
    }),
  );

  return accessToken;
}

const dashboardHeading = (page: Page) =>
  page.getByRole("heading", { name: "Executive Dashboard" });

const signInButton = (page: Page) =>
  page.getByRole("button", { name: "Sign in" });

// ------------------------------------------------------------
// Against the real platform service (needs it running on :8005)
// ------------------------------------------------------------

test.describe("real platform service", () => {
  test.skip(
    !username || !password,
    "Set TEST_AUTH_USERNAME and TEST_AUTH_PASSWORD (see .env.example).",
  );

  test("logs in successfully with real credentials", async ({ page }) => {
    await signIn(page, username, password);

    await expect(dashboardHeading(page)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
  });

  test("shows the platform's error for a wrong password", async ({ page }) => {
    await signIn(page, username, "definitely-the-wrong-password");

    await expect(page.getByRole("alert")).toHaveText("Invalid credentials");
    await expect(signInButton(page)).toBeVisible();
  });
});

// ------------------------------------------------------------
// Failure cases and role views (no backend needed)
// ------------------------------------------------------------

test.describe("auth failure handling", () => {
  test("service unreachable shows a clear error, not a blank screen", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (route) =>
      route.abort("connectionrefused"),
    );

    await signIn(page, "ceo@company.com", "whatever");

    await expect(page.getByRole("alert")).toHaveText(
      "Authentication service is unavailable.",
    );
    await expect(signInButton(page)).toBeVisible();
  });

  test("service down behind the dev proxy (5xx) shows the same error", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({ status: 502, body: "Bad Gateway" }),
    );

    await signIn(page, "ceo@company.com", "whatever");

    await expect(page.getByRole("alert")).toHaveText(
      "Authentication service is unavailable.",
    );
  });

  test("expired session sends the user to login with a message", async ({ page }) => {
    await seedSession(page, fakeJwt("ceo", -60));
    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({
        status: 401,
        json: { detail: "Invalid or expired refresh token" },
      }),
    );

    await page.goto("/");

    await expect(page.getByRole("alert")).toHaveText(
      "Your session has expired. Please sign in again.",
    );
    await expect(signInButton(page)).toBeVisible();
  });

  test("refreshes the token before it expires", async ({ page }) => {
    // Expires in 30s, which is inside the 60s refresh window.
    await seedSession(page, fakeJwt("ceo", 30));
    const refreshedToken = fakeJwt("ceo", 3600);
    const refreshRequest = page.waitForRequest("**/api/v1/auth/refresh");

    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({
        json: {
          access_token: refreshedToken,
          refresh_token: "refresh-token-2",
          token_type: "bearer",
        },
      }),
    );

    await page.goto("/");

    const request = await refreshRequest;
    expect(request.postDataJSON()).toEqual({
      refresh_token: "seeded-refresh-token",
    });

    await expect
      .poll(() =>
        page.evaluate(() => sessionStorage.getItem("dashboard_auth")),
      )
      .toContain("refresh-token-2");
    await expect(dashboardHeading(page)).toBeVisible();
  });

  test("refresh while the service is down keeps the user signed in", async ({ page }) => {
    await seedSession(page, fakeJwt("ceo", 30));
    await page.route("**/api/v1/auth/refresh", (route) =>
      route.abort("connectionrefused"),
    );

    await page.goto("/");
    await page.waitForRequest("**/api/v1/auth/refresh");

    await expect(dashboardHeading(page)).toBeVisible();
    await expect(signInButton(page)).toHaveCount(0);
  });

  test("an unreadable stored token shows login, not a blank screen", async ({ page }) => {
    await seedSession(page, "not-a-jwt");

    await page.goto("/");

    await expect(signInButton(page)).toBeVisible();
  });

  test("ceo token shows the CEO KPIs", async ({ page }) => {
    await mockLoginAs(page, "ceo");

    await signIn(page, "ceo@company.com", "whatever");

    await expect(page.getByText("Total Units", { exact: true })).toBeVisible();
    await expect(page.getByText("Warehouse SKUs", { exact: true })).toHaveCount(0);
  });

  test("warehouse_manager token shows the warehouse KPIs", async ({ page }) => {
    await mockLoginAs(page, "warehouse_manager");

    await signIn(page, "warehousemanager@company.com", "whatever");

    await expect(page.getByText("Warehouse SKUs", { exact: true })).toBeVisible();
    await expect(page.getByText("Total Units", { exact: true })).toHaveCount(0);
  });

  test("a role without a dashboard view gets a clear message", async ({ page }) => {
    await mockLoginAs(page, "supplier");

    await signIn(page, "supplier@company.com", "whatever");

    await expect(page.getByRole("alert")).toHaveText(
      "Your account's role does not have access to this dashboard.",
    );
  });

  test("logout revokes the session with a Bearer token and returns to login", async ({ page }) => {
    const accessToken = await mockLoginAs(page, "ceo");
    const logoutRequest = page.waitForRequest("**/api/v1/auth/logout");

    await page.route("**/api/v1/auth/logout", (route) =>
      route.fulfill({ json: { message: "Logged out" } }),
    );

    await signIn(page, "ceo@company.com", "whatever");
    await page.getByRole("button", { name: "Logout" }).click();

    const request = await logoutRequest;
    expect(request.headers()["authorization"]).toBe(`Bearer ${accessToken}`);
    expect(request.postDataJSON()).toEqual({
      refresh_token: "refresh-token-1",
    });

    await expect(signInButton(page)).toBeVisible();
    expect(
      await page.evaluate(() => sessionStorage.getItem("dashboard_auth")),
    ).toBeNull();
  });
});