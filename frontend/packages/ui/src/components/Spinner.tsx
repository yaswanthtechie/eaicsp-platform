import { colors } from "../tokens";

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
    <>
      <style>
        {`
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
        `}
      </style>

      <div
        style={{
          width: spinnerSize,
          height: spinnerSize,
          border: `4px solid ${colors.border}`,
          borderTop: `4px solid ${colors.primary}`,
          borderRadius: "50%",
          animation: "spin 1s linear infinite",
        }}
      />
    </>
  );
}