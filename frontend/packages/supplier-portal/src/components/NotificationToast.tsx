import type { Notification } from "../types/notification";

interface NotificationToastProps {
  notification: Notification | null;
  onClose: () => void;
}

const NotificationToast = ({
  notification,
  onClose,
}: NotificationToastProps) => {
  if (!notification) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        top: "16px",
        right: "16px",
        zIndex: 1100,
        width: "min(360px, calc(100vw - 32px))",
        padding: "16px",
        borderRadius: "8px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
      }}
    >
      <strong>{notification.title}</strong>

      <p style={{ margin: "8px 0" }}>
        {notification.message}
      </p>

      <button type="button" onClick={onClose}>
        Dismiss
      </button>
    </div>
  );
};

export default NotificationToast;