import { useEffect } from "react";
import { colors, space, radius } from "../tokens";

export interface ToastProps {
  open: boolean;
  message: string;
  type: "success" | "warning" | "danger" | "info";
  duration?: number;
  onClose: () => void;
}

export function Toast({
  open,
  message,
  type,
  duration = 3000,
  onClose,
}: ToastProps) {
  useEffect(() => {
    if (!open) return;

    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [open, duration, onClose]);

  if (!open) {
    return null;
  }

  const backgroundColor =
    type === "success"
      ? colors.success
      : type === "warning"
      ? colors.warning
      : type === "danger"
      ? colors.danger
      : colors.primary;

  return (
    <div
      style={{
        position: "fixed",
        top: "20px",
        right: "20px",
        backgroundColor,
        color: "#fff",
        padding: `${space.md}px ${space.lg}px`,
        borderRadius: radius.md,
        boxShadow: "0 4px 10px rgba(0,0,0,0.2)",
        zIndex: 2000,
        fontWeight: "bold",
      }}
    >
      {message}
    </div>
  );
}