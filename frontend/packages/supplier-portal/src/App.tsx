import { useState } from "react";
import AppRoutes from "./routes/AppRoutes";
import OfflineBanner from "./components/OfflineBanner";
import { useOfflineActionSync } from "./hooks/useOfflineActionSync";

function App() {
  const [syncMessage, setSyncMessage] = useState("");

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

  useOfflineActionSync(handleSyncComplete);

  return (
    <>
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

      <AppRoutes />
    </>
  );
}

export default App;