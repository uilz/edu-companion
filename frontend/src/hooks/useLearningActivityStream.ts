"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api/api";
import type { LearningActivity } from "@/lib/api/learning-activity-api";

export type ActivityStreamEventType =
  | "connected"
  | "activity_created"
  | "activity_updated"
  | "heartbeat";

export interface ActivityStreamEvent {
  event: ActivityStreamEventType;
  activity_id: string | null;
  user_id: string;
  data: Partial<LearningActivity>;
  timestamp: number;
}

export interface UseLearningActivityStreamOptions {
  /** 建立连接后是否立即触发一次活动列表刷新 */
  refetchOnConnect?: () => void;
  /** 收到新活动时回调 */
  onActivity?: (event: ActivityStreamEvent) => void;
  /** 连接状态变化回调 */
  onConnectionChange?: (connected: boolean) => void;
}

export interface UseLearningActivityStreamReturn {
  connected: boolean;
  lastEvent: ActivityStreamEvent | null;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/**
 * 学习活动实时 SSE 流 hook
 *
 * 用法：
 *   const { connected, lastEvent } = useLearningActivityStream({
 *     onActivity: (evt) => {
 *       if (evt.event === "activity_created") console.log("新活动", evt.data);
 *     },
 *   });
 */
export function useLearningActivityStream(
  options: UseLearningActivityStreamOptions = {},
): UseLearningActivityStreamReturn {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<ActivityStreamEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const optionsRef = useRef(options);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    reconnectAttemptRef.current = 0;
    setConnected(false);
  }, []);

  const connect = useCallback(() => {
    disconnect();

    const token = getAccessToken();
    if (!token) {
      setError("未登录");
      return;
    }

    const url = `${API_BASE}/api/activities/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      reconnectAttemptRef.current = 0;
      setConnected(true);
      setError(null);
      optionsRef.current.onConnectionChange?.(true);
    };

    es.onmessage = (message) => {
      if (!message.data) return;

      // 心跳无 payload
      if (message.data.includes("heartbeat")) {
        setLastEvent({
          event: "heartbeat",
          activity_id: null,
          user_id: "",
          data: {},
          timestamp: Date.now(),
        });
        return;
      }

      try {
        const payload = JSON.parse(message.data) as ActivityStreamEvent;
        setLastEvent(payload);

        if (payload.event === "connected") {
          optionsRef.current.refetchOnConnect?.();
        } else if (
          payload.event === "activity_created" ||
          payload.event === "activity_updated"
        ) {
          optionsRef.current.onActivity?.(payload);
        }
      } catch {
        // 忽略无法解析的消息
      }
    };

    es.onerror = () => {
      setConnected(false);
      optionsRef.current.onConnectionChange?.(false);
      // 指数退避重连，最大 30 秒
      reconnectAttemptRef.current = Math.min(reconnectAttemptRef.current + 1, 6);
      const delay = Math.min(1000 * 2 ** reconnectAttemptRef.current, 30000);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };
  }, [disconnect]);

  useEffect(() => {
    connect();

    const onVisibilityChange = () => {
      if (document.hidden) {
        disconnect();
      } else {
        connect();
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    lastEvent,
    error,
    reconnect: connect,
    disconnect,
  };
}
