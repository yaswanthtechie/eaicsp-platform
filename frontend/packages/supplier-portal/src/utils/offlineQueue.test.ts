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

    vi.restoreAllMocks();

    vi.spyOn(crypto, "randomUUID").mockReturnValue(
      "11111111-1111-1111-1111-111111111111"
    );

    vi.spyOn(Date, "now").mockReturnValue(123456789);
  });

  it("adds an offline acknowledgement action to the queue", () => {
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

  it("persists multiple offline actions in insertion order", () => {
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

    expect(getOfflineActions()).toEqual([
      {
        id: "11111111-1111-1111-1111-111111111111",
        type: "ACKNOWLEDGE_PO",
        payload: {
          po_number: "PO-1001",
        },
        createdAt: 123456789,
      },
      {
        id: "22222222-2222-2222-2222-222222222222",
        type: "SUBMIT_INVOICE",
        payload: {
          po_number: "PO-1002",
        },
        createdAt: 123456789,
      },
    ]);
  });

  it("removes only the requested offline action", () => {
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

    expect(getOfflineActions()).toEqual([
      {
        id: "22222222-2222-2222-2222-222222222222",
        type: "ACKNOWLEDGE_PO",
        payload: {
          po_number: "PO-1002",
        },
        createdAt: 123456789,
      },
    ]);
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

  it("handles invalid localStorage data safely", () => {
    localStorage.setItem(
      "supplierPortalOfflineQueue",
      "invalid-json"
    );

    expect(getOfflineActions()).toEqual([]);
  });

  it("handles missing localStorage data safely", () => {
    expect(
      localStorage.getItem("supplierPortalOfflineQueue")
    ).toBeNull();

    expect(getOfflineActions()).toEqual([]);
  });

  it("keeps only the latest duplicate action for the same PO", () => {
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
        po_number: "PO-1001",
      },
    });

    expect(getOfflineActions()).toEqual([
      {
        id: "22222222-2222-2222-2222-222222222222",
        type: "ACKNOWLEDGE_PO",
        payload: {
          po_number: "PO-1001",
        },
        createdAt: 123456789,
      },
    ]);
  });
});