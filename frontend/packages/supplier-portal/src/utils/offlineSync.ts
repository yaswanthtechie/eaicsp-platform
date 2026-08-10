import {
  getOfflineActions,
  removeOfflineAction,
} from "./offlineQueue";

type SyncHandler = (
  type: string,
  payload: Record<string, unknown>
) => Promise<void>;

let isSyncing = false;

export async function syncOfflineActions(
  handler: SyncHandler
): Promise<void> {
  if (!navigator.onLine || isSyncing) {
    return;
  }

  isSyncing = true;

  try {
    const actions = getOfflineActions();

    for (const action of actions) {
      try {
        await handler(action.type, action.payload);

        removeOfflineAction(action.id);
      } catch (error) {
        console.error(
          "Failed to sync offline action:",
          action,
          error
        );

        // Stop here so the action remains in the queue
        // and can be retried when the connection is available.
        break;
      }
    }
  } finally {
    isSyncing = false;
  }
}