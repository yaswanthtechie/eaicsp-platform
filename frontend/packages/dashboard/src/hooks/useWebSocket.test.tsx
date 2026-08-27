import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useWebSocket } from "./useWebSocket";

describe("useWebSocket", () => {
  let socket: {
    onopen: (() => void) | null;
    onmessage: ((event: { data: string }) => void) | null;
    onerror: ((error: Event) => void) | null;
    onclose: (() => void) | null;
    close: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    socket = {
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      close: vi.fn(),
    };

    vi.stubGlobal(
      "WebSocket",
      vi.fn(function () {
        return socket;
      }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("connects to WebSocket", () => {
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    expect(WebSocket).toHaveBeenCalledWith(
      "ws://localhost:8080",
    );
  });

  it("shows connected when socket opens", async () => {
  const onMessage = vi.fn();

  const { result } = renderHook(() =>
    useWebSocket({
      url: "ws://localhost:8080",
      onMessage,
    }),
  );

  act(() => {
    socket.onopen?.();
  });

  await waitFor(() => {
    expect(result.current.connected).toBe(true);
  });

  expect(result.current.isConnecting).toBe(false);
});

  it("receives a valid message", () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage,
      }),
    );

    const alert = {
      id: "ALERT001",
      type: "inventory",
      severity: "warning",
      message: "Low stock",
      timestamp: "2026-08-24T10:00:00Z",
    };

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify(alert),
      });
    });

    expect(onMessage).toHaveBeenCalledWith(alert);
  });

  it("ignores invalid JSON message", () => {
    const onMessage = vi.fn();

    vi.spyOn(console, "error").mockImplementation(() => {});

    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage,
      }),
    );

    act(() => {
      socket.onmessage?.({
        data: "invalid json",
      });
    });

    expect(onMessage).not.toHaveBeenCalled();
  });

  it("shows disconnected when socket closes", () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        autoReconnect: false,
      }),
    );

    act(() => {
      socket.onopen?.();
    });

    act(() => {
      socket.onclose?.();
    });

    expect(result.current.connected).toBe(false);
  });

  it("calls onError when socket has an error", () => {
    const onError = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        onError,
      }),
    );

    const error = new Event("error");

    act(() => {
      socket.onerror?.(error);
    });

    expect(onError).toHaveBeenCalledWith(error);
  });

  it("closes socket when component unmounts", () => {
    const { unmount } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    unmount();

    expect(socket.close).toHaveBeenCalled();
  });
});