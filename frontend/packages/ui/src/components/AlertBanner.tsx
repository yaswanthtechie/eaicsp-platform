import { Card } from "./Card";
import { Button } from "./Button";
import { Badge } from "./Badge";
import { spacing } from "../theme/tokens";

export interface AlertBannerProps {
  type?: "info" | "success" | "warning" | "danger";
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function AlertBanner({
  type = "info",
  title,
  message,
  actionLabel,
  onAction,
}: AlertBannerProps) {
  const borderColor = {
    info: "var(--color-info)",
    success: "var(--color-success)",
    warning: "var(--color-warning)",
    danger: "var(--color-danger)",
  }[type];

  const badgeLabel = {
    info: "Info",
    success: "Success",
    warning: "Warning",
    danger: "Danger",
  }[type];

  return (
    <Card>
      <div
        style={{
          borderLeft: `6px solid ${borderColor}`,
          padding: spacing.md,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: spacing.md,
        }}
      >
        <div style={{ flex: 1 }}>
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: spacing.xs,
            }}
          >
            <h3
              style={{
                margin: 0,
                color: "var(--color-text)",
              }}
            >
              {title}
            </h3>

            <Badge status={type}>
              {badgeLabel}
            </Badge>
          </div>

          {/* Message */}
          <p
            style={{
              margin: 0,
              color: "var(--color-text-secondary)",
            }}
          >
            {message}
          </p>
        </div>

        {actionLabel && onAction && (
          <Button
            variant="primary"
            size="sm"
            onClick={onAction}
          >
            {actionLabel}
          </Button>
        )}
      </div>
    </Card>
  );
}