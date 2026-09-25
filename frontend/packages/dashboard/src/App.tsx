import {
  Profiler,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ProfilerOnRenderCallback,
} from "react";

import AlertsPanel from "./components/AlertsPanel";
import DashboardFilters from "./components/DashboardFilters";
import ErrorBoundary from "./components/ErrorBoundary";
import ForecastAccuracy from "./components/ForecastAccuracy";
import ForecastChart from "./components/ForecastChart";
import InventoryHealth from "./components/InventoryHealth";
import InventoryHeatmap from "./components/InventoryHeatmap";
import InventoryTable from "./components/InventoryTable";
import NarrativeInsights from "./components/NarrativeInsights";
import ShipmentStatus from "./components/ShipmentStatus";
import SupplierRisk from "./components/SupplierRisk";
import SupplierRiskDistribution from "./components/SupplierRiskDistribution";
import ExportCsvButton from "./components/export/ExportCsvButton";
import ExportPdfButton from "./components/export/ExportPdfButton";
import { dashboardApi } from "./api/dashboard";
import { useWebSocket } from "./hooks/useWebSocket";
import { inventory } from "./mocks/inventory";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { mockUser, type UserRole } from "./mocks/user";
import { colors, radius, space } from "./tokens";
import type {
  AlertMessage,
  InventoryItem,
  WebSocketMessage,
} from "./types/forecast";

const handleProfilerRender: ProfilerOnRenderCallback = (
  id,
  phase,
  actualDuration,
  baseDuration,
) => {
  if (import.meta.env.DEV) {
    console.log(
      `[Profiler] ${id} | ${phase} | actual: ${actualDuration.toFixed(
        2,
      )}ms | base: ${baseDuration.toFixed(2)}ms`,
    );
  }
};

