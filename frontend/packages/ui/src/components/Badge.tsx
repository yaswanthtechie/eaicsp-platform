import { colors, space, radius, statusColors } from "../tokens";

type BadgeProps = {
  status: "success" | "warning" | "danger" | "neutral";
  children: string;
};

export function Badge({
  status,
  children,
}: BadgeProps) {
  const backgroundColor = statusColors[status];

  return (
    <span
      style={{
        backgroundColor,
        color:
          status === "neutral"
            ? colors.text
            : colors.textInverse,
        padding: `${space.xs}px ${space.sm}px`,
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