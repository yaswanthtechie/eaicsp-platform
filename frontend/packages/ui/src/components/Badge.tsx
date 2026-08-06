import { colors, spacing, radius } from "../theme/tokens";

export interface BadgeProps {
  status: "info" | "success" | "warning" | "danger" | "neutral";
  children: React.ReactNode;
}

export function Badge({
  status,
  children,
}: BadgeProps) {
  const backgroundColor =
    status === "success"
      ? colors.success
      : status === "warning"
      ? colors.warning
      : status === "danger"
      ? colors.danger
      : status === "info"
      ? colors.info
      : colors.gray200;

  const textColor =
    status === "neutral"
      ? colors.gray900
      : colors.white;

  return (
    <span
      style={{
        backgroundColor,
        color: textColor,
        padding: `${spacing.xs} ${spacing.sm}`,
        borderRadius: radius.lg,
        fontSize: 14,
        fontWeight: 600,
        display: "inline-block",
      }}
    >
      {children}
    </span>
  );
}