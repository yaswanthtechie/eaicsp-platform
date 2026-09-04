export interface OfflineAction {
  id: string;
  type: "ACKNOWLEDGE_PO" | "SUBMIT_INVOICE";
  payload: Record<string, unknown>;
  createdAt: number;
}

const OFFLINE_QUEUE_KEY = "supplierPortalOfflineQueue";

function getQueue(): OfflineAction[] {
  try {
    const stored = localStorage.getItem(OFFLINE_QUEUE_KEY);

    if (!stored) {
      return [];
    }

    return JSON.parse(stored) as OfflineAction[];
  } catch {
    return [];
  }
}

function saveQueue(queue: OfflineAction[]): void {
  localStorage.setItem(
    OFFLINE_QUEUE_KEY,
    JSON.stringify(queue)
  );
}

function isSamePO(
  action: OfflineAction,
  newAction: Omit<OfflineAction, "id" | "createdAt">
): boolean {
  return (
    action.type === newAction.type &&
    action.payload.po_number === newAction.payload.po_number
  );
}

export function addOfflineAction(
  action: Omit<OfflineAction, "id" | "createdAt">
): OfflineAction {
  const newAction: OfflineAction = {
    ...action,
    id: crypto.randomUUID(),
    createdAt: Date.now(),
  };

  let queue = getQueue();

  // Prevent duplicate pending actions for the same PO.
  // The latest user action replaces the older pending action.
  queue = queue.filter(
    (existingAction) =>
      !isSamePO(existingAction, newAction)
  );

  queue.push(newAction);

  saveQueue(queue);

  return newAction;
}

export function getOfflineActions(): OfflineAction[] {
  return getQueue();
}

export function removeOfflineAction(id: string): void {
  const queue = getQueue().filter(
    (action) => action.id !== id
  );

  saveQueue(queue);
}

export function clearOfflineActions(): void {
  localStorage.removeItem(OFFLINE_QUEUE_KEY);
}