import { renderHook, act } from "@testing-library/react";
import { MockedProvider } from "@apollo/client/testing";
import { InMemoryCache } from "@apollo/client";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useAcknowledgePO } from "./useAcknowledgePO";
import { ACKNOWLEDGE_PO } from "../graphql/mutations";
import { GET_PURCHASE_ORDERS } from "../graphql/queries";
import { addOfflineAction } from "../utils/offlineQueue";

vi.mock("../utils/offlineQueue", () => ({
  addOfflineAction: vi.fn(),
}));

const acknowledgeMock = {
  request: {
    query: ACKNOWLEDGE_PO,
    variables: {
      po_number: "PO-1001",
    },
  },
  result: {
    data: {
      acknowledgePurchaseOrder: {
        __typename: "PurchaseOrder",
        po_number: "PO-1001",
        status: "ACKNOWLEDGED",
      },
    },
  },
};

describe("useAcknowledgePO", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
  });

  it("queues the acknowledgement when browser is offline", async () => {
    const { result } = renderHook(
      () => useAcknowledgePO(),
      {
        wrapper: ({ children }) => (
          <MockedProvider>{children}</MockedProvider>
        ),
      }
    );

    let response;

    await act(async () => {
      response = await result.current.acknowledgePO("PO-1001");
    });

    expect(response).toEqual({
      queued: true,
    });

    expect(addOfflineAction).toHaveBeenCalledWith({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
    });
  });

  it("executes the GraphQL mutation when browser is online", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const { result } = renderHook(
      () => useAcknowledgePO(),
      {
        wrapper: ({ children }) => (
          <MockedProvider mocks={[acknowledgeMock]}>
            {children}
          </MockedProvider>
        ),
      }
    );

    let response;

    await act(async () => {
      response = await result.current.acknowledgePO("PO-1001");
    });

    expect(response).toEqual({
      queued: false,
    });

    expect(addOfflineAction).not.toHaveBeenCalled();
  });

  it("uses optimistic response when browser is online", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const mutationMock = {
      request: {
        query: ACKNOWLEDGE_PO,
        variables: {
          po_number: "PO-1001",
        },
      },
      result: {
        data: {
          acknowledgePurchaseOrder: {
            __typename: "PurchaseOrder",
            po_number: "PO-1001",
            status: "ACKNOWLEDGED",
          },
        },
      },
    };

    const cache = new InMemoryCache({
      typePolicies: {
        PurchaseOrder: {
          keyFields: ["po_number"],
        },
      },
    });

    cache.writeQuery({
      query: GET_PURCHASE_ORDERS,
      variables: {
        first: 20,
        after: null,
      },
      data: {
        purchaseOrders: {
          __typename: "PurchaseOrderConnection",
          edges: [
            {
              __typename: "PurchaseOrderEdge",
              cursor: "cursor-1",
              node: {
                __typename: "PurchaseOrder",
                po_number: "PO-1001",
                supplier_id: "SUP-001",
                status: "SENT",
                total_amount: 1000,
                expected_delivery: "2026-08-20",
                items: [],
              },
            },
          ],
          pageInfo: {
            __typename: "PageInfo",
            hasNextPage: false,
            endCursor: "cursor-1",
          },
        },
      },
    });

    const { result } = renderHook(
      () => useAcknowledgePO(),
      {
        wrapper: ({ children }) => (
          <MockedProvider
            mocks={[mutationMock]}
            cache={cache}
          >
            {children}
          </MockedProvider>
        ),
      }
    );

    await act(async () => {
      await result.current.acknowledgePO("PO-1001");
    });

    expect(result.current.loading).toBe(false);
    expect(addOfflineAction).not.toHaveBeenCalled();
  });
});