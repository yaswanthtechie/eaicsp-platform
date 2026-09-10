import client from "./apollo";
import { GET_PURCHASE_ORDERS } from "./queries";
import { describe, expect, it } from "vitest";

describe("Apollo purchaseOrders cache", () => {
it("uses the real purchase orders query and separates cache entries for different filters", () => {
const cache = client.cache;


cache.reset();

cache.writeQuery({
  query: GET_PURCHASE_ORDERS,
  variables: {
    first: 20,
    after: null,
    status: "SENT",
  },
  data: {
    purchaseOrders: {
      __typename: "PurchaseOrderConnection",
      edges: [
        {
          __typename: "PurchaseOrderEdge",
          cursor: "sent-cursor",
          node: {
            __typename: "PurchaseOrder",
            poNumber: "PO-SENT-001",
            supplierId: "SUP-1",
            status: "SENT",
            totalAmount: 1000,
            expectedDelivery: "2026-08-30",
            items: [],
          },
        },
      ],
      pageInfo: {
        __typename: "PageInfo",
        hasNextPage: false,
        endCursor: "sent-cursor",
      },
    },
  },
});

cache.writeQuery({
  query: GET_PURCHASE_ORDERS,
  variables: {
    first: 20,
    after: null,
    status: "ACKNOWLEDGED",
  },
  data: {
    purchaseOrders: {
      __typename: "PurchaseOrderConnection",
      edges: [
        {
          __typename: "PurchaseOrderEdge",
          cursor: "acknowledged-cursor",
          node: {
            __typename: "PurchaseOrder",
            poNumber: "PO-ACK-001",
            supplierId: "SUP-1",
            status: "ACKNOWLEDGED",
            totalAmount: 2000,
            expectedDelivery: "2026-09-01",
            items: [],
          },
        },
      ],
      pageInfo: {
        __typename: "PageInfo",
        hasNextPage: false,
        endCursor: "acknowledged-cursor",
      },
    },
  },
});

const sentData = cache.readQuery<{
  purchaseOrders: {
    edges: Array<{
      node: {
        poNumber: string;
        status: string;
      };
    }>;
  };
}>({
  query: GET_PURCHASE_ORDERS,
  variables: {
    first: 20,
    after: null,
    status: "SENT",
  },
});

const acknowledgedData = cache.readQuery<{
  purchaseOrders: {
    edges: Array<{
      node: {
        poNumber: string;
        status: string;
      };
    }>;
  };
}>({
  query: GET_PURCHASE_ORDERS,
  variables: {
    first: 20,
    after: null,
    status: "ACKNOWLEDGED",
  },
});

expect(
  sentData?.purchaseOrders.edges[0].node.poNumber
).toBe("PO-SENT-001");

expect(
  sentData?.purchaseOrders.edges[0].node.status
).toBe("SENT");

expect(
  acknowledgedData?.purchaseOrders.edges[0].node.poNumber
).toBe("PO-ACK-001");

expect(
  acknowledgedData?.purchaseOrders.edges[0].node.status
).toBe("ACKNOWLEDGED");

});
});
