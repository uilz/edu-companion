// ══════════════════════════════════════════════════════════════
//  sse-parser — 共享 SSE 行解析器
//
//  从 ReadableStream 中解析 text/event-stream 格式的 SSE 数据。
//  消除 useChatStream 与未来可能的其他 SSE 客户端之间的重复解析逻辑。
// ══════════════════════════════════════════════════════════════

export interface SSELineHandler {
  /** 收到 event: 行（可选，默认 "message"） */
  onEvent?: (eventType: string) => void;
  /** 收到 data: 行，JSON 已解析 */
  onData?: (data: Record<string, unknown>, eventType: string) => void;
  /** 流结束 */
  onDone?: () => void;
}

// SSE 协议事件名称（常量化避免 magic string）
export const SSE_EVENTS = {
  TOKEN: "token",
  TOOL_CALL: "tool_call",
  CONVERSATION: "conversation",
  DONE: "done",
  STREAM_END: "stream_end",
  ERROR: "error",
} as const;

/**
 * 从 ReadableStreamDefaultReader 读取并解析 SSE 格式数据。
 * 逐行解析 event: / data: 对，通过 handler 回调分发。
 *
 * @param reader — ReadableStreamDefaultReader<Uint8Array>
 * @param handler — SSELineHandler 回调
 * @param signal  — AbortSignal 用于取消
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  handler: SSELineHandler,
  signal?: AbortSignal,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    if (signal?.aborted) break;

    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
        handler.onEvent?.(currentEvent);
      } else if (line.startsWith("data: ")) {
        const raw = line.slice(6);
        try {
          const data = JSON.parse(raw);
          handler.onData?.(data, currentEvent);
        } catch {
          // skip non-JSON data lines
        }
      }
    }
  }

  handler.onDone?.();
}
