import { test, expect, type Page } from "@playwright/test";
import { inventory } from "../src/mocks/inventory";

// Expected numbers are computed from the same mock data the GraphQL mock
// server returns, so the tests stay correct if the mock data changes.
const all = {
  skus: inventory.length,
  units: inventory.reduce((t, i) => t + i.quantity_on_hand, 0),
  lowStock: inventory.filter((i) => i.needs_reorder).length,
};

const wh001 = inventory.filter((i) => i.warehouse_id === "WH001");
const wh001LowStock = wh001.filter((i) => i.needs_reorder).length;

function kpi(page: Page, title: string, value: number) {
  return page.getByRole("button", {
    name: new RegExp(`^${title}\\s*${value}$`),
  });
}

test("opens dashboard and displays KPIs", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Executive Dashboard" })).toBeVisible();
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();
  await expect(kpi(page, "Total Units", all.units)).toBeVisible();
  await expect(kpi(page, "Low Stock", all.lowStock)).toBeVisible();
});

test("filters by warehouse and drills into Low Stock KPI", async ({ page }) => {
  await page.goto("/");

  const warehouseFilter = page.getByRole("combobox", { name: "Warehouse filter" });
  await warehouseFilter.click();
  await page.getByRole("option", { name: "WH001" }).click();
  await expect(warehouseFilter).toContainText("WH001");

  // The KPIs must follow the filter.
  await expect(kpi(page, "SKUs", wh001.length)).toBeVisible();

  const lowStockKpi = kpi(page, "Low Stock", wh001LowStock);
  await lowStockKpi.click();

  await expect(lowStockKpi).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Showing low-stock inventory only")).toBeVisible();
  await expect(page).toHaveURL(/warehouse=WH001/);
  await expect(page).toHaveURL(/lowStock=true/);
  await expect(page.locator("#inventory-section")).toBeInViewport();
});

test("goes offline, reloads, and still shows the last snapshot", async ({ page, context }) => {
  await page.goto("/");
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();

  // The app itself must have saved the snapshot — the test doesn't seed it.
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("executive-kpi-snapshot:ceo")))
    .toContain(`"value":${all.skus}`);

  // Wait until the service worker controls the page, so the app shell
  // can be served from the precache once the network is gone.
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

  await context.setOffline(true);
  await page.reload();

  await expect(page.getByText(/Offline — showing data from/)).toBeVisible();
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();
  await expect(kpi(page, "Total Units", all.units)).toBeVisible();
});

  test("keeps the dashboard when a refresh fails after reconnecting", async ({
  page,
  context,
}) => {
  await page.goto("/");

  // Initial dashboard data is loaded.
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();
  await expect(page.locator("#inventory-section")).toBeVisible();

  // Make GraphQL fail for the reconnect refresh.
  await page.route("**/graphql", (route) =>
    route.fulfill({
      status: 500,
      body: "Server error",
    }),
  );

  // Simulate going offline.
  await context.setOffline(true);

  await expect
    .poll(() => page.evaluate(() => navigator.onLine))
    .toBe(false);

  // Playwright does not reliably restore navigator.onLine in this setup,
  // so restore the browser state and notify the application of reconnect.
  await context.setOffline(false);

  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    window.dispatchEvent(new Event("online"));
  });

  // Reconnect triggers a failed GraphQL refresh.
  // Previous dashboard data must remain visible.
  await expect(
    page.getByText(/Couldn't reach the server — showing data from/),
  ).toBeVisible({
    timeout: 15000,
  });

  await expect(
    page.getByText("Failed to load dashboard data."),
  ).toBeHidden();

  await expect(page.locator("#inventory-section")).toBeVisible();
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();

  // Server is back: remove the failing route and retry.
  await page.unroute("**/graphql");

  await page.getByRole("button", { name: "Retry" }).click();

  await expect(
    page.getByText(/Couldn't reach the server/),
  ).toBeHidden();

  await expect(page.locator("#inventory-section")).toBeVisible();
  await expect(kpi(page, "SKUs", all.skus)).toBeVisible();
});