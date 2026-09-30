import { test, expect } from "@playwright/test";

test("opens dashboard and displays KPIs", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Executive Dashboard" }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /SKUs\s+12000/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Total Units\s+45800/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Low Stock\s+1300/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Alerts\s+2/ }),
  ).toBeVisible();
});

test("filters by warehouse and drills into Low Stock KPI", async ({
  page,
}) => {
  await page.goto("/");

  const warehouseFilter = page.getByRole("combobox", {
    name: "Warehouse filter",
  });

  await warehouseFilter.click();

  await page.getByRole("option", { name: "WH001" }).click();

  await expect(warehouseFilter).toContainText("WH001");

  const lowStockKpi = page.getByRole("button", {
    name: /Low Stock\s+1300/,
  });

  await lowStockKpi.click();

  await expect(
    page.getByText("Showing low-stock inventory only"),
  ).toBeVisible();

  await expect(
    page.locator("#inventory-section"),
  ).toBeVisible();
});


test("goes offline and shows the last saved KPI snapshot", async ({
  page,
  context,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Executive Dashboard" }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /SKUs\s+12000/ }),
  ).toBeVisible();

  await page.evaluate(() => {
    localStorage.setItem(
      "executive-kpi-snapshot",
      JSON.stringify({
        kpis: [
          { title: "SKUs", value: 12000 },
          { title: "Total Units", value: 45800 },
          { title: "Low Stock", value: 1300 },
          { title: "Alerts", value: 2 },
        ],
        savedAt: new Date().toISOString(),
      }),
    );
  });

  await context.setOffline(true);

  await page.evaluate(() => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });

    window.dispatchEvent(new Event("offline"));
  });


  await expect(
    page.getByText("Offline — showing data from", { exact: false }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /SKUs\s+12000/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Total Units\s+45800/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Low Stock\s+1300/ }),
  ).toBeVisible();

  await expect(
    page.getByRole("button", { name: /Alerts\s+2/ }),
  ).toBeVisible();

  await context.setOffline(false);
});








