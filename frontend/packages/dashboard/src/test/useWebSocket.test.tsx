import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket } from "../hooks/useWebSocket";
interface MockSocket {
  url: string;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((error: Event) => void) | null;
  onclose: ((event: { code: number}) => void) | null;
  close: ReturnType<typeof vi.fn>;
}

describe("useWebSocket", () => {
  let sockets: MockSocket[];

  const stockLowEvent = {
    event_id: "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
    event_type: "inventory.stock.low",
    event_version: "1.0",
    occurred_at: "2026-10-15T10:14:22.481203+00:00",
    producer: "inventory-service",
    payload: {
      sku_id: "SKU-000123",
      warehouse_id: "WH-BLR-01",
      quantity_on_hand: 8,
      reorder_point: 35,
      safety_stock: 15,
      avg_daily_demand: 4.5,
    },
  };

  beforeEach(() => {
    vi.useFakeTimers();

    sockets = [];

    class MockWebSocket {
      url: string;
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: ((error: Event) => void) | null = null;
      onclose: ((event: { code: number}) => void) | null = null;
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

    const event = {
      event_id: "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
      event_type: "inventory.stock.low",
      event_version: 1,
      occurred_at: "2026-08-24T10:00:00Z",
      producer: "inventory-service",
      payload: {
        sku_id: "SKU-000123",
        warehouse_id: "WH-BLR-01",
        quantity_on_hand: 5,
        reorder_point: 10,
        safety_stock: 3,
        avg_daily_demand: 2,
      },
    };

    act(() => {
      sockets[0].onmessage?.({
        data: JSON.stringify(event),
      });
    });

    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
        type: "low-stock",
        severity: "warning",
        timestamp: "2026-08-24T10:00:00Z",
      }),
    );
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

  it("sets failed when socket closes and autoReconnect is false", () => {
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
    expect(result.current.failed).toBe(false);

    act(() => {
      sockets[0].onclose?.({ code: 1006});
    });

    expect(result.current.connected).toBe(false);
    expect(result.current.isConnecting).toBe(false);

    expect(result.current.failed).toBe(true);
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
      sockets[0].onclose?.({ code: 1006});
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
      sockets[1].onclose?.({ code: 1006});
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
      sockets[2].onclose?.({ code: 1006});
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
      sockets[0].onclose?.({ code: 1006});
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(sockets).toHaveLength(2);

    act(() => {
      sockets[1].onclose?.({ code: 1006});
    });

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(sockets).toHaveLength(3);

    act(() => {
      sockets[2].onclose?.({ code: 1006});
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

  it("ignores a duplicate event_id", () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({ url: "ws://localhost:8080", onMessage }),
    );

    act(() => {
      sockets[0].onmessage?.({ data: JSON.stringify(stockLowEvent) });
      sockets[0].onmessage?.({ data: JSON.stringify(stockLowEvent) });
    });

    expect(onMessage).toHaveBeenCalledTimes(1);
  });

  it("accepts an event with trace_id null", () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({ url: "ws://localhost:8080", onMessage }),
    );

    act(() => {
      sockets[0].onmessage?.({
        data: JSON.stringify({ ...stockLowEvent, trace_id: null }),
      });
    });

    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ id: stockLowEvent.event_id }),
    );
  });

  it("ignores an envelope missing required fields", () => {
    const onMessage = vi.fn();
    vi.spyOn(console, "error").mockImplementation(() => {});

    renderHook(() =>
      useWebSocket({ url: "ws://localhost:8080", onMessage }),
    );

    const missingProducer = {
       ...stockLowEvent,
       producer: undefined,
    };

    act(() => {
      sockets[0].onmessage?.({ data: JSON.stringify(missingProducer) });
    });

    expect(onMessage).not.toHaveBeenCalled();
  });
});
