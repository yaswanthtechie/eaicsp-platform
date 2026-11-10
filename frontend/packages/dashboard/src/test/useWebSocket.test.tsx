import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket } from "../hooks/useWebSocket";
import { getAuthSession, refreshAuthSession, type AuthSession } from "../api/auth";

const authMocks = vi.hoisted(() => ({
  session: null as AuthSession | null,
}));

vi.mock("../api/auth", () => ({
  getAuthSession: vi.fn(() => authMocks.session),
  refreshAuthSession: vi.fn(),
}));
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
    vi.clearAllMocks();

    authMocks.session = {
      access_token: "test-access-token",
      refresh_token: "test-refresh-token",
      token_type: "bearer",
      role: "ceo",
    };

    vi.mocked(getAuthSession).mockImplementation(() => authMocks.session);
    vi.mocked(refreshAuthSession).mockReset();

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

  it("connects to WebSocket with an auth token", () => {
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    expect(sockets).toHaveLength(1);

    const socketUrl = new URL(sockets[0].url);
    expect(socketUrl.origin).toBe("ws://localhost:8080");
    expect(socketUrl.searchParams.get("token")).toBe("test-access-token");

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

  it("does not connect and shows failed when there is no token", () => {
    vi.mocked(getAuthSession).mockReturnValueOnce(null);
    const { result } = renderHook(() =>
      useWebSocket({ url: "ws://localhost:8080", onMessage: vi.fn() }),
    );
    expect(sockets).toHaveLength(0);
    expect(result.current.failed).toBe(true);
  });

  it("delivers one alert per anomaly episode", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ url: "ws://localhost:8080", onMessage }));
    const base = {
      event_type: "iot.anomaly.detected",
      event_version: 1,
      occurred_at: "2026-10-15T10:46:12Z",
      producer: "anomaly-detection-service",
      payload: {
        episode_id: "WH-BLR-01-S1|2026-10-15T10:05:00+00:00",
        warehouse_id: "WH-BLR-01",
        severity: "high",
        message: "Temperature unusually high",
      },
    };
    act(() => {
      sockets[0].onopen?.();
      sockets[0].onmessage?.({ data: JSON.stringify({ ...base, event_id: crypto.randomUUID() }) } as MessageEvent);
      sockets[0].onmessage?.({ data: JSON.stringify({ ...base, event_id: crypto.randomUUID() }) } as MessageEvent);
    });
    expect(onMessage).toHaveBeenCalledTimes(1);
  });

  it("connects without a token when requireToken is false", () => {
    vi.mocked(getAuthSession).mockReturnValueOnce(null);
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        requireToken: false,
      }),
    );
    expect(sockets).toHaveLength(1);
    expect(new URL(sockets[0].url).searchParams.has("token")).toBe(false);
  });

  it("refreshes the JWT and reconnects with the new access token after 4401", async () => {
    const refreshedSession: AuthSession = {
      access_token: "new-access-token",
      refresh_token: "new-refresh-token",
      token_type: "bearer",
      role: "ceo",
    };

    vi.mocked(refreshAuthSession).mockImplementation(async () => {
      authMocks.session = refreshedSession;
      return refreshedSession;
    });
    const onAuthSessionRefreshed = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
        onAuthSessionRefreshed,
      }),
    );

    await act(async () => {
      sockets[0].onclose?.({ code: 4401 });
    });

    expect(refreshAuthSession).toHaveBeenCalledTimes(1);
    expect(onAuthSessionRefreshed).toHaveBeenCalledWith(refreshedSession);
    expect(sockets).toHaveLength(2);

    expect(
      new URL(sockets[1].url).searchParams.get("token"),
    ).toBe("new-access-token");
  });

  it("shows failed when JWT refresh fails after 4401", async () => {
    vi.mocked(refreshAuthSession).mockRejectedValue(
      new Error("Refresh failed"),
    );

    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    await act(async () => {
      sockets[0].onclose?.({ code: 4401 });
    });

    expect(refreshAuthSession).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(1);
    expect(result.current.failed).toBe(true);
    expect(result.current.isConnecting).toBe(false);
  });

  it("does not refresh repeatedly when the reconnected socket closes with 4401", async () => {
    const refreshedSession: AuthSession = {
      access_token: "new-access-token",
      refresh_token: "new-refresh-token",
      token_type: "bearer",
      role: "ceo",
    };

    vi.mocked(refreshAuthSession).mockImplementation(async () => {
      authMocks.session = refreshedSession;
      return refreshedSession;
    });
    const { result } = renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8080",
        onMessage: vi.fn(),
      }),
    );

    await act(async () => {
      sockets[0].onclose?.({ code: 4401 });
    });

    expect(sockets).toHaveLength(2);

    act(() => {
      sockets[1].onclose?.({ code: 4401 });
    });

    expect(refreshAuthSession).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(2);
    expect(result.current.failed).toBe(true);
  });

  it("refreshes again when the new token expires later in the session", async () => {
    vi.mocked(refreshAuthSession).mockImplementation(async () => {
      const callNumber = vi.mocked(refreshAuthSession).mock.calls.length;
      const nextSession: AuthSession = {
        access_token: `access-token-${callNumber}`,
        refresh_token: `refresh-token-${callNumber}`,
        token_type: "bearer",
        role: "ceo",
      };
      authMocks.session = nextSession;
      return nextSession;
    });

    const { result } = renderHook(() =>
      useWebSocket({ url: "ws://localhost:8080", onMessage: vi.fn() }),
    );

    // First expiry: refresh, reconnect, and the new socket opens.
    await act(async () => {
      sockets[0].onclose?.({ code: 4401 });
    });
    act(() => {
      sockets[1].onopen?.();
    });
    expect(result.current.connected).toBe(true);

    // The new token expires later in the same session.
    act(() => {
      vi.advanceTimersByTime(61_000);
    });
    await act(async () => {
      sockets[1].onclose?.({ code: 4401 });
    });

    expect(refreshAuthSession).toHaveBeenCalledTimes(2);
    expect(sockets).toHaveLength(3);
    expect(new URL(sockets[2].url).searchParams.get("token")).toBe(
      "access-token-2",
    );
    expect(result.current.failed).toBe(false);
  });
});
