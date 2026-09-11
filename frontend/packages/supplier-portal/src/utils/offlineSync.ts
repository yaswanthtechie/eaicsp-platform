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
): Promise<number> {
  if (!navigator.onLine || isSyncing) {
    return 0;
  }

  isSyncing = true;

  let syncedCount = 0;

  try {
    const actions = getOfflineActions();

    for (const action of actions) {
      try {
        await handler(action.type, action.payload);

        removeOfflineAction(action.id);
        syncedCount += 1;
      } catch (error) {
        console.error(
          "Failed to sync offline action:",
          action,
          error
        );

        // Skip the failed/unsupported action
        // and continue with the remaining actions.
        continue;
      }
    }

    return syncedCount;
  } finally {
    isSyncing = false;
  }
}