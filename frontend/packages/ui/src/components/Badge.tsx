
import { colors, space, radius } from "../tokens";

type BadgeProps = {
  status: "success" | "warning" | "danger" | "neutral";
  children: string;
};

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
      : colors.border;

  return (
    <span
      style={{
        backgroundColor,
        color: colors.text,
        padding: `${space.xs}px ${space.sm}px`,
        borderRadius: radius.lg,
        fontSize: "14px",
        fontWeight: 600,
        display: "inline-block",
      }}
    >
      {children}
    </span>
  );
}