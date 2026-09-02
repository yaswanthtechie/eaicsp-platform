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

type PurchaseOrdersCache = {
  purchaseOrders: {
    edges: Array<{
      node: {
        status: string;
      };
    }>;
  };
};

const acknowledgeMock = {
  request: {
    query: ACKNOWLEDGE_PO,
    variables: {
      poNumber: "PO-1001",
    },
  },
  result: {
    data: {
      acknowledgePurchaseOrder: {
        __typename: "PurchaseOrder",
        poNumber: "PO-1001",
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
    const { result } = renderHook(() => useAcknowledgePO(), {
      wrapper: ({ children }) => (
        <MockedProvider>{children}</MockedProvider>
      ),
    });

    let response;

    await act(async () => {
      response = await result.current.acknowledgePO("PO-1001");
    });

    expect(response).toEqual({
      queued: true,
    });

    // Offline queue intentionally keeps the existing
    // application action payload format.
expect(addOfflineAction).toHaveBeenCalledWith({
  type: "ACKNOWLEDGE_PO",
  payload: {
    poNumber: "PO-1001",
  },
});
  });

  it("executes the GraphQL mutation when browser is online", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const { result } = renderHook(() => useAcknowledgePO(), {
      wrapper: ({ children }) => (
        <MockedProvider mocks={[acknowledgeMock]}>
          {children}
        </MockedProvider>
      ),
    });

    let response;

    await act(async () => {
      response = await result.current.acknowledgePO("PO-1001");
    });

    expect(response).toEqual({
      queued: false,
    });

    expect(addOfflineAction).not.toHaveBeenCalled();
  });

  it("updates the cache optimistically before the mutation resolves", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const mutationMock = {
      request: {
        query: ACKNOWLEDGE_PO,
        variables: {
          poNumber: "PO-1001",
        },
      },
      delay: 100,
      result: {
        data: {
          acknowledgePurchaseOrder: {
            __typename: "PurchaseOrder",
            poNumber: "PO-1001",
            status: "ACKNOWLEDGED",
          },
        },
      },
    };

    const cache = new InMemoryCache({
      typePolicies: {
        PurchaseOrder: {
          keyFields: ["poNumber"],
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
                poNumber: "PO-1001",
                supplierId: "SUP-001",
                status: "SENT",
                totalAmount: 1000,
                expectedDelivery: "2026-08-20",
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

    const { result } = renderHook(() => useAcknowledgePO(), {
      wrapper: ({ children }) => (
        <MockedProvider
          mocks={[mutationMock]}
          cache={cache}
        >
          {children}
        </MockedProvider>
      ),
    });

    let promise: Promise<{ queued: boolean }>;

    act(() => {
      promise = result.current.acknowledgePO("PO-1001");
    });

    const data = cache.readQuery<PurchaseOrdersCache>({
      query: GET_PURCHASE_ORDERS,
      variables: {
        first: 20,
        after: null,
      },
      optimistic: true,
    });

    expect(
      data?.purchaseOrders?.edges?.[0]?.node.status
    ).toBe("ACKNOWLEDGED");

    await act(async () => {
      await promise;
    });

    const finalData = cache.readQuery<PurchaseOrdersCache>({
      query: GET_PURCHASE_ORDERS,
      variables: {
        first: 20,
        after: null,
      },
    });

    expect(
      finalData?.purchaseOrders?.edges?.[0]?.node.status
    ).toBe("ACKNOWLEDGED");

    expect(addOfflineAction).not.toHaveBeenCalled();
  });

  it("rolls back the optimistic status when the mutation fails", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const mutationMock = {
      request: {
        query: ACKNOWLEDGE_PO,
        variables: {
          poNumber: "PO-1001",
        },
      },
      delay: 100,
      error: new Error("Failed to acknowledge purchase order"),
    };

    const cache = new InMemoryCache({
      typePolicies: {
        PurchaseOrder: {
          keyFields: ["poNumber"],
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
                poNumber: "PO-1001",
                supplierId: "SUP-001",
                status: "SENT",
                totalAmount: 1000,
                expectedDelivery: "2026-08-20",
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

    const { result } = renderHook(() => useAcknowledgePO(), {
      wrapper: ({ children }) => (
        <MockedProvider
          mocks={[mutationMock]}
          cache={cache}
        >
          {children}
        </MockedProvider>
      ),
    });

    let promise: Promise<{ queued: boolean }>;

    act(() => {
      promise = result.current.acknowledgePO("PO-1001");
    });

    const optimisticData =
      cache.readQuery<PurchaseOrdersCache>({
        query: GET_PURCHASE_ORDERS,
        variables: {
          first: 20,
          after: null,
        },
        optimistic: true,
      });

    expect(
      optimisticData?.purchaseOrders?.edges?.[0]?.node.status
    ).toBe("ACKNOWLEDGED");

    await act(async () => {
      await expect(promise).rejects.toThrow(
        "Failed to acknowledge purchase order"
      );
    });

    const finalData = cache.readQuery<PurchaseOrdersCache>({
      query: GET_PURCHASE_ORDERS,
      variables: {
        first: 20,
        after: null,
      },
    });

    expect(
      finalData?.purchaseOrders?.edges?.[0]?.node.status
    ).toBe("SENT");

    expect(addOfflineAction).not.toHaveBeenCalled();
  });
});
