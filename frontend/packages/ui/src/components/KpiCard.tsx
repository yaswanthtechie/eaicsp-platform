import React from "react";
import { colors, space, radius } from "../tokens";

type KpiCardProps = {
  label: string;
  value: string;
  delta?: string;
};

export function KpiCard({
  label,
  value,
  delta,
}: KpiCardProps) {
  const deltaColor =
    delta === undefined
      ? colors.textMuted
      : delta.startsWith("-")
      ? colors.danger
      : colors.success;

  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: space.md,
        width: "100%",
        maxWidth: 250,
      }}
    >
      <p
        style={{
          margin: 0,
          color: colors.textMuted,
          fontSize: 14,
        }}
      >
        {label}
      </p>

      <h2
        style={{
          margin: `${space.sm}px 0`,
          color: colors.text,
        }}
      >
        {value}
      </h2>

      {delta && (
        <p
          style={{
            margin: 0,
            color: deltaColor,
            fontWeight: "bold",
          }}
        >
          {delta}
        </p>
      )}
    </div>
  );
}