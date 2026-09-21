export type NotificationType = "NEW_PO";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  poNumber: string;
  createdAt: number;
  read: boolean;
}