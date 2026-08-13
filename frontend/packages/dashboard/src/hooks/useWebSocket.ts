import { useEffect, useRef, useState } from "react";
import type { AlertMessage } from "../types/forecast";

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: AlertMessage) => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxRetries?: number;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    onMessage,
    onError,
    autoReconnect = true,
    maxRetries = 5,
  } = options;

  const [connected, setConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<
    ReturnType<typeof setTimeout> | null
  >(null);

  useEffect(() => {
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) {
        return;
      }

      setIsConnecting(true);

      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        if (isUnmounted) {
          return;
        }

        setConnected(true);
        setIsConnecting(false);

        retryCountRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (
            typeof data.id !== "string" ||
            typeof data.type !== "string" ||
            typeof data.severity !== "string" ||
            typeof data.message !== "string" ||
            typeof data.timestamp !== "string"
          ) {
            console.error(
              "Ignoring malformed alert:",
              data
            );
            return;
          }

          onMessage(data as AlertMessage);
        } catch (error) {
          console.error(
            "Invalid WebSocket message:",
            error
          );
        }
      };

      socket.onerror = (error) => {
        onError?.(error);
      };

      socket.onclose = () => {
        if (isUnmounted) {
          return;
        }

        setConnected(false);
        setIsConnecting(false);

        if (
          autoReconnect &&
          retryCountRef.current < maxRetries
        ) {
          const delay = Math.min(
            1000 * 2 ** retryCountRef.current,
            30000
          );

          retryCountRef.current += 1;

          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    };

    connect();

    return () => {
      isUnmounted = true;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }

      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [
    url,
    onMessage,
    onError,
    autoReconnect,
    maxRetries,
  ]);

  return {
    connected,
    isConnecting,
  };
}