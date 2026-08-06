import { useEffect, useRef } from "react";
import "./Toast.css";

export type ToastVariant =
  | "success"
  | "error"
  | "warning"
  | "info";

export interface ToastProps {
  id: number;
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
  onClose: (id: number) => void;
}

export function Toast({
  id,
  title,
  description,
  variant = "info",
  duration = 3000,
  onClose,
}: ToastProps) {
  const timeoutRef = useRef<number | undefined>(undefined);

  const startTimer = () => {
    timeoutRef.current = window.setTimeout(() => {
      onClose(id);
    }, duration);
  };

  const clearTimer = () => {
    if (timeoutRef.current !== undefined) {
      window.clearTimeout(timeoutRef.current);
    }
  };

  useEffect(() => {
    startTimer();

    return () => {
      clearTimer();
    };
  }, []);

  return (
    <div
      className={`toast toast-${variant}`}
      role="alert"
      onMouseEnter={clearTimer}
      onMouseLeave={startTimer}
    >
      <div className="toast-content">
        <h4 className="toast-title">
          {title}
        </h4>

        {description && (
          <p className="toast-description">
            {description}
          </p>
        )}
      </div>

      <button
        type="button"
        className="toast-close"
        aria-label="Close notification"
        onClick={() => onClose(id)}
      >
        ×
      </button>
    </div>
  );
}