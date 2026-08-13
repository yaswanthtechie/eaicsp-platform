import {useCallback,useEffect,useState} from "react";

import AlertsPanel from "./components/AlertsPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import { startMockWebSocketServer } from "./mocks/wsServer";

import ForecastChart from "./components/ForecastChart";
import InventoryTable from "./components/InventoryTable";
import { colors } from "./tokens";

interface AlertMessage {
  id: string;
  type: "low-stock" | "forecast-change" | "system";
  severity: "error" | "warning" | "info";
  message: string;
  timestamp: string;
}

function App() {
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);

  useEffect(() => {
    startMockWebSocketServer();
  }, []);

  const handleMessage = useCallback(
    (alert: AlertMessage) => {
      setAlerts((prev) => [alert, ...prev]);
    },
    []
  );

  const removeAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.filter((alert) => alert.id !== id)
    );
  }, []);

  const { connected } = useWebSocket({
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: 20,
        }}
      >

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
          </div>
        </div>

        <AlertsPanel
          alerts={alerts}
          connected={connected}
          onRemove={removeAlert}
        />
      </div>
    </div>
  );
}

export default App;