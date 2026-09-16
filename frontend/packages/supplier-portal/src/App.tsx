import { useState } from "react";

import AppRoutes from "./routes/AppRoutes";
import OfflineBanner from "./components/OfflineBanner";
import NotificationToast from "./components/NotificationToast";
import ErrorBoundary from "./components/ErrorBoundary";

import { useOfflineActionSync } from "./hooks/useOfflineActionSync";
import { createNewPONotification } from "./utils/mockNotifications";

import type { Notification } from "./types/notification";

function App() {
  const [syncMessage, setSyncMessage] = useState("");
  const [notification, setNotification] =
    useState<Notification | null>(null);

  const handleSyncComplete = (count: number) => {
    const message =
      count === 1
        ? "1 action synced"
        : `${count} actions synced`;

    setSyncMessage(message);

    window.setTimeout(() => {
      setSyncMessage("");
    }, 3000);
  };

  const handleMockNewPO = () => {
    const newNotification =
      createNewPONotification("PO-1005");

    setNotification(newNotification);
  };

  useOfflineActionSync(handleSyncComplete);

  return (
    <ErrorBoundary>
      <OfflineBanner />

      {syncMessage && (
        <div
          role="status"
          style={{
            position: "fixed",
            top: "16px",
            right: "16px",
            zIndex: 1000,
            padding: "12px 16px",
            borderRadius: "6px",
            background: "var(--success)",
            color: "var(--text-on-primary)",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          {syncMessage}
        </div>
      )}

      <NotificationToast
        notification={notification}
        onClose={() => setNotification(null)}
      />

      <button
        type="button"
        onClick={handleMockNewPO}
        style={{
          position: "fixed",
          bottom: "16px",
          right: "16px",
          zIndex: 1000,
          padding: "10px 14px",
          borderRadius: "6px",
          border: "none",
          cursor: "pointer",
        }}
      >
        Test New PO Notification
      </button>

      <AppRoutes />
    </ErrorBoundary>
  );
}

export default App;