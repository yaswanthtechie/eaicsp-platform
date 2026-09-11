import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import AlertsPanel from "./components/AlertsPanel";
import DashboardFilters from "./components/DashboardFilters";
import ErrorBoundary from "./components/ErrorBoundary";
import ForecastAccuracy from "./components/ForecastAccuracy";
import ForecastChart from "./components/ForecastChart";
import InventoryHealth from "./components/InventoryHealth";
import InventoryHeatmap from "./components/InventoryHeatmap";
import InventoryTable from "./components/InventoryTable";
import ShipmentStatus from "./components/ShipmentStatus";
import SupplierRisk from "./components/SupplierRisk";
import SupplierRiskDistribution from "./components/SupplierRiskDistribution";
import { useWebSocket } from "./hooks/useWebSocket";
import { inventory } from "./mocks/inventory";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { colors, radius, space } from "./tokens";
import type {
    AlertMessage,
    InventoryItem,
    WebSocketMessage,
} from "./types/forecast";

function App() {
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

      setFilters({
        warehouse: params.get("warehouse") || "All",
        category: params.get("category") || "All",
        startDate: params.get("startDate") || "",
        endDate: params.get("endDate") || "",
      });
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

  const baseFilteredInventory = useMemo(() => {
    return liveInventory.filter((item) => {
      const warehouseMatches =
        filters.warehouse === "All" ||
        item.warehouse_id === filters.warehouse;

      const categoryMatches =
        filters.category === "All" ||
        item.category === filters.category;

      return warehouseMatches && categoryMatches;
    });
  }, [
    liveInventory,
    filters.warehouse,
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

  const kpis = [
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
    setSelectedKpi(title);

    if (title === "Low Stock") {
      setLowStockOnly((previous) => !previous);

      setTimeout(() => {
        document
          .getElementById("inventory-section")
          ?.scrollIntoView({
            behavior: "smooth",
          });
      }, 0);

      return;
    }

    if (title === "SKUs" || title === "Total Units") {
      setLowStockOnly(false);

      setTimeout(() => {
        document
          .getElementById("inventory-section")
          ?.scrollIntoView({
            behavior: "smooth",
          });
      }, 0);

      return;
    }

    if (title === "Alerts") {
      setTimeout(() => {
        document
          .getElementById("alerts-section")
          ?.scrollIntoView({
            behavior: "smooth",
          });
      }, 0);
    }
  };

  return (
    <ErrorBoundary>
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

        <DashboardFilters onFilterChange={setFilters} />

        <div className="kpi-grid">
          {kpis.map((kpi) => (
            <div
              key={kpi.title}
              onClick={() => handleKpiClick(kpi.title)}
              style={{
                background: colors.surface,
                border: `1px solid ${
                  selectedKpi === kpi.title
                    ? colors.primary
                    : kpi.title === "Low Stock" &&
                        lowStockOnly
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
            </div>
          ))}
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
              <ForecastChart
                startDate={filters.startDate}
                endDate={filters.endDate}
              />
            </div>
          </div>

          <div
            id="alerts-section"
            className="alerts-section"
          >
            <AlertsPanel
              alerts={alerts}
              connected={connected}
              isConnecting={isConnecting}
              failed={failed}
              onRemove={removeAlert}
            />
          </div>
        </div>

        <div className="kpi-suite-grid">
          <ForecastAccuracy />
          <InventoryHealth />
          <SupplierRisk />
          <ShipmentStatus />
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
            <InventoryTable data={filteredInventory} />
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
            <InventoryHeatmap data={filteredInventory} />
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
          ></div>

          <SupplierRiskDistribution />
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default App;