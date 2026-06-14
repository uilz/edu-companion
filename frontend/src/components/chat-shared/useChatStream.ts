"use client";

import { useCallback, useRef, useState } from "react";
import { parseSSEStream, SSE_EVENTS } from "@/store/pipeline/sse-parser";
import { createTokenThrottle } from "@/store/pipeline/token-throttle";

export interface ToolCallEvent {
  name: string;
  arguments: Record<string, unknown>;
  confidence: number;
  require_confirmation: boolean;
  route?: { target: string; params?: Record<string, string> };
  confirmation_text: string;
}

export interface ChatStreamConfig {
  /** SSE 端点 */
  endpoint: string;
  /** 额外的请求体字段 */
  bodyExtra?: Record<string, unknown>;
  /** 收到 token 时的回调 */
  onToken?: (delta: string) => void;
  /** 收到工具调用时的回调 */
  onToolCall?: (tc: ToolCallEvent) => void;
  /** 收到 conversation_id 时的回调 */
  onConversationId?: (id: string) => void;
  /** 完成时的回调 */
  onDone?: () => void;
  /** 错误时的回调 */
  onError?: (msg: string) => void;
}

/** 获取认证头 */
function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token") || localStorage.getItem("token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (message: string, config: ChatStreamConfig) => {
    setStreaming(true);
    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const response = await fetch(config.endpoint, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          message,
          ...config.bodyExtra,
        }),
        signal: abort.signal,
      });

      if (!response.ok) {
        config.onError?.("抱歉，请求失败，请稍后重试。");
        setStreaming(false);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        setStreaming(false);
        config.onDone?.();
        return;
      }

      // 使用共享的 SSE 解析器 + token 节流
      const throttle = createTokenThrottle((text) => config.onToken?.(text));
      await parseSSEStream(reader, {
        onData: (data, eventType) => {
          switch (eventType) {
            case SSE_EVENTS.TOKEN:
              throttle.add((data.delta as string) || "");
              break;
            case SSE_EVENTS.TOOL_CALL:
              if (data.name && data.arguments) {
                config.onToolCall?.({
                  name: data.name as string,
                  arguments: data.arguments as Record<string, unknown>,
                  confidence: (data.confidence as number) || 0.5,
                  require_confirmation: data.require_confirmation !== false,
                  route: data.route as { target: string; params?: Record<string, string> } | undefined,
                  confirmation_text: (data.confirmation_text as string) || "",
                });
              }
              break;
            case SSE_EVENTS.CONVERSATION:
              if (data.conversation_id) {
                config.onConversationId?.(data.conversation_id as string);
              }
              break;
          }
        },
        onDone: () => {
          throttle.flush();
          setStreaming(false);
          config.onDone?.();
        },
      }, abort.signal);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      config.onError?.("网络错误，请检查连接后重试。");
    } finally {
      setStreaming(false);
      config.onDone?.();
    }
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { streaming, send, abort };
}
