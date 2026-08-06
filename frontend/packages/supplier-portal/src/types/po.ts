export type POStatus =
  | "draft"
  | "sent"
  | "acknowledged"
  | "fulfilled"
  | "cancelled";

export interface POItem {
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

export interface PurchaseOrder {
  po_number: string;
  supplier_id: string;
  status: POStatus;
  total_amount: number;
  expected_delivery: string;
  items: POItem[];
}