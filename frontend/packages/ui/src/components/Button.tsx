
import type { ReactNode } from "react";
import { spacing, radius } from "../theme/tokens";
import { Spinner } from "./Spinner";

export type ButtonProps = {
  variant?: "primary" | "secondary" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: () => void;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  type = "button",
  onClick,
  children,
}: ButtonProps) {
  const backgroundColor =
    variant === "primary"
      ? "var(--color-primary)"
      : variant === "secondary"
        ? "var(--color-muted)"
        : "var(--color-danger)";

  const textColor =
    variant === "secondary"
      ? "var(--color-text)"
      : "var(--color-white)";

  const padding =
    size === "sm"
      ? `${spacing.xs} ${spacing.sm}`
      : `${spacing.sm} ${spacing.md}`;

return (
  <button
    type={type}
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        backgroundColor,
        color: textColor,
        padding,
        border: "1px solid var(--color-border)",
        borderRadius: radius.md,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.6 : 1,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: spacing.xs,
        fontWeight: 600,
      }}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
}
