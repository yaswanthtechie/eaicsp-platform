import "./Spinner.css";

export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
}

export function Spinner({
  size = "md",
}: SpinnerProps) {
  const spinnerSize =
    size === "sm"
      ? 20
      : size === "md"
        ? 35
        : 50;

  return (
    <div
      role="status"
      aria-label="Loading"
      style={{
        width: spinnerSize,
        height: spinnerSize,
        border: "4px solid var(--color-border)",
        borderTop: "4px solid var(--color-primary)",
        borderRadius: "50%",
        animation: "spin 1s linear infinite",
      }}
    />
  );
}