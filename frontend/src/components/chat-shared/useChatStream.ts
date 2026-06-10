"use client";

import { useCallback, useRef, useState } from "react";

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

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const raw = line.slice(6);
            try {
              const data = JSON.parse(raw);
              if (currentEvent === "token") {
                config.onToken?.(data.delta || "");
              } else if (currentEvent === "tool_call") {
                if (data.name && data.arguments) {
                  config.onToolCall?.({
                    name: data.name,
                    arguments: data.arguments,
                    confidence: data.confidence || 0.5,
                    require_confirmation: data.require_confirmation !== false,
                    route: data.route,
                    confirmation_text: data.confirmation_text || "",
                  });
                }
              } else if (currentEvent === "conversation") {
                if (data.conversation_id) {
                  config.onConversationId?.(data.conversation_id);
                }
              }
            } catch {
              // skip non-JSON data lines
            }
          }
        }
      }
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