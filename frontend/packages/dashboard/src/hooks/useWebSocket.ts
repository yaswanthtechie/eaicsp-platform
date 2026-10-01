import { useEffect, useRef, useState } from "react";
import type {
    AlertMessage,
    InventoryUpdate,
    WebSocketMessage,
} from "../types/forecast";

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxRetries?: number;
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

  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    let isUnmounted = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      if (isUnmounted) {
        return;
      }

      clearReconnectTimer();

      setIsConnecting(true);

      const socket = new WebSocket(url);

      socketRef.current = socket;

      socket.onopen = () => {
        if (isUnmounted) {
          return;
        }

        setConnected(true);
        setIsConnecting(false);
        setFailed(false);

        retryCountRef.current = 0;
      };

      socket.onmessage = (event) => {
        if (isUnmounted) {
          return;
        }

        try {
          const data: unknown = JSON.parse(event.data);

          if (
            typeof data !== "object" ||
            data === null
          ) {
            console.error("Ignoring malformed WebSocket message:", data);
            return;
          }

          const message = data as Record<string, unknown>;

          if (message.type === "inventory_update") {
            const item = message.item;

            if (
              typeof item !== "object" ||
              item === null
            ) {
              console.error("Ignoring malformed inventory update:", data);
              return;
            }

            const inventoryItem = item as Record<string, unknown>;

            if (
              typeof inventoryItem.sku_id !== "string" ||
              typeof inventoryItem.product_name !== "string" ||
              typeof inventoryItem.warehouse_id !== "string" ||
              typeof inventoryItem.quantity_on_hand !== "number" ||
              typeof inventoryItem.reorder_point !== "number" ||
              typeof inventoryItem.needs_reorder !== "boolean" ||
              typeof inventoryItem.avg_daily_demand !== "number"
            ) {
              console.error(
                "Ignoring malformed inventory update:",
                data,
              );
              return;
            }

            onMessageRef.current(data as InventoryUpdate);
            return;
          }

          if (
            typeof message.id !== "string" ||
            typeof message.type !== "string" ||
            typeof message.severity !== "string" ||
            typeof message.message !== "string" ||
            typeof message.timestamp !== "string"
          ) {
            console.error("Ignoring malformed alert:", data);
            return;
          }

          onMessageRef.current(data as AlertMessage);
        } catch (error) {
          console.error("Invalid WebSocket message:", error);
        }
      };

      socket.onerror = (error) => {
        if (isUnmounted) {
          return;
        }

        onErrorRef.current?.(error);
      };

      socket.onclose = () => {
        if (isUnmounted) {
          return;
        }

        socketRef.current = null;

        setConnected(false);
        setIsConnecting(false);

        if (
          autoReconnect &&
          retryCountRef.current < maxRetries
        ) {
          const delay = Math.min(
            1000 * 2 ** retryCountRef.current,
            30000,
          );

          retryCountRef.current += 1;

          reconnectTimerRef.current = setTimeout(() => {
            reconnectTimerRef.current = null;

            if (!isUnmounted) {
              connect();
            }
          }, delay);
        } else {
          if (retryCountRef.current >= maxRetries) {
            setFailed(true);
          }

          clearReconnectTimer();
        }
      };
    };

    connect();

    return () => {
      isUnmounted = true;

      clearReconnectTimer();

      const socket = socketRef.current;

      socketRef.current = null;

      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;

        socket.close();
      }
    };
  }, [url, autoReconnect, maxRetries]);

  return {
    connected,
    isConnecting,
    failed,
  };
}