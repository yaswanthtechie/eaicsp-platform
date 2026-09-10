import { colors, spacing, radius } from "../theme/tokens";

export interface KpiCardProps {
  label: string;
  value: string | number;
  delta?: number;
}

export function KpiCard({
  label,
  value,
  delta,
}: KpiCardProps) {
  const deltaColor =
    delta === undefined
      ? colors.gray500
      : delta >= 0
      ? colors.success
      : colors.danger;

  const arrow =
    delta === undefined ? "" : delta >= 0 ? "▲" : "▼";

  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        width: "100%",
        maxWidth: "250px",
      }}
    >
      <p
        style={{
          margin: 0,
          color: colors.gray500,
          fontSize: 14,
        }}
      >
        {label}
      </p>

      <h2
        style={{
          margin: `${spacing.sm} 0`,
          color: colors.text,
        }}
      >
        {value}
      </h2>

      {delta !== undefined && (
        <p
          style={{
            margin: 0,
            color: deltaColor,
            fontWeight: 600,
          }}
        >
          {arrow} {delta >= 0 ? `+${delta}%` : `${delta}%`}
        </p>
      )}
    </div>
  );
}