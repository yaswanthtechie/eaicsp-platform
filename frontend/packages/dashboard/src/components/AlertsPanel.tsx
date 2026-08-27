import { useEffect, useRef, useState } from "react";
import { AlertBanner } from "../../../ui/src/components/AlertBanner";
import { Button } from "../../../ui/src/components/Button";
import { Spinner } from "../../../ui/src/components/Spinner";
import { colors, radius, space } from "../tokens";
import type { AlertMessage } from "../types/forecast";

interface AlertsPanelProps {
  alerts: AlertMessage[];
  connected: boolean;
  isConnecting: boolean;
  onRemove: (id: string) => void;
}

export default function AlertsPanel({
  alerts,
  connected,
  isConnecting,
  onRemove,
}: AlertsPanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [fadingAlerts, setFadingAlerts] = useState<string[]>([]);

  const timers = useRef<
    Record<string, ReturnType<typeof setTimeout>>
  >({});

  const removeTimers = useRef<
    Record<string, ReturnType<typeof setTimeout>>
  >({});

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    alerts.forEach((alert) => {
      if (timers.current[alert.id]) {
        return;
      }

      timers.current[alert.id] = setTimeout(() => {
        setFadingAlerts((prev) => {
          if (prev.includes(alert.id)) {
            return prev;
          }

          return [...prev, alert.id];
        });

        removeTimers.current[alert.id] = setTimeout(() => {
          onRemove(alert.id);

          setFadingAlerts((prev) =>
            prev.filter((id) => id !== alert.id)
          );

          delete timers.current[alert.id];
          delete removeTimers.current[alert.id];
        }, 500);
      }, 5000);
    });
  }, [alerts, onRemove]);

  useEffect(() => {
    const timersMap = timers.current;
    const removeTimersMap = removeTimers.current;

    return () => {
      Object.values(timersMap).forEach((timer) => {
        clearTimeout(timer);
      });

      Object.values(removeTimersMap).forEach((timer) => {
        clearTimeout(timer);
      });
    };
  }, []);

  const getAlertType = (
    severity: AlertMessage["severity"]
  ): "info" | "success" | "warning" | "danger" => {
    if (severity === "error") {
      return "danger";
    }

    if (severity === "warning") {
      return "warning";
    }

    return "info";
  };

  const getTitle = (type: AlertMessage["type"]) => {
    if (type === "low-stock") {
      return "Low Stock Item Alert";
    }

    if (type === "forecast-change") {
      return "Forecast Change";
    }

    return "System Status";
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString("en-GB");
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text
        }}
      >
        <Spinner size="md" />
        <span>Loading Live Alerts...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md
        }}
      >
        <h2 style={{ color: colors.text }}>
          Something went wrong in the alerts.
        </h2>

        <Button
          variant="danger"
          size="sm"
          onClick={() => setError(false)}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md
        }}
      >
        <h2 style={{ color: colors.text }}>
          No Alerts Available.
        </h2>
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        padding: space.md,
        borderRadius: radius.md
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: space.sm
        }}
      >
        <h2 style={{ color: colors.text }}>
          Live Alerts
        </h2>

        <span
          style={{
            fontSize: space.md,
            fontWeight: 500,
            color: isConnecting
              ? colors.warning
              : connected
              ? colors.success
              : colors.danger
          }}
        >
          {isConnecting
            ? "🟡 Connecting…"
            : connected
            ? "🟢 Connected"
            : "🔴 Disconnected"}
        </span>
      </div>

      {alerts.map((alert) => {
        const isFading = fadingAlerts.includes(alert.id);

        return (
          <div
            key={alert.id}
            style={{
              opacity: isFading ? 0 : 1,
              transition: "opacity 0.5s ease",
              pointerEvents: isFading ? "none" : "auto",
              marginBottom: space.sm
            }}
          >
            <AlertBanner
              type={getAlertType(alert.severity)}
              title={getTitle(alert.type)}
              message={`${alert.message} • ${formatTime(
                alert.timestamp
              )}`}
            />
          </div>
        );
      })}
    </div>
  );
}