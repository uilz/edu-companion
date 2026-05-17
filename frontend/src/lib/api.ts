import { Settings, StreamEvent } from "@/types";

let ws: WebSocket | null = null;
let tokenBuffer = "";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return "";
}

export function getSettings(): Settings {
  if (typeof window === "undefined") {
    return { apiEndpoint: "", apiKey: "", modelName: "", systemPrompt: "你是一个智能学习助手，善于用简单易懂的方式解释复杂的概念。回答时使用中文，必要时使用数学公式。" };
  }
  const saved = localStorage.getItem("edu-companion-settings");
  if (saved) {
    return JSON.parse(saved);
  }
  return {
    apiEndpoint: "",
    apiKey: "",
    modelName: "",
    systemPrompt: "你是一个智能学习助手，善于用简单易懂的方式解释复杂的概念。回答时使用中文，必要时使用数学公式。",
  };
}

export function saveSettings(settings: Settings): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("edu-companion-settings", JSON.stringify(settings));
  }
}

export function connectWebSocket(
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): void {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);
        switch (data.type) {
          case "token":
            if (data.content) {
              tokenBuffer += data.content;
              onToken(data.content);
            }
            break;
          case "done":
            onDone();
            break;
          case "error":
            onError(data.content || "未知错误");
            break;
        }
      } catch {
        onError("解析消息失败");
      }
    };

    ws.onerror = () => {
      onError("WebSocket 连接错误");
    };

    ws.onclose = () => {
      ws = null;
    };
  } catch {
    onError("无法建立 WebSocket 连接");
  }
}

export function sendMessage(
  conversationId: string,
  message: string,
  settings: Settings
): void {
  tokenBuffer = "";
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        conversationId,
        message,
        settings,
      })
    );
  }
}

export function disconnectWebSocket(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
}

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

// Fallback REST streaming via fetch
export async function sendViaFetch(
  conversationId: string,
  message: string,
  settings: Settings,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, message, settings }),
    });

    if (!res.ok) {
      onError(`请求失败: ${res.status}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError("无法读取响应流");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            onDone();
            return;
          }
          try {
            const parsed: StreamEvent = JSON.parse(data);
            if (parsed.type === "token" && parsed.content) {
              onToken(parsed.content);
            } else if (parsed.type === "error") {
              onError(parsed.content || "流处理错误");
            }
          } catch {
            onToken(data);
          }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "请求失败");
  }
}
