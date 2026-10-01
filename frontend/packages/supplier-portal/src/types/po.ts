export type POStatus =
  | "DRAFT"
  | "SENT"
  | "ACKNOWLEDGED"
  | "FULFILLED"
  | "CANCELLED";

export interface POItem {
  sku: string;
  productName: string;
  quantity: number;
  unitPrice: number;
}

export interface PurchaseOrder {
  poNumber: string;
  supplierId: string;
  status: POStatus;
  totalAmount: number;
  expectedDelivery: string;
  items: POItem[];
}