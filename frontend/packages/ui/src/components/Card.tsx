import React from "react";
import { spacing, radius } from "../theme/tokens";

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
        backgroundColor: "var(--color-surface)",
        color: "var(--color-text)",
        border: "1px solid var(--color-border)",
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