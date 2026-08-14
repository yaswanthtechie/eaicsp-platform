import { Card } from "./Card";
import { Button } from "./Button";
import { Badge } from "./Badge";
import { colors, spacing } from "../theme/tokens";

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
    info: colors.info,
    success: colors.success,
    warning: colors.warning,
    danger: colors.danger,
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
                color: colors.gray900,
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
              color: colors.gray500,
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