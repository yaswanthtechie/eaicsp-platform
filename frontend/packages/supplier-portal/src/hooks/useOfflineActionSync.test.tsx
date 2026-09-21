import { renderHook, waitFor } from "@testing-library/react";
import { MockedProvider } from "@apollo/client/testing";
import { beforeEach, describe, expect, it } from "vitest";

import { useOfflineActionSync } from "./useOfflineActionSync";
import { ACKNOWLEDGE_PO } from "../graphql/mutations";
import {
  addOfflineAction,
  getOfflineActions,
} from "../utils/offlineQueue";

describe("useOfflineActionSync", () => {
  beforeEach(() => {
    localStorage.clear();

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });
  });

  it("replays a queued acknowledgement using the poNumber contract", async () => {
    addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        poNumber: "PO-1001",
      },
    });

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

    renderHook(() => useOfflineActionSync(), {
      wrapper: ({ children }) => (
        <MockedProvider mocks={[acknowledgeMock]}>
          {children}
        </MockedProvider>
      ),
    });

    // The queued action is only removed if the mutation
    // matched and resolved successfully.
    await waitFor(() => {
      expect(getOfflineActions()).toHaveLength(0);
    });
  });
});