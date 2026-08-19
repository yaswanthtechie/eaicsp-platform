import React from "react";
import { colors, spacing, radius } from "../theme/tokens";

type CardProps = {
  title?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
};

export function Card({
  title,
  actions,
  children,
}: CardProps) {
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        color: colors.text,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        width: "350px",
        boxSizing: "border-box",
      }}
    >
      {(title || actions) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: spacing.md,
          }}
        >
          {title && (
            <h3
              style={{
                margin: 0,
                fontSize: "18px",
              }}
            >
              {title}
            </h3>
          )}

          {actions && <div>{actions}</div>}
        </div>
      )}

      <div>{children}</div>
    </div>
  );
}