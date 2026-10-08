import {
  lazy,
  Profiler,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ProfilerOnRenderCallback,
} from "react";
import {
  clearAuthSession,
  getAuthSession,
  getTokenExpiry,
  logout,
  refreshAuthSession,
} from "./api/auth";
import { useDashboardData } from "./api/dashboardGraphql";
import Login from "./components/Login";
import { Button } from "@/components/ui/button";
import AlertsPanel from "./components/AlertsPanel";
import DashboardFilters from "./components/DashboardFilters";
import ErrorBoundary from "./components/ErrorBoundary";
import InventoryHealth from "./components/InventoryHealth";
import InventoryHeatmap from "./components/InventoryHeatmap";
import InventoryTable from "./components/InventoryTable";
import NarrativeInsights from "./components/NarrativeInsights";
import ShipmentStatus from "./components/ShipmentStatus";
import SupplierRisk from "./components/SupplierRisk";
import SupplierRiskDistribution from "./components/SupplierRiskDistribution";
import ExportCsvButton from "./components/export/ExportCsvButton";
import ExportPdfButton from "./components/export/ExportPdfButton";
import Skeleton from "./components/Skeleton";
import KpiGrid from "./components/KpiGrid";
import OfflineBanner from "./components/OfflineBanner";
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { useWebSocket } from "./hooks/useWebSocket";
import { mockUser, type UserRole } from "./mocks/user";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { colors, radius, space } from "./tokens";
import type {
  AlertMessage,
  InventoryItem,
  WebSocketMessage,
} from "./types/forecast";
import { getKpiSnapshot, saveKpiSnapshot } from "./utils/kpiSnapshot";
const ForecastChart = lazy(() => import("./components/ForecastChart"));
const ForecastAccuracy = lazy(() => import("./components/ForecastAccuracy"));
const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === "true";
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

function roleFromUrl(): UserRole {
  // ?role= is a mock stand-in for authentication until real auth is implemented.
  const urlRole = new URLSearchParams(window.location.search).get("role");

  return urlRole === "ceo" || urlRole === "warehouse_manager"
    ? urlRole
    : mockUser.role;
}

function buildKpis(
  role: UserRole,
  inventory: InventoryItem[],
  alertCount: number,
) {
  const skus = inventory.length;
  const units = inventory.reduce(
    (total, item) => total + item.quantity_on_hand,
    0,
  );
  const lowStock = inventory.filter(
    (item) => item.needs_reorder,
  ).length;

  return role === "warehouse_manager"
    ? [
        { title: "Warehouse SKUs", value: skus },
        { title: "Warehouse Units", value: units },
        { title: "Reorder Items", value: lowStock },
        { title: "Warehouse Alerts", value: alertCount },
      ]
    : [
        { title: "SKUs", value: skus },
        { title: "Total Units", value: units },
        { title: "Low Stock", value: lowStock },
        { title: "Alerts", value: alertCount },
      ];
}

