import {
  Profiler,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ProfilerOnRenderCallback,
} from "react";
import { useDashboardData } from "./api/dashboardGraphql";
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
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { useWebSocket } from "./hooks/useWebSocket";
import { inventory } from "./mocks/inventory";
import { mockUser, type UserRole } from "./mocks/user";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { colors, radius, space } from "./tokens";
import type {
  AlertMessage,
  InventoryItem,
  WebSocketMessage,
} from "./types/forecast";
import { getKpiSnapshot, saveKpiSnapshot } from "./utils/kpiSnapshot";

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
  const {
    data: dashboardData,
    loading: dashboardLoading,
    error: dashboardError,
    refetch,
  } = useDashboardData();
  const [role, setRole] = useState<UserRole>(mockUser.role);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [liveInventory, setLiveInventory] =
    useState<InventoryItem[]>(dashboardData?.dashboard.inventory ?? inventory);
  const isOnline = useOnlineStatus();
  const wasOffline = useRef(false);
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

  const refreshDashboardData = useCallback(async () => {
    try {
      await refetch();
    } catch {
      // Keep the current data if refresh fails.
    }
  }, [refetch]);

  useEffect(() => {
    if (!isOnline) {
      wasOffline.current = true;
      return;
    }

    if (wasOffline.current) {
      wasOffline.current = false;
      void refreshDashboardData();
    }
  }, [isOnline, refreshDashboardData]);

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

  const totalSkus = dashboardData?.dashboard.kpis.totalSkus ?? 0;

  const totalUnits = dashboardData?.dashboard.kpis.totalUnits ?? 0;

  const lowStockCount = dashboardData?.dashboard.kpis.reorderItems ?? 0;
  const alertCount = dashboardData?.dashboard.kpis.alerts ?? 0;

  const kpis = useMemo( () => 
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
        ],
    [
      role,
      totalSkus,
      totalUnits,
      lowStockCount,
      alertCount
    ],
  );
  
  const offlineSnapshot = !isOnline
    ? getKpiSnapshot()
    : null;

  const displayedKpis = offlineSnapshot?.kpis ?? kpis;

  useEffect(() => {
    if (isOnline) {
      saveKpiSnapshot(kpis);
    }
  }, [isOnline, kpis]);

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

  if (dashboardLoading) {
    return (
      <div
        style={{
        background: colors.bg,
        minHeight: "100vh",
        padding: space.lg,
        color: colors.text,
      }}
      >
        Loading dashboard data...
      </div>
    );
  }

  if (dashboardError) {
    return (
      <div
        style={{
        background: colors.bg,
        minHeight: "100vh",
        padding: space.lg,
        color: colors.text,
      }}
      >
        Failed to load dashboard data.
      </div>
    );
  }

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
          suppliers={dashboardData?.dashboard.supplierRisk ?? []}
          shipments=
            {dashboardData?.dashboard.shipmentStatus ?? {
              total: 0,
              pending: 0,
              delivered: 0,
              in_transit: 0,
              delayed: 0,
              cancelled: 0,
            }
          }
        />

        <ExportPdfButton
          role={role}
          inventory={filteredInventory}
          suppliers={dashboardData?.dashboard.supplierRisk ?? []}
          shipments=
            {dashboardData?.dashboard.shipmentStatus ?? {
              total: 0,
              pending: 0,
              delivered: 0,
              in_transit: 0,
              delayed: 0,
              cancelled: 0,
            }
          }
          filters={{ ...filters, warehouse: effectiveWarehouse }}
          kpis={kpis}
        />
      </div>
      {!isOnline && offlineSnapshot && (
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
          role="status"
          aria-live="polite"
        >
          Offline — showing data from{" "}
          {new Date(offlineSnapshot.savedAt).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      )}
      <div className="kpi-grid">
        {displayedKpis.map((kpi) => (
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
            suppliers={dashboardData?.dashboard.supplierRisk ?? []}
            shipments=
              {dashboardData?.dashboard.shipmentStatus ?? {
                total: 0,
                pending: 0,
                delivered: 0,
                in_transit: 0,
                delayed: 0,
                cancelled: 0,
              }
            }
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
                  data={dashboardData?.dashboard.forecast ?? []}
                  loading={dashboardLoading}
                  error={Boolean(dashboardError)}
                  onRetry={() => void refetch()}
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
            inventory={dashboardData?.dashboard.inventory ?? []}
            warehouse={filters.warehouse}
            category={filters.category}
          />
        </ErrorBoundary>

        {role === "ceo" && (
          <ErrorBoundary>
            <SupplierRisk
              supplierRisk={dashboardData?.dashboard.supplierRisk ?? []}
              loading={dashboardLoading}
              error={Boolean(dashboardError)}
              onRetry={() => void refetch()}
            />
          </ErrorBoundary>
        )}

        <ErrorBoundary>
          <ShipmentStatus
              shipmentStatus={dashboardData?.dashboard.shipmentStatus}
              loading={dashboardLoading}
              error={Boolean(dashboardError)}
              onRetry={() => void refetch()}
          />
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