function App() {
  const [role, setRole] = useState<UserRole>(mockUser.role);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [liveInventory, setLiveInventory] =
    useState<InventoryItem[]>(inventory);

  const [filters, setFilters] = useState({
    warehouse: "All",
    category: "All",
    startDate: "",
    endDate: "",
  });

  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [selectedKpi, setSelectedKpi] = useState("");

  useEffect(() => {
    const updateFiltersFromUrl = () => {
      const params = new URLSearchParams(
        window.location.search,
      );

      const urlRole = params.get("role");

      if (urlRole === "ceo" || urlRole === "warehouse_manager") {
        setRole(urlRole);
      } else {
        setRole(mockUser.role);
      }

      setFilters({
        warehouse: params.get("warehouse") || "All",
        category: params.get("category") || "All",
        startDate: params.get("startDate") || "",
        endDate: params.get("endDate") || "",
      });

      setSelectedKpi(
        params.get("selectedKpi") || "",
      );

      setLowStockOnly(
        params.get("lowStock") === "true",
      );
    };

    updateFiltersFromUrl();

    window.addEventListener(
      "popstate",
      updateFiltersFromUrl,
    );

    return () => {
      window.removeEventListener(
        "popstate",
        updateFiltersFromUrl,
      );
    };
  }, []);

  useEffect(() => {
    if (import.meta.env.DEV) {
      startMockWebSocketServer();
    }
  }, []);

  const handleMessage = useCallback(
    (data: WebSocketMessage) => {
      if (data.type === "inventory_update") {
        setLiveInventory((prev) => {
          const existingIndex = prev.findIndex(
            (item) => item.sku_id === data.item.sku_id,
          );

          if (existingIndex === -1) {
            return [...prev, data.item];
          }

          const updated = [...prev];
          updated[existingIndex] = data.item;

          return updated;
        });

        return;
      }

      setAlerts((prev) => [data, ...prev]);
    },
    [],
  );

  const removeAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.filter((alert) => alert.id !== id),
    );
  }, []);

  const {
    connected,
    isConnecting,
    failed,
  } = useWebSocket({
    url: "ws://localhost:8080",
    onMessage: handleMessage,
    autoReconnect: true,
    maxRetries: 5,
  });
  const effectiveWarehouse = 
    role === "warehouse_manager"
      ? mockUser.warehouse ?? "All"
      : filters.warehouse;

  const baseFilteredInventory = useMemo(() => {
    return liveInventory.filter((item) => {
      const warehouseMatches =
        effectiveWarehouse === "All" ||
        item.warehouse_id === effectiveWarehouse;

      const categoryMatches =
        filters.category === "All" ||
        item.category === filters.category;

      return warehouseMatches && categoryMatches;
    });
  }, [
    liveInventory,
    effectiveWarehouse,
    filters.category,
  ]);

  const filteredInventory = useMemo(() => {
    if (!lowStockOnly) {
      return baseFilteredInventory;
    }

    return baseFilteredInventory.filter(
      (item) => item.needs_reorder,
    );
  }, [baseFilteredInventory, lowStockOnly]);

  const totalSkus = baseFilteredInventory.length;

  const totalUnits = useMemo(
    () =>
      baseFilteredInventory.reduce(
        (total, item) =>
          total + item.quantity_on_hand,
        0,
      ),
    [baseFilteredInventory],
  );

  const lowStockCount = useMemo(
    () =>
      baseFilteredInventory.filter(
        (item) => item.needs_reorder,
      ).length,
    [baseFilteredInventory],
  );

  const alertCount = alerts.length;

  const kpis =
    role === "warehouse_manager"
      ? [
          {
            title: "Warehouse SKUs",
            value: totalSkus,
          },
          {
            title: "Warehouse Units",
            value: totalUnits,
          },
          {
            title: "Reorder Items",
            value: lowStockCount,
          },
          {
            title: "Warehouse Alerts",
            value: alertCount,
          },
        ]
      : [
          {
            title: "SKUs",
            value: totalSkus,
          },
          {
            title: "Total Units",
            value: totalUnits,
          },
          {
            title: "Low Stock",
            value: lowStockCount,
          },
          {
            title: "Alerts",
            value: alertCount,
          },
        ];

  const handleKpiClick = (title: string) => {
    const params = new URLSearchParams(
      window.location.search,
    );

    let nextLowStock = lowStockOnly;

    if (
      title === "Low Stock" ||
      title === "Reorder Items"
    ) {
      nextLowStock = !lowStockOnly;
    } else if (
      title === "SKUs" ||
      title === "Total Units" ||
      title === "Warehouse SKUs" ||
      title === "Warehouse Units"
    ) {
      nextLowStock = false;
    }

    params.set("selectedKpi", title);
    params.set(
      "lowStock",
      String(nextLowStock),
    );

    const queryString = params.toString();

    window.history.pushState(
      {},
      "",
      queryString
        ? `${window.location.pathname}?${queryString}`
        : window.location.pathname,
    );

    setSelectedKpi(title);
    setLowStockOnly(nextLowStock);

    setTimeout(() => {
      if (title === "Alerts") {
        document
          .getElementById("alerts-section")
          ?.scrollIntoView({
            behavior: "smooth",
          });
      } else {
        document
          .getElementById("inventory-section")
          ?.scrollIntoView({
            behavior: "smooth",
          });
      }
    }, 0);
  };

  return (
    <div
      style={{
        background: colors.bg,
        minHeight: "100vh",
        padding: space.lg,
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
          marginBottom: space.lg,
        }}
      >
        <h1
          style={{
            color: colors.text,
            textAlign: "center",
            margin: 0,
            fontSize: space.xl,
            fontWeight: 700,
          }}
        >
          Executive Dashboard
        </h1>
      </div>

      <DashboardFilters
        filters={filters}
        onFilterChange={setFilters}
        lockedWarehouse={
          role === "warehouse_manager" ? effectiveWarehouse : undefined
        }
      />

      <div
        style={{
          display: "flex",
          gap: space.md,
          alignItems: "center",
          marginBottom: space.lg,
        }}
      >
        <ExportCsvButton
          role={role}
          inventory={filteredInventory}
          suppliers={dashboardApi.getSupplierRisk()}
          shipments={dashboardApi.getShipmentStatus()}
        />

        <ExportPdfButton
          role={role}
          inventory={filteredInventory}
          suppliers={dashboardApi.getSupplierRisk()}
          shipments={dashboardApi.getShipmentStatus()}
          filters={{ ...filters, warehouse: effectiveWarehouse }}
          kpis={kpis}
        />
      </div>

      <div className="kpi-grid">
        {kpis.map((kpi) => (
          <button
            key={kpi.title}
            type="button"
            onClick={() =>
              handleKpiClick(kpi.title)
            }
            aria-pressed={
              selectedKpi === kpi.title
            }
            style={{
              background: colors.surface,
              border: `1px solid ${
                selectedKpi === kpi.title
                  ? colors.primary
                  : (
                      kpi.title === "Low Stock" ||
                      kpi.title === "Reorder Items"
                    ) && lowStockOnly
                    ? colors.warning
                    : colors.border
              }`,
              borderRadius: radius.md,
              padding: space.lg,
              cursor: "pointer",
              boxSizing: "border-box",
              minWidth: 0,
            }}
          >
            <div
              style={{
                color: colors.textMuted,
                fontSize: 14,
                marginBottom: space.sm,
              }}
            >
              {kpi.title}
            </div>

            <div
              style={{
                color: colors.text,
                fontSize: 28,
                fontWeight: 700,
              }}
            >
              {kpi.value}
            </div>
          </button>
        ))}
      </div>

      <div
        style={{
          marginTop: space.lg,
          marginBottom: space.lg,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          color: colors.text,
        }}
      >
        <ErrorBoundary>
          <NarrativeInsights
            inventory={baseFilteredInventory}
            suppliers={dashboardApi.getSupplierRisk()}
            shipments={dashboardApi.getShipmentStatus()}
            showSupplierInsight={role === "ceo"}
          />
        </ErrorBoundary>
      </div>

      {lowStockOnly && (
        <div
          style={{
            background: colors.surface,
            border: `1px solid ${colors.warning}`,
            borderRadius: radius.md,
            padding: space.sm,
            marginBottom: space.lg,
            color: colors.text,
            fontSize: 14,
          }}
        >
          Showing low-stock inventory only
        </div>
      )}

      <div className="dashboard-grid">
        <div className="forecast-section">
          <div
            style={{
              background: colors.surface,
              padding: space.lg,
              borderRadius: radius.lg,
              boxSizing: "border-box",
              width: "100%",
            }}
          >
            <ErrorBoundary>
              <Profiler
                id="ForecastChart"
                onRender={handleProfilerRender}
              >
                <ForecastChart
                  startDate={filters.startDate}
                  endDate={filters.endDate}
                />
              </Profiler>
            </ErrorBoundary>
          </div>
        </div>

        <div
          id="alerts-section"
          className="alerts-section"
        >
          <ErrorBoundary>
            <AlertsPanel
              alerts={alerts}
              connected={connected}
              isConnecting={isConnecting}
              failed={failed}
              onRemove={removeAlert}
            />
          </ErrorBoundary>
        </div>
      </div>

      <div className="kpi-suite-grid">
        <ErrorBoundary>
          <ForecastAccuracy
            startDate={filters.startDate}
            endDate={filters.endDate}
          />
        </ErrorBoundary>

        <ErrorBoundary>
          <InventoryHealth
            inventory={liveInventory}
            warehouse={filters.warehouse}
            category={filters.category}
          />
        </ErrorBoundary>

        {role === "ceo" && (
          <ErrorBoundary>
            <SupplierRisk />
          </ErrorBoundary>
        )}

        <ErrorBoundary>
          <ShipmentStatus />
        </ErrorBoundary>
      </div>

      <div
        id="inventory-section"
        className="inventory-section"
        style={{
          marginTop: space.lg,
          width: "100%",
        }}
      >
        <div
          style={{
            background: colors.surface,
            padding: space.lg,
            borderRadius: radius.lg,
            boxSizing: "border-box",
            width: "100%",
          }}
        >
          <ErrorBoundary>
            <Profiler
              id="InventoryTable"
              onRender={handleProfilerRender}
            >
              <InventoryTable
                data={filteredInventory}
              />
            </Profiler>
          </ErrorBoundary>
        </div>

        <div
          style={{
            background: colors.surface,
            padding: space.lg,
            borderRadius: radius.lg,
            boxSizing: "border-box",
            width: "100%",
            marginTop: space.lg,
          }}
        >
          <ErrorBoundary>
            <Profiler
              id="InventoryHeatmap"
              onRender={handleProfilerRender}
            >
              <InventoryHeatmap
                data={filteredInventory}
              />
            </Profiler>
          </ErrorBoundary>
        </div>

        {role === "ceo" && (
          <div
            style={{
              background: colors.surface,
              padding: space.lg,
              borderRadius: radius.lg,
              boxSizing: "border-box",
              width: "100%",
              marginTop: space.lg,
            }}
          >
            <ErrorBoundary>
              <SupplierRiskDistribution />
            </ErrorBoundary>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;