function DashboardApp({ onLogout }: { onLogout : () => void }) {
  const {
    data: dashboardData,
    loading: dashboardLoading,
    error: dashboardError,
    refetch,
  } = useDashboardData();
  const authSession = getAuthSession();
  const [role, setRole] = useState<UserRole>(
    USE_MOCK_AUTH
      ? roleFromUrl()
      : authSession?.role ?? "ceo",
  );
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [liveInventory, setLiveInventory] =
    useState<InventoryItem[]>(() => dashboardData?.dashboard.inventory ?? []);
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
  const [syncedData, setSyncedData] = useState(dashboardData);

  if (dashboardData !== syncedData) {
    setSyncedData(dashboardData);

    if (dashboardData) {
      setLiveInventory(dashboardData.dashboard.inventory);
    }
  }

  useEffect(() => {
    const updateFiltersFromUrl = () => {
      const params = new URLSearchParams(
        window.location.search,
      );
    if(USE_MOCK_AUTH) {
      setRole(roleFromUrl());
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
      ? mockUser.warehouse ?? ""
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

    const alertCount = alerts.length;

  // KPIs on screen follow the CEO's filters.
  const kpis = useMemo(
    () => buildKpis(role, baseFilteredInventory, alertCount),
    [role, baseFilteredInventory, alertCount],
  );

  // The offline snapshot must hold the role's UNFILTERED totals. Otherwise a
  // CEO who filtered to WH001 would later see WH001 numbers as company totals.
  const roleInventory = useMemo(
    () =>
      role === "warehouse_manager"
        ? liveInventory.filter((item) => item.warehouse_id === effectiveWarehouse)
        : liveInventory,
    [role, liveInventory, effectiveWarehouse],
  );

  const snapshotKpis = useMemo(
    () => buildKpis(role, roleInventory, alertCount),
    [role, roleInventory, alertCount],
  );

  const snapshotScope =
    role === "warehouse_manager" ? `${role}:${effectiveWarehouse}` : role;

// The saved snapshot is only needed when nothing is in memory
// (opened while offline, or the first load failed).
  const offlineSnapshot = useMemo(
    () =>
      !dashboardData && (!isOnline || dashboardError)
        ? getKpiSnapshot(snapshotScope)
        : null,
    [dashboardData, isOnline, dashboardError, snapshotScope],
  );

  const staleSince = useMemo(
    () =>
      !isOnline || dashboardError
        ? getKpiSnapshot(snapshotScope)?.savedAt ?? null
        : null,
    [isOnline, dashboardError, snapshotScope],
  );

  // Panels only show their own error state when there is nothing to show.
  const panelError = Boolean(dashboardError) && !dashboardData;
  const panelLoading = dashboardLoading && !dashboardData;

// savedAt = when the data was LOADED, not when a filter last changed.
  const loadedAt = useRef<{ data: unknown; at: string } | null>(null);

  useEffect(() => {
    if (!dashboardData || dashboardError) {
      return;
    }

    if (loadedAt.current?.data !== dashboardData) {
      loadedAt.current = {
        data: dashboardData,
        at: new Date().toISOString(),
      };
    }

    saveKpiSnapshot(snapshotScope, snapshotKpis, loadedAt.current.at);
  }, [dashboardData, dashboardError, snapshotScope, snapshotKpis]);

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
  const header = (
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
      <Button type="button" onClick={onLogout}>
        Logout
      </Button>
    </div>
  );

  if (!dashboardData && offlineSnapshot) {
    return (
      <div
        style={{
          background: colors.bg,
          minHeight: "100vh",
          padding: space.lg,
          boxSizing: "border-box",
        }}
      >
        {header}

        <OfflineBanner
          savedAt={offlineSnapshot.savedAt}
          isOnline={isOnline}
          hasServerError={Boolean(dashboardError)}
          onRetry={() => void refreshDashboardData()}
        />

        <KpiGrid
          kpis={offlineSnapshot.kpis}
          selectedKpi={selectedKpi}
          lowStockOnly={lowStockOnly}
          onSelect={handleKpiClick}
        />

        <p
          style={{
            color: colors.textMuted,
            marginTop: space.lg,
          }}
        >
          Charts and tables will load when the connection returns.
        </p>
      </div>
    );
  }

  if (dashboardLoading && !dashboardData) {
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

  if (dashboardError && !dashboardData) {
    return (
      <div
        role="alert"
        style={{
          background: colors.bg,
          minHeight: "100vh",
          padding: space.lg,
          color: colors.text,
        }}
      >
        <p style={{ margin:0, marginBottom: space.md }}>
          Failed to load dashboard data.
        </p>

        <button
          type="button"
          onClick={() => void refreshDashboardData()}
          style={{
            background: colors.primary,
            color: colors.text,
            border: "none",
            borderRadius: radius.sm,
            padding: `${space.sm}px ${space.md}px`,
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </div>
    );
  }
  if (role === "warehouse_manager" && !mockUser.warehouse) {
    return (
      <div
        style={{
          background: colors.bg,
          minHeight: "100vh",
          padding: space.lg,
          color: colors.text,
        }}
      >
        {header}

        <p>No warehouse is assigned to this user.</p>
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
        { header }

      <DashboardFilters
        filters={filters}
        onFilterChange={setFilters}
        lockedWarehouse={
          role === "warehouse_manager" ? effectiveWarehouse : undefined
        }
        inventory={dashboardData?.dashboard.inventory ?? []}
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
      {staleSince && (
        <OfflineBanner
          savedAt={staleSince}
          isOnline={isOnline}
          hasServerError={Boolean(dashboardError)}
          onRetry={() => void refreshDashboardData()}
        />
      )}
      <KpiGrid
        kpis={kpis}
        selectedKpi={selectedKpi}
        lowStockOnly={lowStockOnly}
        onSelect={handleKpiClick}
      />
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
              <Suspense fallback={<Skeleton />}>
                <Profiler
                  id="ForecastChart"
                  onRender={handleProfilerRender}
                >
                  <ForecastChart
                    startDate={filters.startDate}
                    endDate={filters.endDate}
                    data={dashboardData?.dashboard.forecast ?? []}
                    loading={panelLoading}
                    error={panelError}
                    onRetry={() => void refetch()}
                   />
                </Profiler>
              </Suspense>
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
          <Suspense fallback={<Skeleton />}>
            <ForecastAccuracy
              startDate={filters.startDate}
              endDate={filters.endDate}
              data={dashboardData?.dashboard.forecastAccuracy ?? []}
              loading={panelLoading}
              error={panelError}
              onRetry={() => void refetch()}
            />
          </Suspense>
        </ErrorBoundary>

        <ErrorBoundary>
          <InventoryHealth
            inventory={liveInventory}
            warehouse={effectiveWarehouse}
            category={filters.category}
          />
        </ErrorBoundary>

        {role === "ceo" && (
          <ErrorBoundary>
            <SupplierRisk
              supplierRisk={dashboardData?.dashboard.supplierRisk ?? []}
              loading={panelLoading}
              error={panelError}
              onRetry={() => void refetch()}
            />
          </ErrorBoundary>
        )}

        <ErrorBoundary>
          <ShipmentStatus
              shipmentStatus={dashboardData?.dashboard.shipmentStatus}
              loading={panelLoading}
              error={panelError}
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
              <SupplierRiskDistribution
                supplierRisk={dashboardData?.dashboard.supplierRisk ?? []}
                loading={panelLoading}
                error={panelError}
                onRetry={() => void refetch()}
               />
            </ErrorBoundary>
          </div>
        )}

      </div>
    </div>
  );
}
function App() {
  const [authSession, setAuthSession] = useState(getAuthSession);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    if (USE_MOCK_AUTH || !authSession) {
      return;
    }

    const refreshBeforeExpiry = async () => {
      try {
        const refreshedSession = await refreshAuthSession();
        setAuthSession(refreshedSession);
      } catch {
        clearAuthSession();
        setAuthSession(null);
        setAuthError("Your session has expired. Please sign in again.");
      }
    };

    const refreshAt = Math.max(
      getTokenExpiry(authSession.access_token) - Date.now() - 60_000,
      0,
    );

    const timer = window.setTimeout(() => {
      void refreshBeforeExpiry();
    }, refreshAt);

    return () => {
      window.clearTimeout(timer);
    };
  }, [authSession]);

  if (USE_MOCK_AUTH) {
    return <DashboardApp onLogout={() => {}} />;
  }

  if (!authSession) {
    return (
      <Login
        errorMessage={authError}
        onLogin={() => {
          setAuthError("");
          setAuthSession(getAuthSession());
        }}
      />
    );
  }

  return (
    <DashboardApp
      onLogout={async () => {
        await logout(authSession.refresh_token);
        clearAuthSession();
        setAuthSession(null);
      }}
    />
  );
}

export default App;