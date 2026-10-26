import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AlertMessage,
  AnalyticsEventEnvelope,
  InventoryItem,
  InventoryUpdate,
  WebSocketMessage,
} from "../types/forecast";
import { mapAnalyticsEventToAlert } from "../utils/alertMapper";
interface UseWebSocketOptions {
  url: string;
  onMessage: (data: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxRetries?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isInventoryItem(value: unknown): value is InventoryItem {
  if (!isRecord(value)) return false;

  return (
    typeof value.sku_id === "string" &&
    typeof value.product_name === "string" &&
    typeof value.category === "string" &&
    typeof value.warehouse_id === "string" &&
    typeof value.quantity_on_hand === "number" &&
    typeof value.reorder_point === "number" &&
    typeof value.needs_reorder === "boolean" &&
    typeof value.avg_daily_demand === "number"
  );
}

function isInventoryUpdate(value: unknown): value is InventoryUpdate {
  return (
    isRecord(value) &&
    value.type === "inventory_update" &&
    isInventoryItem(value.item)
  );
}


function isSupportedEventVersion(value: unknown): boolean {
  return value === 1 || value === "1" || value === "1.0";
}


function isAnalyticsEvent(value: unknown): value is AnalyticsEventEnvelope {
  return (
    isRecord(value) &&
    typeof value.event_id === "string" &&
    typeof value.event_type === "string" &&
    isSupportedEventVersion(value.event_version) &&
    typeof value.occurred_at === "string" &&
    typeof value.producer === "string" &&
    isRecord(value.payload) &&
    (value.trace_id === undefined ||
      value.trace_id === null ||
      typeof value.trace_id === "string")
  );
}

export function useWebSocket({
  url,
  onMessage,
  onError,
  autoReconnect = true,
  maxRetries = 5,
}: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [failed, setFailed] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);

  const retryCountRef = useRef(0);

  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const connectRef = useRef<(() => void) | null>(null);
  const seenEventIdsRef = useRef(new Set<string>());
  const intentionalCloseRef = useRef(false);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const retryConnection = useCallback(() => {
    retryCountRef.current = 0;
    setFailed(false);
    intentionalCloseRef.current = true;

    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const socket = socketRef.current;
    socketRef.current = null;

    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      socket.close();
    }

    intentionalCloseRef.current = false;
    connectRef.current?.();
  }, []);

  useEffect(() => {
    let isUnmounted = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const scheduleReconnect = (delay: number) => {
      if (isUnmounted) return;

      if (retryCountRef.current >= maxRetries) {
        setFailed(true);
        setIsConnecting(false);
        return;
      }

      retryCountRef.current += 1;
      setIsConnecting(false);

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (!isUnmounted) connect();
      }, delay);
    };

    const connect = () => {
      if (isUnmounted) {
        return;
      }

      clearReconnectTimer();
      setFailed(false);
      setIsConnecting(true);

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        setConnected(false);
        setIsConnecting(false);

        if (autoReconnect) {
          const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
          scheduleReconnect(delay);
        } else {
          setFailed(true);
        }

        return;
      }

      socketRef.current = socket;

      socket.onopen = () => {
        if (isUnmounted) return;

        setConnected(true);
        setIsConnecting(false);
        setFailed(false);
        retryCountRef.current = 0;
      };

      socket.onmessage = (event: MessageEvent) => {
        if (isUnmounted) {
          return;
        }
        let data: unknown;
        try {
          data = JSON.parse(String(event.data)) as unknown;
        } catch {
          console.error("Ignoring invalid WebSocket JSON.");
          return;
        }

        if (isInventoryUpdate(data)) {
          onMessageRef.current(data);
          return;
        }

        // Ignore malformed R15-M1 envelopes.
        if (!isAnalyticsEvent(data)) {
          console.error("Ignoring malformed analytics event:", data);
          return;
        }

        if (seenEventIdsRef.current.has(data.event_id)) return;

        seenEventIdsRef.current.add(data.event_id);

        if (seenEventIdsRef.current.size > 100) {
          const oldestId = seenEventIdsRef.current.values().next().value;
          if (oldestId !== undefined) {
            seenEventIdsRef.current.delete(oldestId);
          }
        }

        const alert: AlertMessage | null = mapAnalyticsEventToAlert(data);

        // Valid event types not supported by this dashboard are ignored.
        if (alert) onMessageRef.current(alert);
      };

      socket.onerror = (error: Event) => {
        if (isUnmounted) return;
        onErrorRef.current?.(error);
      };

      socket.onclose = (event: CloseEvent) => {
        if (isUnmounted) return;

        socketRef.current = null;
        setConnected(false);
        setIsConnecting(false);

        if (intentionalCloseRef.current || event.code === 1000) {
          return;
        }

        if (event.code === 4403) {
          setFailed(true);
          return;
        }

        if (!autoReconnect) {
          setFailed(true);
          return;
        }

        // Unauthorized: authentication refresh must happen before reconnecting.
        // Until that is wired in, stop and expose the Retry Connection control.
        if (event.code === 4401) {
          setFailed(true);
          return;
        }

        // Rate limited: wait 60 seconds before trying again.
        if (event.code === 4429) {
          scheduleReconnect(60000);
          return;
        }

        // Abnormal closure: exponential backoff, capped at 30 seconds.
        const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
        scheduleReconnect(delay);
      };
    };

    connectRef.current = connect;
    connect();

    return () => {
      isUnmounted = true;
      connectRef.current = null;
      clearReconnectTimer();

      const socket = socketRef.current;
      socketRef.current = null;

      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close(1000, "Component unmounted");
      }
    };
  }, [url, autoReconnect, maxRetries]);

  return { connected, isConnecting, failed, retryConnection };
}
