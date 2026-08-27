import { useCallback, useEffect, useState } from "react";
import AlertsPanel from "./components/AlertsPanel";
import ForecastChart from "./components/ForecastChart";
import InventoryHeatmap from "./components/InventoryHeatmap";
import InventoryTable from "./components/InventoryTable";
import { useWebSocket } from "./hooks/useWebSocket";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { colors, radius, space } from "./tokens";
import type { AlertMessage } from "./types/forecast";

function App() {
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);

  useEffect(() => {
    startMockWebSocketServer();
  }, []);

  const handleMessage = useCallback((alert: AlertMessage) => {
    setAlerts((prev) => [alert, ...prev]);
  }, []);

  const removeAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.filter((alert) => alert.id !== id)
    );
  }, []);

  const { connected, isConnecting } = useWebSocket({
    url: "ws://localhost:8080",
    onMessage: handleMessage,
    autoReconnect: true,
    maxRetries: 5,
  });

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
            <ForecastChart />
          </div>
        </div>

        <div className="alerts-section">
          <AlertsPanel
            alerts={alerts}
            connected={connected}
            isConnecting={isConnecting}
            onRemove={removeAlert}
          />
        </div>
      </div>

      <div
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
          <InventoryTable />
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
          <InventoryHeatmap />
        </div>
      </div>
    </div>
  );
}

export default App;