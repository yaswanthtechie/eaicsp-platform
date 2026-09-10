import type { PurchaseOrder } from "./po";

export interface PurchaseOrderEdge {
  cursor: string;
  node: PurchaseOrder;
}

export interface PageInfo {
  hasNextPage: boolean;
  endCursor: string | null;
}

export interface PurchaseOrdersConnection {
  edges: PurchaseOrderEdge[];
  pageInfo: PageInfo;
}

export interface PurchaseOrdersQuery {
  purchaseOrders: PurchaseOrdersConnection;
}

export interface AcknowledgePurchaseOrderMutation {
  acknowledgePurchaseOrder: PurchaseOrder;
}