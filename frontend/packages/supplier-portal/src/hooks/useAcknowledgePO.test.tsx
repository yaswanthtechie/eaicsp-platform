import { renderHook, act } from "@testing-library/react";
import { MockedProvider } from "@apollo/client/testing";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useAcknowledgePO } from "./useAcknowledgePO";
import { ACKNOWLEDGE_PO } from "../graphql/mutations";
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
          <MockedProvider>
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
});