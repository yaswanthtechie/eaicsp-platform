import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@base-ui/react/dialog";
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle2,
  X,
} from "lucide-react";
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

// Payload fields defined by the six supported WebSocket event types.
const EVENT_PAYLOAD_FIELDS: Record<string, string[]> = {
  "inventory.stock.low": [
    "sku_id",
    "warehouse_id",
    "quantity_on_hand",
    "reorder_point",
    "safety_stock",
    "avg_daily_demand",
  ],

  "iot.anomaly.detected": [
    "episode_id",
    "sensor_id",
    "warehouse_id",
    "severity",
    "message",
    "window_start",
    "window_end",
    "first_flag_time",
    "confirmed_time",
    "peak_time",
    "peak_score",
    "threshold",
    "n_flagged",
    "severe",
    "closed_by",
    "top_features",
    "model_version",
  ],

  "supplierrisk.score.changed": [
    "supplier",
    "supplier_id",
    "previous_tier",
    "new_tier",
    "risk_score",
    "supporting_articles",
    "evidence_count",
    "explanation",
  ],

  "eta.shipment.predicted": [
    "shipment_id",
    "po_number",
    "eta_days",
    "confidence_low",
    "confidence_high",
    "model_version",
    "predicted_at",
    "top_features",
  ],

  "forecast.batch.completed": [
    "run_id",
    "model_version",
    "granularity",
    "sku_count",
    "warehouse_count",
    "horizon",
    "completed_at",
    "status",
    "metrics",
    "duration_seconds",
    "destination_mart",
    "message",
  ],

  "data.pipeline.completed": [
    "run_id",
    "status",
    "batches_seen",
    "rows_inserted",
    "rows_updated",
    "rows_rejected",
    "task_states",
    "duration_seconds",
    "pipeline_name",
    "message",
  ],
};

function formatFieldLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatFieldValue(value: unknown): string {
  if (value === undefined || value === null || value === "") {
    return "Not available";
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2) ?? "Not available";
  }

  return String(value);
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

