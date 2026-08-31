import { useEffect, useRef, useState } from "react";
import type { AlertMessage } from "../types/forecast";

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: AlertMessage) => void;
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
            data === null ||
            typeof (data as Record<string, unknown>).id !== "string" ||
            typeof (data as Record<string, unknown>).type !== "string" ||
            typeof (data as Record<string, unknown>).severity !== "string" ||
            typeof (data as Record<string, unknown>).message !== "string" ||
            typeof (data as Record<string, unknown>).timestamp !== "string"
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
          setFailed(true);
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