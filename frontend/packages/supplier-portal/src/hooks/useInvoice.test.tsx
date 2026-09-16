import { renderHook, act } from "@testing-library/react";
import { MockedProvider } from "@apollo/client/testing";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useInvoice } from "./useInvoice";
import { SUBMIT_INVOICE } from "../graphql/mutations";
import { addOfflineAction } from "../utils/offlineQueue";

vi.mock("../utils/offlineQueue", () => ({
  addOfflineAction: vi.fn(),
}));

vi.mock("./usePurchaseOrders", () => ({
  usePurchaseOrders: vi.fn(() => ({
    data: {
      purchaseOrders: {
        edges: [],
        pageInfo: {
          hasNextPage: false,
          endCursor: null,
        },
      },
    },
    loading: false,
    error: undefined,
  })),
}));

describe("useInvoice", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
  });

  it("queues invoice submission when browser is offline", async () => {
    const submitInvoiceMock = {
      request: {
        query: SUBMIT_INVOICE,
        variables: {
          invoiceNumber: "INV-1001",
          poReference: "PO-1001",
          amount: 5000,
          date: "2026-08-24",
        },
      },
      result: {
        data: {
          submitInvoice: {
            invoiceNumber: "INV-1001",
            poReference: "PO-1001",
            amount: 5000,
            date: "2026-08-24",
          },
        },
      },
    };

    const { result } = renderHook(
      () => useInvoice(),
      {
        wrapper: ({ children }) => (
          <MockedProvider mocks={[submitInvoiceMock]}>
            {children}
          </MockedProvider>
        ),
      }
    );

    let response;

    await act(async () => {
      response =
        await result.current.submitInvoiceWithOfflineSupport(
          "INV-1001",
          "PO-1001",
          5000,
          "2026-08-24"
        );
    });

    expect(response).toEqual({
      queued: true,
    });

    expect(addOfflineAction).toHaveBeenCalledWith({
      type: "SUBMIT_INVOICE",
      payload: {
        invoiceNumber: "INV-1001",
        poReference: "PO-1001",
        amount: 5000,
        date: "2026-08-24",
      },
    });
  });
});