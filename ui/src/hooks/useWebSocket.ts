import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export type WebSocketEventType =
  | "request.started"
  | "request.completed"
  | "request.error"
  | "provider.health"
  | "stats.update"
  | "connected"
  | "ping"
  | "pong";

export interface WebSocketMessage<T = unknown> {
  type: WebSocketEventType;
  data: T;
  timestamp: string;
}

export interface RequestStartedData {
  request_id: string;
  provider: string;
  model: string | null;
  agent_type: string | null;
}

export interface RequestCompletedData {
  request_id: string;
  provider: string;
  status_code: number;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface RequestErrorData {
  request_id: string;
  provider: string;
  error: string;
  error_type: string | null;
}

export interface ProviderHealthData {
  provider: string;
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  latency_ms: number | null;
}

export type Topic = "requests" | "providers" | "stats" | "all";

interface UseWebSocketOptions {
  topics?: Topic[];
  autoReconnect?: boolean;
  reconnectInterval?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  connect: () => void;
  disconnect: () => void;
  sendPing: () => void;
}

export function useWebSocket(
  options: UseWebSocketOptions = {},
): UseWebSocketReturn {
  const {
    topics = ["all"],
    autoReconnect = true,
    reconnectInterval = 5000,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const connectRef = useRef<() => void>(() => {});

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mountedRef.current) {
      setIsConnected(false);
    }
  }, [clearReconnectTimeout]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    clearReconnectTimeout();

    const topicsQuery = topics.map((t) => `topics=${t}`).join("&");
    const ws = api.createWebSocket(`/ws/live?${topicsQuery}`);

    ws.onopen = () => {
      if (mountedRef.current) {
        setIsConnected(true);
        onConnect?.();
      }
    };

    ws.onclose = () => {
      if (mountedRef.current) {
        setIsConnected(false);
        onDisconnect?.();

        if (autoReconnect) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            if (mountedRef.current) {
              connectRef.current();
            }
          }, reconnectInterval);
        }
      }
    };

    ws.onerror = (event) => {
      onError?.(event);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        if (mountedRef.current) {
          setLastMessage(message);
          onMessage?.(message);
        }
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    wsRef.current = ws;
  }, [
    topics,
    autoReconnect,
    reconnectInterval,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    clearReconnectTimeout,
  ]);

  // Keep connectRef in sync with connect
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "ping" }));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect,
    sendPing,
  };
}

export function useRequestEvents(
  onRequestStarted?: (data: RequestStartedData) => void,
  onRequestCompleted?: (data: RequestCompletedData) => void,
  onRequestError?: (data: RequestErrorData) => void,
) {
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case "request.started":
          onRequestStarted?.(message.data as RequestStartedData);
          break;
        case "request.completed":
          onRequestCompleted?.(message.data as RequestCompletedData);
          break;
        case "request.error":
          onRequestError?.(message.data as RequestErrorData);
          break;
      }
    },
    [onRequestStarted, onRequestCompleted, onRequestError],
  );

  return useWebSocket({
    topics: ["requests"],
    onMessage: handleMessage,
  });
}

export function useProviderEvents(
  onProviderHealth?: (data: ProviderHealthData) => void,
) {
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === "provider.health") {
        onProviderHealth?.(message.data as ProviderHealthData);
      }
    },
    [onProviderHealth],
  );

  return useWebSocket({
    topics: ["providers"],
    onMessage: handleMessage,
  });
}
