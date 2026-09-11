import { spacing, radius } from "../theme/tokens";

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
      ? "var(--color-text-secondary)"
      : delta >= 0
        ? "var(--color-success)"
        : "var(--color-danger)";

  const arrow =
    delta === undefined ? "" : delta >= 0 ? "▲" : "▼";

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: radius.md,
        padding: spacing.md,
        width: "100%",
        maxWidth: "250px",
      }}
    >
      <p
        style={{
          margin: 0,
          color: "var(--color-text-secondary)",
          fontSize: 14,
        }}
      >
        {label}
      </p>

      <h2
        style={{
          margin: `${spacing.sm} 0`,
          color: "var(--color-text)",
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