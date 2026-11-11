import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldAlert, AlertTriangle, Info, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { colors, radius, space } from "../tokens";
import type { AlertMessage } from "../types/forecast";
import Skeleton from "./Skeleton";

const MAX_VISIBLE_ALERTS = 2;
interface AlertsPanelProps {
  alerts: AlertMessage[];
  connected: boolean;
  isConnecting: boolean;
  failed: boolean;
  onRemove: (id: string) => void;
  onRetry?: () => void;
}

function normalizeSeverity(
  severity: AlertMessage["severity"],
): "critical" | "warning" | "info" | "success" {
  if (
    severity === "critical" ||
    severity === "warning" ||
    severity === "info" ||
    severity === "success"
  ) {
    return severity;
  }

  return "info";
}

export default function AlertsPanel({
  alerts,
  connected,
  isConnecting,
  failed,
  onRemove,
  onRetry,
}: AlertsPanelProps) {
  const [fadingAlerts, setFadingAlerts] = useState<string[]>([]);
  const [severityFilter, setSeverityFilter] = useState<
    "all" | "critical" | "warning" | "info"
  >("all");

  const severityOrder: Record<string, number> = {
    critical: 0,
    warning: 1,
    info: 2,
    success: 3,
  };

  const filteredAlerts = alerts
    .filter((alert) => {
      const severity = normalizeSeverity(alert.severity);

      return severityFilter === "all" || severity === severityFilter;
    })
    .sort(
      (a, b) =>
        (severityOrder[normalizeSeverity(a.severity)]) -
        (severityOrder[normalizeSeverity(b.severity)]),
    );

  const visibleAlerts = filteredAlerts.slice(0, MAX_VISIBLE_ALERTS);

  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const removeTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );

  useEffect(() => {
    alerts.slice(0, MAX_VISIBLE_ALERTS).forEach((alert) => {
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

          setFadingAlerts((prev) => prev.filter((id) => id !== alert.id));

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

  const getSeverityBadge = (severity: AlertMessage["severity"]) => {
    switch (severity) {
      case "critical":
        return {
          label: "Critical",
          icon: ShieldAlert,
          color: colors.danger,
        };

      case "warning":
        return {
          label: "Warning",
          icon: AlertTriangle,
          color: colors.warning,
        };

      case "success":
        return {
          label: "Success",
          icon: CheckCircle2,
          color: colors.success,
        };

      case "info":
      default:
        return {
          label: "Info",
          icon: Info,
          color: colors.info,
        };
    }
  };

  const getTitle = (alert: AlertMessage) => {
    if (alert.title) {
      return alert.title;
    }

    if (alert.type === "low-stock") {
      return "Low Stock Item Alert";
    }

    if (alert.type === "forecast-change") {
      return "Forecast Change";
    }

    if (alert.type === "cold-chain-anomaly") {
      return "Cold-Chain Anomaly";
    }

    if (alert.type === "supplier-risk-change") {
      return "Supplier Risk Change";
    }

    if (alert.type === "shipment-eta-update") {
      return "Shipment ETA Update";
    }

    if (alert.type === "forecast-batch-completed") {
      return "Forecast Batch Done";
    }

    if (alert.type === "data-pipeline-completed") {
      return "Data Ingestion Sync";
    }

    return "System Status";
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString("en-GB");
  };

  if (isConnecting) {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-label="Loading live alerts"
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
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
        </div>

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
        </div>

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
        </div>
      </div>
    );
  }

  if (failed) {
    return (
      <div
        role="alert"
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

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              marginTop: space.md,
              background: colors.primary,
              color: colors.bg,
              border: "none",
              borderRadius: radius.sm,
              padding: `${space.sm}px ${space.md}px`,
              cursor: "pointer",
            }}
          >
            Retry connection
          </button>
        )}
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
    <Card aria-label="Live alerts">
      <CardHeader>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: space.sm,
          }}
        >
          <CardTitle>Live Alerts</CardTitle>
          <Badge
            variant={isConnecting ? "secondary" : "outline"}
            className="border-transparent"
            style={{
              background: connected
                ? colors.successAlpha12
                : colors.dangerAlpha12,
              color: connected ? colors.success : colors.danger,
            }}
          >
            {isConnecting
              ? "Connecting…"
              : connected
                ? "Connected"
                : "Disconnected"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div
          style={{
            display: "flex",
            gap: space.sm,
            flexWrap: "wrap",
            marginBottom: space.md,
          }}
        >
          {(["all", "critical", "warning", "info"] as const).map((filter) => (
            <button
              key={filter}
              type="button"
              onClick={() => setSeverityFilter(filter)}
              aria-pressed={severityFilter === filter}
              style={{
                padding: `${space.xs}px ${space.md}px`,
                borderRadius: radius.sm,
                border: `1px solid ${
                  severityFilter === filter ? colors.primary : colors.border
                }`,
                background:
                  severityFilter === filter ? colors.primary : colors.surface,
                color: severityFilter === filter ? colors.bg : colors.text,
                cursor: "pointer",
                fontWeight: 600,
                textTransform: "capitalize",
              }}
            >
              {filter === "all" ? "All" : filter}
            </button>
          ))}
        </div>
        {visibleAlerts.length === 0 ? (
          <p style={{ color: colors.textMuted }}>
            No {severityFilter === "all" ? "" : severityFilter + " "}alerts
            available.
          </p>
        ) : (
          visibleAlerts.map((alert) => {
            const isFading = fadingAlerts.includes(alert.id);
            const severityBadge = getSeverityBadge(
              normalizeSeverity(alert.severity),
            );
            const SeverityIcon = severityBadge.icon;

            return (
              <div
                key={alert.id}
                role="article"
                aria-label={`${getTitle(alert)}: ${alert.message}`}
                style={{
                  opacity: isFading ? 0 : 1,
                  transition: "opacity 0.5s ease",
                  pointerEvents: isFading ? "none" : "auto",
                  marginBottom: space.sm,
                  padding: space.md,
                  borderRadius: radius.md,
                  borderLeft: `4px solid ${severityBadge.color}`,
                  background: colors.bg,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: space.sm,
                    marginBottom: space.xs,
                  }}
                >
                  <h3
                    style={{
                      margin: 0,
                      color: colors.text,
                      fontSize: "15px",
                    }}
                  >
                    {getTitle(alert)}
                  </h3>
                  <Badge
                    className="px-3 py-1.5 text-base font-semibold"
                    style={{
                      color: severityBadge.color,
                      backgroundColor: colors.surface,
                      borderColor: severityBadge.color,
                    }}
                  >
                    <SeverityIcon size={20} />
                    {severityBadge.label}
                  </Badge>
                </div>

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
          })
        )}
      </CardContent>
    </Card>
  );
}
