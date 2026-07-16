// ============================================================
// Session 💬 Chat API（G1: 真实 Conversation 接入）
//
// 职责:
//  将 EXP-04 的 💬 从本地 Conversation Engine
// 切换到后端真实 `/api/conversations/tree/conversation/{convId}/message` 端点
//
// 用法:
//  1. 创建 sessionChatApi 实例
//  2. 调用 sendMessage() → 返回 AsyncGenerator 逐块 yield text
//  3. 外部消费 stream 并追加到 messages[]
//
// 原则:
//  - 不改变 1 轮限制逻辑（由外部控制）
//  - 不改变 UI 样式
//  - SSE 错误时 fallback 到本地引擎（不崩溃）
// ============================================================

import { authedFetch } from "@/lib/api/api";

/** SSE 事件回调 */
export interface ChatStreamCallbacks {
  onChunk: (text: string) => void;
  onDone: (fullText: string) => void;
  onError: (error: Error) => void;
}

/** 创建 SSE 流式聊天连接 */
export async function sendChatMessage(
  convId: string,
  dirId: string,
  text: string,
  callbacks: ChatStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await authedFetch(
      `/api/conversations/tree/conversation/${convId}/message`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "send",
          text,
          dir_id: dirId,
          parent_id: "",
        }),
        signal,
      },
    );

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";
    let inContent = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") {
            callbacks.onDone(fullText);
            return;
          }
          try {
            const parsed = JSON.parse(data);
            // 处理不同的 event 格式
            const content =
              parsed.content ||
              parsed.text ||
              parsed.delta ||
              parsed.message ||
              "";
            if (content) {
              fullText += content;
              callbacks.onChunk(content);
            }
          } catch {
            // 非 JSON 的 data 行
            if (data && data !== "[DONE]") {
              fullText += data;
              callbacks.onChunk(data);
            }
          }
        }
      }
    }

    callbacks.onDone(fullText);
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
  }
}
