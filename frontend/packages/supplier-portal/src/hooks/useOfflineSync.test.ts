import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useOfflineSync } from "./useOfflineSync";
import { syncOfflineActions } from "../utils/offlineSync";

vi.mock("../utils/offlineSync", () => ({
  syncOfflineActions: vi.fn().mockResolvedValue(0),
}));

describe("useOfflineSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
  });

  it("syncs immediately when application starts online", () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });

    const handler = vi.fn().mockResolvedValue(undefined);

    renderHook(() => useOfflineSync(handler));

    expect(syncOfflineActions).toHaveBeenCalledWith(handler);
  });

  it("syncs when browser comes online", () => {
    const handler = vi.fn().mockResolvedValue(undefined);

    renderHook(() => useOfflineSync(handler));

    expect(syncOfflineActions).not.toHaveBeenCalled();

    window.dispatchEvent(new Event("online"));

    expect(syncOfflineActions).toHaveBeenCalledWith(handler);
  });

  it("removes the online event listener on unmount", () => {
    const handler = vi.fn().mockResolvedValue(undefined);

    const removeEventListenerSpy = vi.spyOn(
      window,
      "removeEventListener"
    );

    const { unmount } = renderHook(
      () => useOfflineSync(handler)
    );

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      "online",
      expect.any(Function)
    );

    removeEventListenerSpy.mockRestore();
  });
});

it("reports the number of successfully synced actions", async () => {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });

  vi.mocked(syncOfflineActions).mockResolvedValue(1);

  const handler = vi.fn().mockResolvedValue(undefined);
  const onSyncComplete = vi.fn();

  renderHook(() =>
    useOfflineSync(handler, onSyncComplete)
  );

  await vi.waitFor(() => {
    expect(syncOfflineActions).toHaveBeenCalledWith(handler);
  });

  await vi.waitFor(() => {
    expect(onSyncComplete).toHaveBeenCalledWith(1);
  });
});