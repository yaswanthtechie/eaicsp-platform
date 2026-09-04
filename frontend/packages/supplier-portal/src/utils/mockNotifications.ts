import type { Notification } from "../types/notification";

export function createNewPONotification(
  poNumber: string
): Notification {
  return {
    id: crypto.randomUUID(),
    type: "NEW_PO",
    title: "New Purchase Order",
    message: `${poNumber} has been received.`,
    poNumber,
    createdAt: Date.now(),
    read: false,
  };
}