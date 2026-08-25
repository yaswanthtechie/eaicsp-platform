import { InMemoryCache, gql } from "@apollo/client";
import { describe, expect, it } from "vitest";

const PURCHASE_ORDERS_QUERY = gql`
  query GetPurchaseOrders(
    $first: Int!
    $after: String
    $status: String
    $poNumber: String
    $minAmount: Int
    $maxAmount: Int
    $startDate: String
    $endDate: String
  ) {
    purchaseOrders(
      first: $first
      after: $after
      status: $status
      poNumber: $poNumber
      minAmount: $minAmount
      maxAmount: $maxAmount
      startDate: $startDate
      endDate: $endDate
    ) {
      edges {
        cursor
        node {
          __typename
          po_number
          status
        }
      }
      pageInfo {
        __typename
        hasNextPage
        endCursor
      }
    }
  }
`;

const createCache = () =>
  new InMemoryCache({
    typePolicies: {
      PurchaseOrder: {
        keyFields: ["po_number"],
      },
      Query: {
        fields: {
          purchaseOrders: {
            keyArgs: [
              "status",
              "poNumber",
              "minAmount",
              "maxAmount",
              "startDate",
              "endDate",
            ],
          },
        },
      },
    },
  });

describe("Apollo purchaseOrders cache", () => {
  it("separates purchase order cache entries for different filter combinations", () => {
    const cache = createCache();

    cache.writeQuery({
      query: PURCHASE_ORDERS_QUERY,
      variables: {
        first: 20,
        after: null,
        status: "sent",
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
                po_number: "PO-SENT-001",
                status: "SENT",
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
      query: PURCHASE_ORDERS_QUERY,
      variables: {
        first: 20,
        after: null,
        status: "acknowledged",
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
                po_number: "PO-ACK-001",
                status: "ACKNOWLEDGED",
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
            po_number: string;
            status: string;
          };
        }>;
      };
    }>({
      query: PURCHASE_ORDERS_QUERY,
      variables: {
        first: 20,
        after: null,
        status: "sent",
      },
    });

    const acknowledgedData = cache.readQuery<{
      purchaseOrders: {
        edges: Array<{
          node: {
            po_number: string;
            status: string;
          };
        }>;
      };
    }>({
      query: PURCHASE_ORDERS_QUERY,
      variables: {
        first: 20,
        after: null,
        status: "acknowledged",
      },
    });

    expect(
      sentData?.purchaseOrders.edges[0].node.po_number
    ).toBe("PO-SENT-001");

    expect(
      sentData?.purchaseOrders.edges[0].node.status
    ).toBe("SENT");

    expect(
      acknowledgedData?.purchaseOrders.edges[0].node.po_number
    ).toBe("PO-ACK-001");

    expect(
      acknowledgedData?.purchaseOrders.edges[0].node.status
    ).toBe("ACKNOWLEDGED");
  });
});