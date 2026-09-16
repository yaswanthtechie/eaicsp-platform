import { renderHook, act } from "@testing-library/react";
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
} from "vitest";
import { useWebSocket } from "./useWebSocket";
interface MockSocket {
  url: string;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((error: Event) => void) | null;
  onclose: (() => void) | null;
  close: ReturnType<typeof vi.fn>;
}

describe("useWebSocket", () => {
  let sockets: MockSocket[];

  beforeEach(() => {
    vi.useFakeTimers();

    sockets = [];

    class MockWebSocket {
      url: string;

      onopen: (() => void) | null = null;

      onmessage: ((event: { data: string }) => void) | null = null;

      onerror: ((error: Event) => void) | null = null;

      onclose: (() => void) | null = null;

      close = vi.fn();

      constructor(url: string) {
        this.url = url;

        sockets.push(this);
      }
    }

    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("connects to WebSocket", () => {
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe("ws://localhost:8080");
  });

  it("shows connected when socket opens", () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    expect(result.current.isConnecting).toBe(true);
    expect(result.current.connected).toBe(false);

    act(() => {
      sockets[0].onopen?.();
    });

    expect(result.current.connected).toBe(true);
    expect(result.current.isConnecting).toBe(false);
    expect(result.current.failed).toBe(false);
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
      sockets[0].onmessage?.({
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
      sockets[0].onmessage?.({
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
      sockets[0].onopen?.();
    });

    expect(result.current.connected).toBe(true);

    act(() => {
      sockets[0].onclose?.();
    });

    expect(result.current.connected).toBe(false);
    expect(result.current.isConnecting).toBe(false);
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
      sockets[0].onerror?.(error);
    });

    expect(onError).toHaveBeenCalledWith(error);
  });

  it("reconnects with exponential backoff", () => {
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        autoReconnect: true,
        maxRetries: 3,
      }),
    );

    expect(sockets).toHaveLength(1);
    act(() => {
      sockets[0].onclose?.();
    });
    act(() => {
      vi.advanceTimersByTime(999);
    });

    expect(sockets).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(sockets).toHaveLength(2);
    act(() => {
      sockets[1].onclose?.();
    });

    act(() => {
      vi.advanceTimersByTime(1999);
    });

    expect(sockets).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(sockets).toHaveLength(3);

    act(() => {
      sockets[2].onclose?.();
    });

    act(() => {
      vi.advanceTimersByTime(3999);
    });

    expect(sockets).toHaveLength(3);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(sockets).toHaveLength(4);
  });

  it("stops reconnecting after max retries", () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        autoReconnect: true,
        maxRetries: 2,
      }),
    );

    expect(sockets).toHaveLength(1);

    act(() => {
      sockets[0].onclose?.();
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(sockets).toHaveLength(2);

    act(() => {
      sockets[1].onclose?.();
    });

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(sockets).toHaveLength(3);

    act(() => {
      sockets[2].onclose?.();
    });

    expect(result.current.failed).toBe(true);

    act(() => {
      vi.advanceTimersByTime(30000);
    });

    expect(sockets).toHaveLength(3);
  });

  it("closes socket when component unmounts", () => {
    const { unmount } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    unmount();

    expect(sockets[0].close).toHaveBeenCalled();
  });
});
