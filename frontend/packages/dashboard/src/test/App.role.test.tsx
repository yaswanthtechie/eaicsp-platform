import { act, fireEvent, render, screen } from "@testing-library/react";import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { WebSocketMessage } from "../types/forecast";
import { snapshotStorageKey } from "../utils/kpiSnapshot";

vi.mock("../api/dashboardGraphql", () => ({
  useDashboardData: vi.fn(),
}));

const ws = vi.hoisted(() => ({
  onMessage: undefined as ((data: WebSocketMessage) => void) | undefined,
}));

vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: ({
    onMessage,
  }: {
    onMessage: (data: WebSocketMessage) => void;
  }) => {
    ws.onMessage = onMessage;

    return {
      connected: true,
      isConnecting: false,
      failed: false,
    };
  },
}));

import { useDashboardData } from "../api/dashboardGraphql";

vi.mock("../mocks/user", () => ({
  mockUser: {
    role: "ceo",
    warehouse: "WH001",
  },
}));

vi.mock("../components/SupplierRisk", () => ({
  default: ({ loading }: { loading: boolean }) => (
    <div data-testid="supplier-risk" data-loading={String(loading)}>
      Supplier Risk
    </div>
  ),
}));

vi.mock("../components/SupplierRiskDistribution", () => ({
  default: () => <div>Supplier Risk Distribution</div>,
}));

vi.mock("../components/InventoryHeatmap", () => ({
  default: () => <div>Inventory Heatmap</div>,
}));

vi.mock("../components/InventoryTable", () => ({
  default: () => <div>Inventory Table</div>,
}));

vi.mock("../components/ForecastChart", () => ({
  default: () => <div>Forecast Chart</div>,
}));

vi.mock("../components/ForecastAccuracy", () => ({
  default: () => <div>Forecast Accuracy</div>,
}));

vi.mock("../components/InventoryHealth", () => ({
  default: ({
    inventory,
    warehouse,
  }: {
    inventory: { quantity_on_hand: number }[];
    warehouse: string;
  }) => (
    <div
      data-testid="inventory-health"
      data-warehouse={warehouse}
      data-units={inventory.reduce(
        (total, item) => total + item.quantity_on_hand,
        0,
      )}
    >
      Inventory Health
    </div>
  ),
}));

vi.mock("../components/ShipmentStatus", () => ({
  default: () => <div>Shipment Status</div>,
}));

vi.mock("../components/AlertsPanel", () => ({
  default: () => <div>Alerts Panel</div>,
}));

vi.mock("../components/DashboardFilters", () => ({
  default: ({
    lockedWarehouse,
  }: {
    lockedWarehouse?: string;
  }) => (
    <select
      aria-label="Warehouse filter"
      disabled={lockedWarehouse !== undefined}
      value={lockedWarehouse ?? "All"}
      onChange={() => {}}
    >
      <option value="All">All Warehouses</option>
      <option value="WH001">WH001</option>
      <option value="WH002">WH002</option>
    </select>
  ),
}));

vi.mock("../components/NarrativeInsights", () => ({
  default: ({
    showSupplierInsight,
  }: {
    showSupplierInsight?: boolean;
  }) => (
    <div>
      Narrative Insights
      {showSupplierInsight && <span>Supplier Insight</span>}
    </div>
  ),
}));

