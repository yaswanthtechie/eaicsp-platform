import React from "react";
import { colors, space, radius } from "../tokens";
import { Spinner } from "./Spinner";

type ButtonProps = {
  variant: "primary" | "secondary" | "danger";
  size: "sm" | "md";
  loading?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
};

export function Button({
  variant,
  size,
  loading = false,
  disabled = false,
  onClick,
  children,
}: ButtonProps) {
  const backgroundColor =
    variant === "primary"
      ? colors.primary
      : variant === "secondary"
      ? colors.surface
      : colors.danger;

  const textColor =
    variant === "secondary"
      ? colors.text
      : colors.textInverse;

  const padding =
    size === "sm"
      ? `${space.xs}px ${space.sm}px`
      : `${space.sm}px ${space.md}px`;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      style={{
        backgroundColor,
        color: textColor,
        padding,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        cursor: loading || disabled ? "not-allowed" : "pointer",
        opacity: loading || disabled ? 0.6 : 1,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: space.xs,
        fontWeight: 600,
      }}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
}
