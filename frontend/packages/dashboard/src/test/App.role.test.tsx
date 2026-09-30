import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";

vi.mock("../api/dashboardGraphql", () => ({
  useDashboardData: vi.fn(),
}));

import { useDashboardData } from "../api/dashboardGraphql";

vi.mock("../mocks/user", () => ({
  mockUser: {
    role: "ceo",
    warehouse: "WH001",
  },
}));

vi.mock("../components/SupplierRisk", () => ({
  default: () => <div>Supplier Risk</div>,
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
  default: () => <div>Inventory Health</div>,
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