vi.mock("../components/ErrorBoundary", () => ({
  default: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("../components/export/ExportCsvButton", () => ({
  default: () => <button>Export CSV</button>,
}));

vi.mock("../components/export/ExportPdfButton", () => ({
  default: () => <button>Export PDF</button>,
}));

const mockDashboardData = {
  dashboard: {
    kpis: {
      totalSkus: 12000,
      totalUnits: 45800,
      reorderItems: 1300,
      alerts: 2,
    },
    inventory: [],
    forecast: [],
    supplierRisk: [],
    shipmentStatus: {
      total: 100,
      pending: 20,
      delivered: 50,
      in_transit: 15,
      delayed: 10,
      cancelled: 5,
    },
    inventoryHealth: [],
  },
};

function mockQuery(
  result: Partial<ReturnType<typeof useDashboardData>>,
) {
  vi.mocked(useDashboardData).mockReturnValue({
    data: undefined,
    loading: false,
    error: undefined,
    refetch: vi.fn(),
    ...result,
  } as unknown as ReturnType<typeof useDashboardData>);
}

const inventoryItem = {
  product_name: "Item",
  category: "Food",
  quantity_on_hand: 10,
  reorder_point: 5,
  avg_daily_demand: 1,
};

describe("App role-based views", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useDashboardData).mockReturnValue({
      data: mockDashboardData,
      loading: false,
      error: undefined,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDashboardData>);
  });


  it("shows supplier risk and CEO KPIs for CEO", () => {
    window.history.replaceState({}, "", "/?role=ceo");

    render(<App />);

    expect(screen.getByText("Supplier Risk")).toBeInTheDocument();
    expect(
      screen.getByText("Supplier Risk Distribution"),
    ).toBeInTheDocument();
    expect(screen.getByText("Supplier Insight")).toBeInTheDocument();

    expect(screen.getByText("SKUs")).toBeInTheDocument();
    expect(screen.getByText("Total Units")).toBeInTheDocument();
    expect(screen.getByText("Low Stock")).toBeInTheDocument();
    expect(screen.getByText("Alerts")).toBeInTheDocument();
  });

  it("hides supplier risk and shows warehouse manager KPIs", () => {
    window.history.replaceState({}, "", "/?role=warehouse_manager");

    render(<App />);

    expect(screen.queryByText("Supplier Risk")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Supplier Risk Distribution"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Supplier Insight")).not.toBeInTheDocument();

    expect(screen.getByText("Warehouse SKUs")).toBeInTheDocument();
    expect(screen.getByText("Warehouse Units")).toBeInTheDocument();
    expect(screen.getByText("Reorder Items")).toBeInTheDocument();
    expect(screen.getByText("Warehouse Alerts")).toBeInTheDocument();
  });

  it("locks the warehouse filter for a warehouse manager", async () => {
    window.history.replaceState({}, "", "/?role=warehouse_manager");

    render(<App />);

    const warehouseSelect = await screen.findByLabelText("Warehouse filter");
    expect(warehouseSelect).toBeDisabled();
  });

  it("lets the CEO change the warehouse filter", async () => {
    window.history.replaceState({}, "", "/?role=ceo");

    render(<App />);

    const warehouseSelect = await screen.findByLabelText("Warehouse filter");
    expect(warehouseSelect).not.toBeDisabled();
  });
});

