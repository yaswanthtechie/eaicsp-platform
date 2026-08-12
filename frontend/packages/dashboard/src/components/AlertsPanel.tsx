import { useEffect, useRef, useState } from "react";
import { colors } from "../tokens";

interface AlertMessage {
  id: string;
  type: "low-stock" | "forecast-change" | "system";
  severity: "error" | "warning" | "info";
  message: string;
  timestamp: string;
}

interface AlertsPanelProps {
  alerts: AlertMessage[];
  connected: boolean;
  onRemove: (id: string) => void;
}

export default function AlertsPanel({
  alerts,
  connected,
  onRemove,
}: AlertsPanelProps) {
  const [fadingAlerts, setFadingAlerts] = useState<string[]>([]);
  const timers = useRef<
    Record<string, ReturnType<typeof setTimeout>>
  >({});

  useEffect(() => {
    alerts.forEach((alert) => {
      if (timers.current[alert.id]) {
        return;
      }

      timers.current[alert.id] = setTimeout(() => {
        setFadingAlerts((prev) => [...prev, alert.id]);

        setTimeout(() => {
          onRemove(alert.id);

          setFadingAlerts((prev) =>
            prev.filter((id) => id !== alert.id)
          );

          delete timers.current[alert.id];
        }, 500);
      }, 5000);
    });
  }, [alerts, onRemove]);

  const getColor = (
    severity: AlertMessage["severity"]
  ) => {
    if (severity === "error") {
      return colors.danger;
    }

    if (severity === "warning") {
      return colors.warning;
    }

    return colors.primary;
  };

  const getTitle = (
    type: AlertMessage["type"]
  ) => {
    if (type === "low-stock") {
      return "Low Stock Item Alert";
    }

    if (type === "forecast-change") {
      return "Forecast Change";
    }

    return "System Status";
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };
  

  return (
    <div
      style={{
        background: colors.surface,
        padding: 20,
        borderRadius: 10,
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2
          style={{
            color: colors.text,
            margin: 0,
          }}
        >
          Live Alerts
        </h2>

        <span
          style={{
            color: connected
              ? colors.success
              : colors.danger,
          }}
        >
          {connected ? "🟢 Connected" : "🔴 Disconnected"}
        </span>
      </div>

      {alerts.length === 0 ? (
        <p style={{ color: colors.textMuted }}>
          No recent alerts available
        </p>
      ) : (
        alerts.map((alert) => {
          const color = getColor(alert.severity);
          const isFading = fadingAlerts.includes(alert.id);

          return (
            <div
              key={alert.id}
              style={{
                borderLeft: `4px solid ${color}`,
                background: colors.bg,
                padding: 12,
                marginBottom: 10,
                borderRadius: 6,
                opacity: isFading ? 0 : 1,
                transition: "opacity 0.5s ease",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <strong style={{ color }}>
                  {getTitle(alert.type)}
                </strong>

                <span
                  style={{
                    color: colors.textMuted,
                    fontSize: 12,
                  }}
                >
                  {formatTime(alert.timestamp)}
                </span>
              </div>

              <div
                style={{
                  color,
                  fontSize: 12,
                  marginTop: 5,
                  textTransform: "uppercase",
                }}
              >
                {alert.severity}
              </div>

              <p
                style={{
                  color: colors.text,
                  margin: "6px 0 0",
                }}
              >
                {alert.message}
              </p>
            </div>
          );
        })
      )}
    </div>
  );
}