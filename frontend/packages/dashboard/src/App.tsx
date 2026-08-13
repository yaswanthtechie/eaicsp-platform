import { useCallback, useEffect, useState } from "react";

import AlertsPanel from "./components/AlertsPanel";
import ForecastChart from "./components/ForecastChart";
import InventoryTable from "./components/InventoryTable";
import InventoryHeatmap from "./components/InventoryHeatmap";

import { useWebSocket } from "./hooks/useWebSocket";
import { startMockWebSocketServer } from "./mocks/wsServer";
import { colors } from "./tokens";

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
        padding: 20,
      }}
    >
      <div
        style={{
          background: colors.surface,
          padding: 20,
          borderRadius: 10,
          marginBottom: 20,
        }}
      >
        <h1
          style={{
            color: colors.text,
            textAlign: "center",
            margin: 0,
          }}
        >
          Executive Dashboard
        </h1>
      </div>

      <div className="dashboard-grid">
        <div>
          <div
            style={{
              background: colors.surface,
              padding: 20,
              borderRadius: 10,
              marginBottom: 20,
            }}
          >
            <ForecastChart />
          </div>

          <div
            style={{
              background: colors.surface,
              padding: 20,
              borderRadius: 10,
            }}
          >
            <InventoryTable />
            <InventoryHeatmap />
          </div>
        </div>

        <AlertsPanel
          alerts={alerts}
          connected={connected}
          isConnecting={isConnecting}
          onRemove={removeAlert}
        />
      </div>
    </div>
  );
}

export default App;