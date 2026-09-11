import { spacing, radius } from "../theme/tokens";

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
      ? "var(--color-success)"
      : status === "warning"
        ? "var(--color-warning)"
        : status === "danger"
          ? "var(--color-danger)"
          : status === "info"
            ? "var(--color-info)"
            : "var(--color-muted)";

  const textColor =
    status === "neutral"
      ? "var(--color-text)"
      : "var(--color-white)";

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