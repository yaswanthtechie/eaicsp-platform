import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ToastContext,
  type ToastItem,
  type ShowToastOptions,
} from "./ToastContext";
import { colors, shadows } from "../theme/tokens";

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({
  children,
}: ToastProviderProps) {
  const [toasts, setToasts] = useState<
    ToastItem[]
  >([]);

  const idRef = useRef(0);

  const removeToast = useCallback((id: number) => {
    setToasts((previous) =>
      previous.filter(
        (toast) => toast.id !== id
      )
    );
  }, []);

  const showToast = useCallback(
    ({
      title,
      description,
      variant = "info",
      duration = 3000,
    }: ShowToastOptions) => {
      const id = ++idRef.current;

      const toast: ToastItem = {
        id,
        title,
        description,
        variant,
        duration,
      };

      setToasts((previous) => [
        ...previous,
        toast,
      ]);

      window.setTimeout(() => {
        removeToast(id);
      }, duration);
    },
    [removeToast]
  );

  const value = useMemo(
    () => ({
      toasts,
      showToast,
      removeToast,
    }),
    [toasts, showToast, removeToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div
        style={{
          position: "fixed",
          top: 16,
          right: 16,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          zIndex: 9999,
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            style={{
              background: colors.surface,
              border: `1px solid ${colors.border}`,
              padding: "12px 16px",
              borderRadius: "8px",
              minWidth: "260px",
              boxShadow: shadows.md,
            }}
          >
            <strong>{toast.title}</strong>

            {toast.description && (
              <div style={{ marginTop: 4 }}>
                {toast.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}