function AlertPayloadDetails({ alert }: { alert: AlertMessage }) {
  const eventType = alert.eventType ?? "";
  const payload = alert.payload ?? {};

  const fields = EVENT_PAYLOAD_FIELDS[eventType];

  // Known event: display all contract fields.
  // Unknown event: display whatever payload keys are available.
  const displayedFields: [string, unknown][] = fields
    ? fields.map((key): [string, unknown] => [key, payload[key]])
    : Object.entries(payload);

  if (displayedFields.length === 0) {
    return (
      <p style={{ color: colors.textMuted }}>No event details available.</p>
    );
  }

  return (
    <div style={{ display: "grid", gap: space.sm }}>
      {displayedFields.map(([key, value]) => (
        <div
          key={key}
          style={{
            padding: space.sm,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
            background: colors.bg,
          }}
        >
          <p
            style={{
              color: colors.textMuted,
              fontSize: "12px",
              margin: 0,
              marginBottom: space.xs,
            }}
          >
            {formatFieldLabel(key)}
          </p>

          <pre
            style={{
              color: colors.text,
              fontSize: "13px",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              margin: 0,
              fontFamily: "inherit",
            }}
          >
            {formatFieldValue(value)}
          </pre>
        </div>
      ))}
    </div>
  );
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

  const [selectedAlert, setSelectedAlert] = useState<AlertMessage | null>(null);
  const alertTriggerRef = useRef<HTMLElement | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const removeTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );

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
        severityOrder[normalizeSeverity(a.severity)] -
        severityOrder[normalizeSeverity(b.severity)],
    );

  const visibleAlerts = filteredAlerts.slice(0, MAX_VISIBLE_ALERTS);

  const openAlert = (alert: AlertMessage, trigger: HTMLElement) => {
    alertTriggerRef.current = trigger;
    setSelectedAlert(alert);
  };

  const closeAlert = () => {
    setSelectedAlert(null);

    requestAnimationFrame(() => {
      alertTriggerRef.current?.focus();
    });
  };

  // C5: Auto-dismiss only alerts that are actually visible.
  useEffect(() => {
    visibleAlerts.forEach((alert) => {
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
  }, [visibleAlerts, onRemove]);

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
    <Dialog.Root
      open={Boolean(selectedAlert)}
      onOpenChange={(open) => {
        if (!open) {
          closeAlert();
        }
      }}
    >
      <>
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
              {(["all", "critical", "warning", "info"] as const).map(
                (filter) => (
                  <button
                    key={filter}
                    type="button"
                    onClick={() => setSeverityFilter(filter)}
                    aria-pressed={severityFilter === filter}
                    style={{
                      padding: `${space.xs}px ${space.md}px`,
                      borderRadius: radius.sm,
                      border: `1px solid ${
                        severityFilter === filter
                          ? colors.primary
                          : colors.border
                      }`,
                      background:
                        severityFilter === filter
                          ? colors.primary
                          : colors.surface,
                      color:
                        severityFilter === filter ? colors.bg : colors.text,
                      cursor: "pointer",
                      fontWeight: 600,
                      textTransform: "capitalize",
                    }}
                  >
                    {filter === "all" ? "All" : filter}
                  </button>
                ),
              )}
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
                    role="button"
                    tabIndex={isFading ? -1 : 0}
                    aria-haspopup="dialog"
                    aria-label={`${getTitle(alert)}: ${alert.message}. Press Enter to view details`}
                    onClick={(event) => openAlert(alert, event.currentTarget)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openAlert(alert, event.currentTarget);
                      }
                    }}
                    style={{
                      opacity: isFading ? 0 : 1,
                      transition: "opacity 0.5s ease",
                      pointerEvents: isFading ? "none" : "auto",
                      marginBottom: space.sm,
                      padding: space.md,
                      borderRadius: radius.md,
                      borderLeft: `4px solid ${severityBadge.color}`,
                      background: colors.bg,
                      cursor: "pointer",
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

        {/* C6: Right-side alert details drawer */}
        <Dialog.Portal>
          <Dialog.Backdrop
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.55)",
              zIndex: 100,
            }}
          />

          <Dialog.Popup
            style={{
              position: "fixed",
              top: 0,
              right: 0,
              bottom: 0,
              width: "min(520px, 100%)",
              overflowY: "auto",
              padding: space.lg,
              background: colors.surface,
              borderLeft: `1px solid ${colors.border}`,
              color: colors.text,
              zIndex: 101,
              outline: "none",
            }}
          >
            {selectedAlert && (
              <>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: space.md,
                    marginBottom: space.lg,
                  }}
                >
                  <div>
                    <Dialog.Title
                      style={{
                        fontSize: "20px",
                        fontWeight: 700,
                        margin: 0,
                      }}
                    >
                      Alert Details
                    </Dialog.Title>

                    <Dialog.Description
                      style={{
                        color: colors.textMuted,
                        fontSize: "13px",
                        marginTop: space.xs,
                      }}
                    >
                      Details explaining why this alert was generated.
                    </Dialog.Description>
                  </div>

                  <button
                    type="button"
                    aria-label="Close alert details"
                    onClick={closeAlert}
                    style={{
                      border: `1px solid ${colors.border}`,
                      borderRadius: radius.sm,
                      background: colors.bg,
                      color: colors.text,
                      padding: space.sm,
                      cursor: "pointer",
                    }}
                  >
                    <X size={20} />
                  </button>
                </div>

                <h3 style={{ margin: 0, marginBottom: space.sm }}>
                  {getTitle(selectedAlert)}
                </h3>

                <p
                  style={{
                    color: colors.textMuted,
                    lineHeight: 1.5,
                  }}
                >
                  {selectedAlert.message}
                </p>

                <div
                  style={{
                    display: "grid",
                    gap: space.md,
                    marginTop: space.lg,
                    marginBottom: space.lg,
                  }}
                >
                  <div>
                    <strong>Severity</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {
                        getSeverityBadge(
                          normalizeSeverity(selectedAlert.severity),
                        ).label
                      }
                    </p>
                  </div>

                  <div>
                    <strong>Timestamp</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {selectedAlert.timestamp
                        ? new Date(selectedAlert.timestamp).toLocaleString()
                        : "Not available"}
                    </p>
                  </div>

                  <div>
                    <strong>Event Type</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {selectedAlert.eventType || "Not available"}
                    </p>
                  </div>

                  <div>
                    <strong>Producer</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {selectedAlert.producer || "Not available"}
                    </p>
                  </div>

                  <div>
                    <strong>Event Version</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {selectedAlert.eventVersion ?? "Not available"}
                    </p>
                  </div>

                  <div>
                    <strong>Trace ID</strong>
                    <p style={{ margin: 0, color: colors.textMuted }}>
                      {selectedAlert.traceId || "Not available"}
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    borderTop: `1px solid ${colors.border}`,
                    paddingTop: space.md,
                  }}
                >
                  <h3 style={{ marginTop: 0, marginBottom: space.md }}>
                    Event Payload
                  </h3>

                  <AlertPayloadDetails alert={selectedAlert} />
                </div>
              </>
            )}
          </Dialog.Popup>
        </Dialog.Portal>
      </>
    </Dialog.Root>
  );
}
