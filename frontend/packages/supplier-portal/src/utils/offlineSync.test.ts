import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getOfflineActions,
  removeOfflineAction,
} from "./offlineQueue";

import { syncOfflineActions } from "./offlineSync";

vi.mock("./offlineQueue", () => ({
  getOfflineActions: vi.fn(),
  removeOfflineAction: vi.fn(),
}));

describe("syncOfflineActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });
  });

  it("does not sync when browser is offline", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });

    const handler = vi.fn();

    await syncOfflineActions(handler);

    expect(getOfflineActions).not.toHaveBeenCalled();
    expect(handler).not.toHaveBeenCalled();
  });

  it("does nothing when there are no queued actions", async () => {
    vi.mocked(getOfflineActions).mockReturnValue([]);

    const handler = vi.fn();

    await syncOfflineActions(handler);

    expect(getOfflineActions).toHaveBeenCalled();
    expect(handler).not.toHaveBeenCalled();
  });

  it("syncs a queued action and removes it after success", async () => {
    const action = {
      id: "action-1",
      type: "ACKNOWLEDGE_PO" as const,
      payload: {
        po_number: "PO-1001",
      },
      createdAt: 123456789,
    };

    vi.mocked(getOfflineActions).mockReturnValue([action]);

    const handler = vi.fn().mockResolvedValue(undefined);

    await syncOfflineActions(handler);

    expect(handler).toHaveBeenCalledWith(
      "ACKNOWLEDGE_PO",
      {
        po_number: "PO-1001",
      }
    );

    expect(removeOfflineAction).toHaveBeenCalledWith(
      "action-1"
    );
  });

  it("keeps the action in the queue when sync fails", async () => {
    const action = {
      id: "action-1",
      type: "ACKNOWLEDGE_PO" as const,
      payload: {
        po_number: "PO-1001",
      },
      createdAt: 123456789,
    };

    vi.mocked(getOfflineActions).mockReturnValue([action]);

    const handler = vi
      .fn()
      .mockRejectedValue(new Error("Network error"));

    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    await syncOfflineActions(handler);

    expect(handler).toHaveBeenCalledWith(
      "ACKNOWLEDGE_PO",
      {
        po_number: "PO-1001",
      }
    );

    expect(removeOfflineAction).not.toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });
});