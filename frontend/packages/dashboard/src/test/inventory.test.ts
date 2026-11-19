import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/auth", () => ({
  getAuthSession: vi.fn(),
}));

function mockResponse(
  payload: unknown,
  status = 200,
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

async function loadInventoryModule() {
  vi.stubEnv("VITE_USE_MOCK_INVENTORY_NAMES", "false");

  const auth = await import("../api/auth");

  vi.mocked(auth.getAuthSession).mockReturnValue({
    access_token: "synthetic-test-token",
    refresh_token: "synthetic-refresh-token",
    token_type: "bearer",
    role: "ceo",
  });

  return import("../api/inventory");
}

describe("C7 Inventory name lookups", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();

    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns product and warehouse names when found", async () => {
    fetchMock
      .mockResolvedValueOnce(
        mockResponse({
          items: [
            {
              sku_id: "SKU-000123",
              name: "Steel Fastener Set 50pc",
            },
          ],
          total: 1,
        }),
      )
      .mockResolvedValueOnce(
        mockResponse({
          items: [
            {
              warehouse_id: "WH-HYD-01",
              name: "Hyderabad Central DC",
            },
          ],
          total: 1,
        }),
      );

    const {
      fetchInventoryNames,
      formatProductLabel,
      formatWarehouseLabel,
    } = await loadInventoryModule();

    const names = await fetchInventoryNames();

    expect(names.products["SKU-000123"]).toBe(
      "Steel Fastener Set 50pc",
    );

    expect(names.warehouses["WH-HYD-01"]).toBe(
      "Hyderabad Central DC",
    );

    expect(
      formatProductLabel("SKU-000123", names.products),
    ).toBe("Steel Fastener Set 50pc (SKU-000123)");

    expect(
      formatWarehouseLabel("WH-HYD-01", names.warehouses),
    ).toBe("Hyderabad Central DC (WH-HYD-01)");

    await fetchInventoryNames();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uses IDs when product or warehouse names are missing", async () => {
    fetchMock
      .mockResolvedValueOnce(
        mockResponse({
          items: [
            {
              sku_id: "SKU-000999",
              name: "Other Product",
            },
          ],
          total: 1,
        }),
      )
      .mockResolvedValueOnce(
        mockResponse({
          items: [
            {
              warehouse_id: "WH-DEL-01",
              name: "Other Warehouse",
            },
          ],
          total: 1,
        }),
      );

    const {
      fetchInventoryNames,
      formatProductLabel,
      formatWarehouseLabel,
    } = await loadInventoryModule();

    const names = await fetchInventoryNames();

    expect(
      formatProductLabel("SKU-000123", names.products),
    ).toBe("SKU-000123");

    expect(
      formatWarehouseLabel("WH-HYD-01", names.warehouses),
    ).toBe("WH-HYD-01");
  });

  it("does not reject when both lookup endpoints are down", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({}, 500))
      .mockResolvedValueOnce(mockResponse({}, 500));

    const { fetchInventoryNames } = await loadInventoryModule();

    await expect(fetchInventoryNames()).resolves.toEqual({
      products: {},
      warehouses: {},
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  describe("C7 Inventory name lookups, mock mode and retry", () => {
    beforeEach(() => {
      vi.resetModules();
      vi.clearAllMocks();
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
    });

    it("returns mock names with mock auth (no session)", async () => {
      vi.stubEnv("VITE_USE_MOCK_INVENTORY_NAMES", "true");
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const auth = await import("../api/auth");
      vi.mocked(auth.getAuthSession).mockReturnValue(null);
      const { fetchInventoryNames } = await import("../api/inventory");

      const names = await fetchInventoryNames();

      expect(names.products["SKU-000001"]).toBeDefined();
      expect(names.warehouses["WH-BLR-01"]).toBeDefined();
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("fetches again after a failed lookup", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(mockResponse({}, 503))
        .mockResolvedValueOnce(mockResponse({}, 503))
        .mockResolvedValueOnce(
          mockResponse({
            items: [{ sku_id: "SKU-000123", name: "Steel Fastener Set 50pc" }],
            total: 1,
          }),
        )
        .mockResolvedValueOnce(mockResponse({ items: [], total: 0 }));
      vi.stubGlobal("fetch", fetchMock);

      const { fetchInventoryNames } = await loadInventoryModule();

      await fetchInventoryNames();
      const names = await fetchInventoryNames();

      expect(names.products["SKU-000123"]).toBe("Steel Fastener Set 50pc");
      expect(fetchMock).toHaveBeenCalledTimes(4);
    });
  });
});
