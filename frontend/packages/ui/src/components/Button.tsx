import React from "react";

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
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
    >
      {loading ? "Loading..." : children}
    </button>
  );
}
