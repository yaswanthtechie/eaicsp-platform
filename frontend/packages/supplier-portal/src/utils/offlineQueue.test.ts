
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addOfflineAction,
  getOfflineActions,
  removeOfflineAction,
  clearOfflineActions,
} from "./offlineQueue";

describe("offlineQueue", () => {
  beforeEach(() => {
    localStorage.clear();

    vi.spyOn(crypto, "randomUUID").mockReturnValue(
      "11111111-1111-1111-1111-111111111111"
    );

    vi.spyOn(Date, "now").mockReturnValue(123456789);
  });

  it("adds an offline action to the queue", () => {
    const action = addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
    });

    expect(action).toEqual({
      id: "11111111-1111-1111-1111-111111111111",
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
      createdAt: 123456789,
    });

    expect(getOfflineActions()).toEqual([action]);
  });

  it("returns an empty queue when no actions exist", () => {
    expect(getOfflineActions()).toEqual([]);
  });

  it("stores multiple offline actions", () => {
    vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce(
        "11111111-1111-1111-1111-111111111111"
      )
      .mockReturnValueOnce(
        "22222222-2222-2222-2222-222222222222"
      );

    addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
    });

    addOfflineAction({
      type: "SUBMIT_INVOICE",
      payload: {
        po_number: "PO-1002",
      },
    });

    const actions = getOfflineActions();

    expect(actions).toHaveLength(2);
    expect(actions[0].id).toBe(
      "11111111-1111-1111-1111-111111111111"
    );
    expect(actions[1].id).toBe(
      "22222222-2222-2222-2222-222222222222"
    );
  });

  it("removes an offline action by id", () => {
    vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce(
        "11111111-1111-1111-1111-111111111111"
      )
      .mockReturnValueOnce(
        "22222222-2222-2222-2222-222222222222"
      );

    addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
    });

    addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1002",
      },
    });

    removeOfflineAction(
      "11111111-1111-1111-1111-111111111111"
    );

    const actions = getOfflineActions();

    expect(actions).toHaveLength(1);
    expect(actions[0].id).toBe(
      "22222222-2222-2222-2222-222222222222"
    );
  });

  it("clears all offline actions", () => {
    addOfflineAction({
      type: "ACKNOWLEDGE_PO",
      payload: {
        po_number: "PO-1001",
      },
    });

    addOfflineAction({
      type: "SUBMIT_INVOICE",
      payload: {
        po_number: "PO-1002",
      },
    });

    clearOfflineActions();

    expect(getOfflineActions()).toEqual([]);
  });

  it("returns an empty queue when localStorage contains invalid JSON", () => {
    localStorage.setItem(
      "supplierPortalOfflineQueue",
      "invalid-json"
    );

    expect(getOfflineActions()).toEqual([]);
  });
});
