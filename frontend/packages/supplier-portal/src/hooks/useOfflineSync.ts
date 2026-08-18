import { useEffect } from "react";
import { syncOfflineActions } from "../utils/offlineSync";

export function useOfflineSync(
  handler: (
    type: string,
    payload: Record<string, unknown>
  ) => Promise<void>,
  onSyncComplete?: (count: number) => void
) {
  useEffect(() => {
    const handleOnline = () => {
      void syncOfflineActions(handler).then((count) => {
        if (count > 0) {
          onSyncComplete?.(count);
        }
      });
    };

    window.addEventListener("online", handleOnline);

    if (navigator.onLine) {
      void syncOfflineActions(handler).then((count) => {
        if (count > 0) {
          onSyncComplete?.(count);
        }
      });
    }

    return () => {
      window.removeEventListener("online", handleOnline);
    };
  }, [handler, onSyncComplete]);
}