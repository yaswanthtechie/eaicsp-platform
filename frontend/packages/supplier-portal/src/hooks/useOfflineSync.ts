import { useEffect } from "react";
import { syncOfflineActions } from "../utils/offlineSync";

export function useOfflineSync(
  handler: (
    type: string,
    payload: Record<string, unknown>
  ) => Promise<void>
) {
  useEffect(() => {
    const handleOnline = () => {
      void syncOfflineActions(handler);
    };

    window.addEventListener("online", handleOnline);

    // Try syncing once when the application starts.
    if (navigator.onLine) {
      void syncOfflineActions(handler);
    }

    return () => {
      window.removeEventListener("online", handleOnline);
    };
  }, [handler]);
}