describe("App KPIs and offline snapshot", () => {
    beforeEach(() => {
      localStorage.clear();
      vi.restoreAllMocks();
    });

    const oneItem = (quantity: number) =>
  ({
    ...mockDashboardData,
    dashboard: {
      ...mockDashboardData.dashboard,
      inventory: [
        {
          ...inventoryItem,
          sku_id: "A",
          warehouse_id: "WH001",
          quantity_on_hand: quantity,
          needs_reorder: false,
        },
      ],
    },
  }) as unknown as ReturnType<typeof useDashboardData>["data"];

    it("offers Retry when the first load fails online and only a snapshot exists (Issue 3)", () => {
  window.history.replaceState({}, "", "/?role=ceo");
  localStorage.setItem(
    snapshotStorageKey("ceo"),
    JSON.stringify({
      kpis: [{ title: "SKUs", value: 7 }],
      savedAt: "2026-10-01T10:42:00.000Z",
    }),
  );
  const refetch = vi.fn().mockResolvedValue({});
  mockQuery({ error: new Error("Server error") as never, refetch });

  render(<App />);

  expect(
    screen.getByText(/Couldn't reach the server — showing data from/),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Retry" }));

  expect(refetch).toHaveBeenCalledTimes(1);
});

it("does not turn panels into skeletons during a refetch (Issue 4)", () => {
  window.history.replaceState({}, "", "/?role=ceo");
  mockQuery({ data: oneItem(10), loading: true });

  render(<App />);

  expect(screen.getByTestId("supplier-risk")).toHaveAttribute(
    "data-loading",
    "false",
  );
});
    it("computes KPIs from the inventory, scoped to the manager's warehouse", () => {
     window.history.replaceState(
      {},
      "",
      "/?role=warehouse_manager",
    );

    mockQuery({
      data: {
        ...mockDashboardData,
        dashboard: {
          ...mockDashboardData.dashboard,
          inventory: [
            {
              ...inventoryItem,
              sku_id: "A",
              warehouse_id: "WH001",
              needs_reorder: true,
            },
            {
              ...inventoryItem,
              sku_id: "B",
              warehouse_id: "WH001",
              needs_reorder: false,
            },
            {
              ...inventoryItem,
              sku_id: "C",
              warehouse_id: "WH002",
              needs_reorder: true,
            },
          ],
        },
      } as unknown as ReturnType<typeof useDashboardData>["data"],
    });

    render(<App />);

    expect(
      screen.getByRole("button", {
        name: /Warehouse SKUs\s*2/,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /Warehouse Units\s*20/,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /Reorder Items\s*1/,
      }),
    ).toBeInTheDocument();
  });

  it("shows the saved snapshot and banner when opened offline", () => {
    window.history.replaceState({}, "", "/?role=ceo");

    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);

    localStorage.setItem(
      snapshotStorageKey("ceo"),
      JSON.stringify({
        kpis: [{ title: "SKUs", value: 4242 }],
        savedAt: "2026-10-01T10:42:00.000Z",
      }),
    );

    mockQuery({
      error: new Error("Failed to fetch") as never,
    });

    render(<App />);

    expect(
      screen.getByText(/Offline — showing data from/),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /SKUs\s*4242/,
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Failed to load dashboard data."),
    ).not.toBeInTheDocument();
  });

  it("does not overwrite the snapshot with zeros while loading", () => {
    window.history.replaceState({}, "", "/?role=ceo");

    const saved = JSON.stringify({
      kpis: [{ title: "SKUs", value: 4242 }],
      savedAt: "2026-10-01T10:42:00.000Z",
    });

    localStorage.setItem(
      snapshotStorageKey("ceo"),
      saved,
    );

    mockQuery({
      loading: true,
    });

    render(<App />);

    expect(
      localStorage.getItem(snapshotStorageKey("ceo")),
    ).toBe(saved);
  });

  it("keeps the dashboard mounted while refetching (Fix 1)", () => {
  window.history.replaceState({}, "", "/?role=ceo");

  mockQuery({
    data: oneItem(10),
    loading: true,
  });

  render(<App />);

  expect(
    screen.queryByText("Loading dashboard data..."),
  ).not.toBeInTheDocument();

  expect(
    screen.getByText("Inventory Table"),
  ).toBeInTheDocument();
});

it("lets the user retry when the first load fails (Fix 2)", () => {
  window.history.replaceState({}, "", "/?role=ceo");

  const refetch = vi.fn().mockResolvedValue({});

  mockQuery({
    error: new Error("Server error") as never,
    refetch,
  });

  render(<App />);

  expect(
    screen.getByText("Failed to load dashboard data."),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Retry" }),
  );

  expect(refetch).toHaveBeenCalledTimes(1);
});

it("passes live WebSocket updates to Inventory Health (Fix 3)", () => {
  window.history.replaceState({}, "", "/?role=ceo");

  mockQuery({
    data: oneItem(10),
  });

  render(<App />);

  expect(
    screen.getByTestId("inventory-health"),
  ).toHaveAttribute("data-units", "10");

  act(() => {
    ws.onMessage?.({
      type: "inventory_update",
      item: {
        ...inventoryItem,
        sku_id: "A",
        warehouse_id: "WH001",
        quantity_on_hand: 3,
        needs_reorder: true,
      },
    });
  });

  expect(
    screen.getByTestId("inventory-health"),
  ).toHaveAttribute("data-units", "3");
});

it("scopes Inventory Health to the manager's warehouse (Fix 3)", () => {
  window.history.replaceState(
    {},
    "",
    "/?role=warehouse_manager",
  );

  mockQuery({
    data: oneItem(10),
  });

  render(<App />);

  expect(
    screen.getByTestId("inventory-health"),
  ).toHaveAttribute("data-warehouse", "WH001");
});

it("never shows another role's snapshot (Fix 4)", () => {
  window.history.replaceState(
    {},
    "",
    "/?role=warehouse_manager",
  );

  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);

  localStorage.setItem(
    snapshotStorageKey("ceo"),
    JSON.stringify({
      kpis: [{ title: "SKUs", value: 99999 }],
      savedAt: "2026-10-01T10:42:00.000Z",
    }),
  );

  mockQuery({
    error: new Error("Failed to fetch") as never,
  });

  render(<App />);

  expect(
    screen.queryByRole("button", {
      name: /SKUs\s*99999/,
    }),
  ).not.toBeInTheDocument();
});

it("keeps live KPIs when going offline mid-session (Fix 4)", () => {
  window.history.replaceState({}, "", "/?role=ceo");

  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);

  localStorage.setItem(
    snapshotStorageKey("ceo"),
    JSON.stringify({
      kpis: [{ title: "SKUs", value: 4242 }],
      savedAt: "2026-10-01T10:42:00.000Z",
    }),
  );

  mockQuery({
    data: oneItem(10),
  });

  render(<App />);

  // Live data (1 SKU), not the stale snapshot (4242), plus the banner.
  expect(
    screen.getByRole("button", {
      name: /^SKUs\s*1$/,
    }),
  ).toBeInTheDocument();

  expect(
    screen.getByText(/Offline — showing data from/),
  ).toBeInTheDocument();
});

it("keeps the dashboard and offers Retry when a refresh fails (Issue A)", () => {
  window.history.replaceState({}, "", "/?role=ceo");

  localStorage.setItem(
    snapshotStorageKey("ceo"),
    JSON.stringify({
      kpis: [{ title: "SKUs", value: 1 }],
      savedAt: "2026-10-01T10:42:00.000Z",
    }),
  );

  const refetch = vi.fn().mockResolvedValue({});

  mockQuery({
    data: oneItem(10),
    error: new Error("Server error") as never,
    refetch,
  });

  render(<App />);

  expect(
    screen.queryByText("Failed to load dashboard data."),
  ).not.toBeInTheDocument();

  expect(screen.getByText("Inventory Table")).toBeInTheDocument();

  expect(
    screen.getByText(
      /Couldn't reach the server — showing data from/,
    ),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Retry" }),
  );

  expect(refetch).toHaveBeenCalledTimes(1);
});

it("saves unfiltered totals in the snapshot, not the CEO's filtered view (Issue D)", () => {
  window.history.replaceState(
    {},
    "",
    "/?role=ceo&warehouse=WH001",
  );

  mockQuery({
    data: {
      ...mockDashboardData,
      dashboard: {
        ...mockDashboardData.dashboard,
        inventory: [
          {
            ...inventoryItem,
            sku_id: "A",
            warehouse_id: "WH001",
            quantity_on_hand: 10,
            needs_reorder: false,
          },
          {
            ...inventoryItem,
            sku_id: "B",
            warehouse_id: "WH002",
            quantity_on_hand: 5,
            needs_reorder: true,
          },
        ],
      },
    } as unknown as ReturnType<typeof useDashboardData>["data"],
  });

  render(<App />);

  // On screen: filtered to WH001 (1 SKU).
  expect(
    screen.getByRole("button", {
      name: /^SKUs\s*1$/,
    }),
  ).toBeInTheDocument();

  // In the snapshot: company totals (2 SKUs, 15 units).
  const saved = JSON.parse(
    localStorage.getItem(snapshotStorageKey("ceo")) ?? "{}",
  );

  expect(saved.kpis).toEqual(
    expect.arrayContaining([
      { title: "SKUs", value: 2 },
      { title: "Total Units", value: 15 },
    ]),
  );
});
});
