import { useEffect, useRef, useState } from "react";
import { colors, radius, space } from "../tokens";
import type { AlertMessage } from "../types/forecast";
import Skeleton from "./Skeleton";
interface AlertsPanelProps {
  alerts: AlertMessage[];
  connected: boolean;
  isConnecting: boolean;
  failed: boolean;
  onRemove: (id: string) => void;
}

export default function AlertsPanel({
  alerts,
  connected,
  isConnecting,
  failed,
  onRemove,
}: AlertsPanelProps) {
  const [fadingAlerts, setFadingAlerts] = useState<string[]>([]);

  const timers = useRef<
    Record<string, ReturnType<typeof setTimeout>>
  >({});

  const removeTimers = useRef<
    Record<string, ReturnType<typeof setTimeout>>
  >({});

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

  const getAlertColor = (
    type: "info" | "success" | "warning" | "danger"
  ) => {
    if (type === "danger") {
      return colors.danger;
    }

    if (type === "warning") {
      return colors.warning;
    }

    if (type === "success") {
      return colors.success;
    }

    return colors.primary;
  };

  if (isConnecting) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
        }}
      >
        <Skeleton width="30%" height={28} />

        <div style={{ marginTop: space.md }}>
          <Skeleton width="25%" height={18} />
        </div>

        <div style={{ marginTop: space.md }}>
          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />
        </div>

        <div style={{ marginTop: space.sm }}>
          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />
        </div>

        <div style={{ marginTop: space.sm }}>
          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />
        </div>
      </div>
    );
  }

  if (failed) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
          border: `1px solid ${colors.danger}`,
        }}
      >
        <h2
          style={{
            color: colors.text,
            margin: 0,
            marginBottom: space.sm,
          }}
        >
          Unable to connect to the alerts service.
        </h2>

        <p
          style={{
            color: colors.textMuted,
            margin: 0,
          }}
        >
          Connection failed after multiple retry attempts.
        </p>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
        }}
      >
        <h2
          style={{
            color: colors.text,
            margin: 0,
          }}
        >
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
        borderRadius: radius.md,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: space.sm,
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
            fontSize: space.md,
            fontWeight: 500,
            color: isConnecting
              ? colors.warning
              : connected
              ? colors.success
              : colors.danger,
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
        const alertType = getAlertType(alert.severity);
        const alertColor = getAlertColor(alertType);

        return (
          <div
            key={alert.id}
            style={{
              opacity: isFading ? 0 : 1,
              transition: "opacity 0.5s ease",
              pointerEvents: isFading ? "none" : "auto",
              marginBottom: space.sm,
              padding: space.md,
              borderRadius: radius.md,
              borderLeft: `4px solid ${alertColor}`,
              background: colors.bg,
            }}
          >
            <h3
              style={{
                margin: 0,
                marginBottom: space.xs,
                color: colors.text,
                fontSize: "15px",
              }}
            >
              {getTitle(alert.type)}
            </h3>

            <p
              style={{
                margin: 0,
                color: colors.textMuted,
                fontSize: "14px",
                lineHeight: 1.5,
              }}
            >
              {alert.message}
            </p>

            <span
              style={{
                display: "block",
                marginTop: space.xs,
                color: colors.textMuted,
                fontSize: "12px",
              }}
            >
              {formatTime(alert.timestamp)}
            </span>
          </div>
        );
      })}
    </div>
  );
}