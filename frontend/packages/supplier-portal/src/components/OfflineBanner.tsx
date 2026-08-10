import { useOnlineStatus } from "../hooks/useOnlineStatus";

const OfflineBanner = () => {
  const isOnline = useOnlineStatus();

  if (isOnline) {
    return null;
  }

  return (
    <div
      role="alert"
      style={{
        width: "100%",
        padding: "10px 16px",
        textAlign: "center",
        background: "#EF4444",
        color: "#FFFFFF",
        fontSize: "14px",
        fontWeight: 600,
        boxSizing: "border-box",
      }}
    >
      You are currently offline. Some features may not be available.
    </div>
  );
};

export default OfflineBanner;