import { useEffect, useRef } from "react";
import { colors, space, radius, statusColors } from "../tokens";

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
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const timer = setTimeout(() => {
      onCloseRef.current();
    }, duration);

    return () => clearTimeout(timer);
  }, [open, duration]);

  if (!open) {
    return null;
  }

  const backgroundColor =
    type === "info"
      ? colors.primary
      : statusColors[type];

  return (
    <div
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        backgroundColor,
        color: colors.textInverse,
        padding: `${space.md}px ${space.lg}px`,
        borderRadius: radius.md,
        boxShadow: colors.shadow,
        zIndex: 2000,
        fontWeight: "bold",
      }}
    >
      {message}
    </div>
  );
}